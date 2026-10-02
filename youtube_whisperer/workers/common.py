import logging
from abc import ABC, abstractmethod
from collections.abc import Callable, Generator
from pathlib import Path
from typing import cast

import redis
from redis import StrictRedis

from youtube_whisperer.config import Settings
from youtube_whisperer.domain import TranscriberType, is_url
from youtube_whisperer.models import Task
from youtube_whisperer.queueing import (
    WORKERS_GROUP,
    decode_redis_value,
    ensure_consumer_group,
    get_stream_name,
    queue_dead_letter,
)
from youtube_whisperer.runtime import Runtime

logger = logging.getLogger(__name__)

TaskDispatcher = Callable[[Task, Path], None]
StreamReadResponse = list[tuple[bytes, list[tuple[bytes, dict[bytes, bytes]]]]]
# XAUTOCLAIM returns (next_cursor, [(message_id, fields), ...], [deleted_ids]).
XAutoClaimResponse = tuple[bytes, list[tuple[bytes, dict[bytes, bytes]]], list[bytes]]

DEFAULT_CLAIM_MIN_IDLE_SECONDS = 21600  # 6 hours; see Settings.worker_claim_min_idle_seconds


def _decode_task(fields: dict[bytes, bytes], stream_name: str, log_message: str) -> Task:
    """Decode, log and validate a payload without containing malformed task errors.

    Args:
        fields: Redis message fields containing the serialized task payload.
        stream_name: Stream whose task is being recovered or received.
        log_message: Stage-specific logging format retained by the polling loop.

    Returns:
        The validated task.
    """
    payload = decode_redis_value(fields[b'payload'])
    logger.info(log_message, stream_name, payload)
    return Task.model_validate_json(payload)


def yield_task(
    client: StrictRedis,
    stream_name: str,
    group_name: str,
    consumer_name: str,
    poll_interval_seconds: int = 5,
    claim_min_idle_seconds: int = DEFAULT_CLAIM_MIN_IDLE_SECONDS,
) -> Generator[tuple[bytes, Task], None, None]:
    """Poll a Redis Stream and yield tasks assigned to this consumer group.

    Each loop iteration: (1) resumes this consumer's own orphaned PEL entries (crash recovery),
    (2) claims PEL entries stranded by other (likely dead) consumer identities that have been idle
    longer than ``claim_min_idle_seconds`` via XAUTOCLAIM, then (3) blocks for newly queued tasks.
    The claim step keeps tasks abandoned by a vanished consumer name from being pinned "active"
    forever; the idle threshold must exceed the longest plausible processing time so a task
    in-flight on a live worker is never stolen. Each generator retains the next claim cursor,
    including across empty pages and yielded tasks, and resets it after group recreation.
    One claim page per cycle leaves new work an opportunity after an empty claim.

    Args:
        client (StrictRedis): The Redis client to read from.
        stream_name (str): The stream to consume tasks from.
        group_name (str): The consumer group shared by all workers of this type.
        consumer_name (str): This worker's consumer identity, used to recover its own PEL.
        poll_interval_seconds (int): How long each blocking read waits for new messages.
        claim_min_idle_seconds (int): Minimum idle time before a PEL entry owned by another
            consumer is claimed by this worker.

    Raises:
        ValueError: On first iteration, before Redis commands, if polling is not
            positive or claim idle time is negative. Zero idle time claims immediately.

    Yields:
        A tuple of (Message ID bytes, Validated Task model).
    """
    if poll_interval_seconds <= 0:
        raise ValueError("poll_interval_seconds must be positive")
    if claim_min_idle_seconds < 0:
        raise ValueError("claim_min_idle_seconds must be nonnegative")
    ensure_consumer_group(client, stream_name, group_name)
    claim_min_idle_ms = claim_min_idle_seconds * 1000
    claim_cursor: str | bytes = '0-0'

    while True:
        try:
            pending_messages = cast(
                StreamReadResponse,
                client.xreadgroup(group_name, consumer_name, {stream_name: '0-0'}, count=1),
            )
            if pending_messages:
                _stream, messages = pending_messages[0]
                if messages:
                    msg_id, fields = messages[0]
                    yield msg_id, _decode_task(fields, stream_name, "Resuming orphaned task from %s: %s")
                    continue
            claim_cursor, claimed_messages, *_deleted = cast(
                XAutoClaimResponse,
                client.xautoclaim(stream_name, group_name, consumer_name, min_idle_time=claim_min_idle_ms, start_id=claim_cursor, count=1),
            )
            if claimed_messages:
                msg_id, fields = claimed_messages[0]
                yield msg_id, _decode_task(fields, stream_name, "Claimed stranded task from %s: %s")
                continue
            new_messages = cast(
                StreamReadResponse,
                client.xreadgroup(
                    group_name,
                    consumer_name,
                    {stream_name: '>'},
                    count=1,
                    block=poll_interval_seconds * 1000
                ),
            )
            if new_messages:
                _stream, messages = new_messages[0]
                if messages:
                    msg_id, fields = messages[0]
                    yield msg_id, _decode_task(fields, stream_name, "Claimed new task from %s: %s")
        except redis.exceptions.ResponseError as e:
            if "NOGROUP" in str(e):
                ensure_consumer_group(client, stream_name, group_name)
                claim_cursor = '0-0'
                continue
            raise


