from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable, Generator, cast

import redis
from redis import StrictRedis

from youtube_whisperer.fastapi.models import Task
from youtube_whisperer.queueing import decode_redis_value, get_stream_name, queue_dead_letter, WORKERS_GROUP, ensure_consumer_group
from youtube_whisperer.utils import REDIS_CLIENT, TranscriberType, is_url

TaskDispatcher = Callable[[Task, Path], None]
StreamReadResponse = list[tuple[bytes, list[tuple[bytes, dict[bytes, bytes]]]]]


def yield_task(
    client: StrictRedis,
    stream_name: str,
    group_name: str,
    consumer_name: str,
    poll_interval_seconds: int = 5
) -> Generator[tuple[bytes, Task], None, None]:
    """
    Poll a Redis Stream and yield tasks assigned to this consumer group.

    First, it automatically resumes any orphaned tasks assigned to this consumer in the PEL.
    Then, it blocks for new messages to arrive in the stream.

    Args:
        client (StrictRedis): The Redis client to read from.
        stream_name (str): The stream to consume tasks from.
        group_name (str): The consumer group shared by all workers of this type.
        consumer_name (str): This worker's consumer identity, used to recover its own PEL.
        poll_interval_seconds (int): How long each blocking read waits for new messages.

    Yields:
        A tuple of (Message ID bytes, Validated Task model).
    """
    ensure_consumer_group(client, stream_name, group_name)

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
                    task_payload = fields[b'payload']
                    print(f"Resuming orphaned task from {stream_name}: {decode_redis_value(task_payload)}")
                    yield msg_id, Task.model_validate_json(decode_redis_value(task_payload))
                    continue
        except redis.exceptions.ResponseError as e:
            if "NOGROUP" in str(e):
                ensure_consumer_group(client, stream_name, group_name)
                continue
            raise
        try:
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
                    task_payload = fields[b'payload']
                    print(f"Claimed new task from {stream_name}: {decode_redis_value(task_payload)}")
                    yield msg_id, Task.model_validate_json(decode_redis_value(task_payload))
        except redis.exceptions.ResponseError as e:
            if "NOGROUP" in str(e):
                ensure_consumer_group(client, stream_name, group_name)
                continue
            raise


class BaseWorker(ABC):
    """Abstract base worker providing a robust task-processing loop via Redis Streams."""

    def __init__(self, client: StrictRedis = REDIS_CLIENT) -> None:
        """Bind the worker to the Redis client it consumes and acknowledges tasks on.

        Args:
            client: Redis client used for stream reads, acknowledgements, and dead-lettering.
                Defaults to the shared pooled client; tests can inject a substitute.
        """
        self.client = client

    @abstractmethod
    def get_stream_name(self) -> str:
        """Return the active stream name for the worker.

        Returns:
            The Redis key string for the stream this worker consumes.
        """
        pass

    @abstractmethod
    def get_consumer_name(self) -> str:
        """Return the active consumer name assigned to this worker."""
        pass

    def yield_tasks(self, poll_interval_seconds: int) -> Generator[tuple[bytes, Task], None, None]:
        """Yield tasks from the worker's queue.

        Args:
            poll_interval_seconds: Number of seconds to wait before checking again when the queue is empty.

        Yields:
            Validated task models alongside their message sequence IDs.
        """
        stream_name = self.get_stream_name()
        consumer_name = self.get_consumer_name()
        print(f"Worker for {stream_name} started utilizing consumer identity: {consumer_name}")
        return yield_task(
            client=self.client,
            stream_name=stream_name,
            group_name=WORKERS_GROUP,
            consumer_name=consumer_name,
            poll_interval_seconds=poll_interval_seconds
        )

    @abstractmethod
    def process_task(self, task: Task) -> None:
        """Process a single task.

        Args:
            task: The task to be processed by this worker.
        """
        pass

    def process_queue(self, poll_interval_seconds: int = 5) -> None:
        """Poll the queue indefinitely and process tasks.

        A message is acknowledged and deleted only after the task succeeds or is
        durably dead-lettered. If processing is aborted by a BaseException (e.g.
        KeyboardInterrupt) or the dead-letter write itself fails, the acknowledgement
        is skipped so the message stays in the consumer's pending list and a restarted
        worker can recover it via its PEL.

        Args:
            poll_interval_seconds: Number of seconds to wait before checking again when the queue is empty.
        """
        stream_name = self.get_stream_name()
        for msg_id, task in self.yield_tasks(poll_interval_seconds):
            try:
                self.process_task(task)
            except Exception as e:
                print(f"An error occurred while processing task {task}: {e}")
                queue_dead_letter(self.client, task, stream_name, str(e))
            # Reached only on success or after a durable dead-letter; a BaseException
            # or a failed dead-letter skips the acknowledgement and leaves the message
            # pending for recovery.
            pipe = self.client.pipeline()
            pipe.xack(stream_name, WORKERS_GROUP, msg_id)
            pipe.xdel(stream_name, msg_id)
            pipe.execute()
            print(f"Acknowledged and deleted task from {stream_name}: {task}")


class TranscriptionWorker(BaseWorker):
    """Base class for transcriber workers utilizing Native Streams."""

    def __init__(self, transcriber: TranscriberType, slot: str, client: StrictRedis = REDIS_CLIENT) -> None:
        """Initialize the transcription worker.

        Args:
            transcriber: Transcriber whose pending stream should be processed.
            slot: Bound consumer identity orchestrating message safety.
            client: Redis client used for stream operations. Defaults to the shared pooled client.
        """
        super().__init__(client)
        self.transcriber = transcriber
        self.slot = slot
        self.stream_name = get_stream_name(self.transcriber)

    def get_stream_name(self) -> str:
        """Return the active stream name configured for this transcriber.

        Returns:
            The Redis string key for the active stream.
        """
        return self.stream_name

    def get_consumer_name(self) -> str:
        """Return the active consumer name configured for this transcriber."""
        return self.slot

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
        pass