class BaseWorker(ABC):
    """Abstract base worker providing a robust task-processing loop via Redis Streams."""

    def __init__(self, client: StrictRedis | None = None, *, stream_name: str | None = None, slot: str | None = None, settings: Settings | None = None, runtime: Runtime | None = None) -> None:
        """Bind the worker to the Redis client it consumes and acknowledges tasks on.

        Args:
            client: Redis client used for stream reads, acknowledgements, and dead-lettering.
                Borrowed when supplied; otherwise owned by this worker.
            stream_name: Stream key, omitted only by legacy subclasses overriding accessors.
            slot: Consumer identity, omitted only by legacy subclasses overriding accessors.
            settings: Supplied settings snapshot, or invocation-time environment defaults.
            runtime: Borrowed runtime supplying resources and the authoritative snapshot.
        """
        if stream_name is not None:
            self.stream_name = stream_name
        if slot is not None:
            self.slot = slot
        self._owns_runtime = runtime is None
        self.runtime = runtime if runtime is not None else Runtime(settings if settings is not None else Settings(), client)
        self.settings = self.runtime.settings
        self.client = self.runtime.client

    def get_stream_name(self) -> str:
        """Return the active stream name for the worker.

        Returns:
            The Redis key string for the stream this worker consumes.

        Raises:
            NotImplementedError: If a legacy subclass supplies no stream or override.
        """
        try:
            return self.stream_name
        except AttributeError as exc:
            raise NotImplementedError("Worker stream identity is not configured") from exc

    def get_consumer_name(self) -> str:
        """Return the active consumer identity, including later slot assignments.

        Raises:
            NotImplementedError: If a legacy subclass supplies no slot or override.
        """
        try:
            return self.slot
        except AttributeError as exc:
            raise NotImplementedError("Worker consumer identity is not configured") from exc

    def yield_tasks(self, poll_interval_seconds: int) -> Generator[tuple[bytes, Task], None, None]:
        """Yield tasks from the worker's queue.

        Args:
            poll_interval_seconds: Number of seconds to wait before checking again when the queue is empty.

        Raises:
            ValueError: If the polling interval is not positive.

        Yields:
            Validated task models alongside their message sequence IDs.
        """
        if poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds must be positive")
        stream_name = self.get_stream_name()
        consumer_name = self.get_consumer_name()
        logger.info("Worker for %s started with consumer identity: %s", stream_name, consumer_name)
        return yield_task(
            client=self.client,
            stream_name=stream_name,
            group_name=WORKERS_GROUP,
            consumer_name=consumer_name,
            poll_interval_seconds=poll_interval_seconds,
            claim_min_idle_seconds=self.settings.worker_claim_min_idle_seconds,
        )

    @abstractmethod
    def process_task(self, task: Task) -> None:
        """Process a single task.

        Args:
            task: The task to be processed by this worker.
        """

    def process_queue(self, poll_interval_seconds: int = 5) -> None:
        """Poll the queue indefinitely and process tasks.

        Invalid polling closes an owned runtime while leaving borrowed resources open.
        A message is acknowledged and deleted only after the task succeeds or is
        durably dead-lettered. If processing is aborted by a BaseException (e.g.
        KeyboardInterrupt) or the dead-letter write itself fails, the acknowledgement
        is skipped so the message stays in the consumer's pending list and a restarted
        worker can recover it via its PEL.

        Args:
            poll_interval_seconds: Positive seconds between empty-queue checks.

        Raises:
            ValueError: If the polling interval is not positive.
        """
        try:
            if poll_interval_seconds <= 0:
                raise ValueError("poll_interval_seconds must be positive")
            stream_name = self.get_stream_name()
            for msg_id, task in self.yield_tasks(poll_interval_seconds):
                try:
                    self.process_task(task)
                except Exception as e:
                    logger.exception("Error processing task %s", task)
                    queue_dead_letter(self.client, task, stream_name, str(e))
                # Reached only on success or after a durable dead-letter; a BaseException
                # or a failed dead-letter skips the acknowledgement and leaves the message
                # pending for recovery.
                pipe = self.client.pipeline()
                pipe.xack(stream_name, WORKERS_GROUP, msg_id)
                pipe.xdel(stream_name, msg_id)
                pipe.execute()
                logger.info("Acknowledged and deleted task from %s: %s", stream_name, task)
        finally:
            if self._owns_runtime:
                self.runtime.close()


class TranscriptionWorker(BaseWorker):
    """Base class for transcriber workers utilizing Native Streams."""

    def __init__(self, transcriber: TranscriberType, slot: str, client: StrictRedis | None = None, *, settings: Settings | None = None, runtime: Runtime | None = None) -> None:
        """Initialize the transcription worker.

        Args:
            transcriber: Transcriber whose pending stream should be processed.
            slot: Bound consumer identity orchestrating message safety.
            client: Redis client used for stream operations. Borrowed when supplied; otherwise owned by this worker.
            settings: Supplied snapshot, or invocation-time environment defaults.
            runtime: Borrowed runtime supplying resources and its snapshot.
        """
        super().__init__(client, stream_name=get_stream_name(transcriber), slot=slot, settings=settings, runtime=runtime)
        self.transcriber = transcriber

    def process_task(self, task: Task) -> None:
        """Resolve the valid media file path and dispatch the task for transcription.

        Args:
            task: The transcription task that requires processing.

        Raises:
            ValueError: If the task's source is a URL instead of a valid local filesystem path.
        """
        if is_url(task.source):
            raise ValueError(f"Transcription worker received URL task: {task.source}")
        self.dispatch_task(task, Path(task.source))

    @abstractmethod
    def dispatch_task(self, task: Task, source: Path) -> None:
        """Perform transcriber-specific work for a claimed filesystem media file.

        Args:
            task: Task containing transcriber configuration.
            source: Local filesystem path to the media file.
        """
