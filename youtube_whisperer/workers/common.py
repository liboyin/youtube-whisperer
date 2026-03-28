import os
from abc import ABC, abstractmethod
from pathlib import Path
import time
from typing import Callable, Generator, cast

from pathlib_extensions import OverwriteMode
from redis import StrictRedis

from youtube_whisperer.downloaders import download_video_and_transcript_with_default_title
from youtube_whisperer.fastapi.models import Task
from youtube_whisperer.queueing import decode_redis_value, get_active_queue_name, get_pending_queue_name, queue_dead_letter
from youtube_whisperer.utils import REDIS_CLIENT, TranscriberType, is_url

TaskDispatcher = Callable[[Task, Path], None]


def yield_task(client: StrictRedis, queue_name: str, poll_interval_seconds: int = 5) -> Generator[Task, None, None]:
    """
    Poll a Redis queue and yield the task currently at its head.

    Args:
        client: Redis client used to inspect the queue.
        queue_name: Redis key for the queue being polled.
        poll_interval_seconds: Number of seconds to wait before checking again when the queue is empty.

    Yields:
        Validated task models in the order they appear at the queue head.
    """
    while True:
        head = cast(list[str | bytes], client.lrange(queue_name, 0, 0))
        if not head:
            time.sleep(poll_interval_seconds)
            continue
        task_payload = head[0]
        print(f"Picked up task from {queue_name}: {decode_redis_value(task_payload)}")
        yield Task.model_validate_json(task_payload)


def yield_active_slot_task(client: StrictRedis, pending_queue_name: str, active_queue_name: str, poll_interval_seconds: int = 5) -> Generator[Task, None, None]:
    """
    Yield the task assigned to an active worker slot, claiming work when needed.

    Args:
        client: Redis client used to inspect and move queue items.
        pending_queue_name: Redis key for the pending queue to claim work from.
        active_queue_name: Redis key for the active-slot queue owned by the worker.
        poll_interval_seconds: Number of seconds to wait before retrying when no work is available.

    Yields:
        Validated task models that are either resumed from the active slot or newly claimed from the pending queue.
    """
    while True:
        active_task = cast(list[str | bytes], client.lrange(active_queue_name, 0, 0))
        if active_task:
            task_payload = active_task[0]
            print(f"Resuming task from {active_queue_name}: {decode_redis_value(task_payload)}")
            yield Task.model_validate_json(task_payload)
            continue
        claimed_task = cast(str | bytes | None, client.lmove(pending_queue_name, active_queue_name, 'LEFT', 'RIGHT'))
        if claimed_task is None:
            time.sleep(poll_interval_seconds)
            continue
        print(f"Claimed task from {pending_queue_name} into {active_queue_name}: {decode_redis_value(claimed_task)}")
        yield Task.model_validate_json(claimed_task)


def resolve_waveform_file_path(task: Task) -> tuple[Path, bool]:
    """
    Resolve a task source into a local media path and transcript state.

    Args:
        task: Task whose source should be resolved to a concrete media file.

    Returns:
        A tuple containing the local media path and a flag indicating whether a transcript already exists.
    """
    source = task.source
    if is_url(source):
        return download_video_and_transcript_with_default_title(source, task.language, overwrite=OverwriteMode.NEVER)
    return Path(source), False


def create_transcription_task(task: Task, source: Path) -> Task:
    """
    Create a follow-up transcription task for a concrete media file.

    Args:
        task: Original task whose transcriber, language, and mode should be preserved.
        source: Concrete local media file path that should be transcribed.

    Returns:
        A new task model pointing at the resolved media file.
    """
    return Task(
        source=str(source),
        transcriber=task.transcriber,
        language=task.language,
        mode=task.mode,
    )


def copy_task_with_source(task: Task, source: str) -> Task:
    """
    Copy a task while replacing only its source.

    Args:
        task: Original task whose non-source fields should be preserved.
        source: Concrete source value to write into the copied task.

    Returns:
        A new task model with the updated source.
    """
    return Task(
        source=source,
        transcriber=task.transcriber,
        language=task.language,
        mode=task.mode,
    )


def resolve_worker_slot(slot: str | None, role_name: str) -> str:
    """
    Resolve the slot name a worker should use for active-queue ownership.

    Args:
        slot: Explicit slot override, if provided.
        role_name: Worker role name used when constructing the fallback slot name.

    Returns:
        The resolved slot name from the explicit value, environment, or role-based default.
    """
    return slot or os.getenv('WORKER_SLOT') or os.getenv('HOSTNAME') or f'{role_name}-0'


class BaseWorker(ABC):
    """Abstract base worker providing a robust task-processing loop."""

    @abstractmethod
    def get_queue_name(self) -> str:
        """Return the active queue name for the worker.

        Returns:
            The Redis key string for the queue this worker consumes.
        """
        pass

    @abstractmethod
    def yield_tasks(self, poll_interval_seconds: int) -> Generator[Task, None, None]:
        """Yield tasks from the worker's queue.

        Args:
            poll_interval_seconds: Number of seconds to wait before checking again when the queue is empty.

        Yields:
            Validated task models in the order they appear at the queue head.
        """
        pass

    @abstractmethod
    def process_task(self, task: Task) -> None:
        """Process a single task.

        Args:
            task: The task to be processed by this worker.
        """
        pass

    def process_queue(self, poll_interval_seconds: int = 5) -> None:
        """Poll the queue indefinitely and process tasks.

        Args:
            poll_interval_seconds: Number of seconds to wait before checking again when the queue is empty.
        """
        queue_name = self.get_queue_name()
        for task in self.yield_tasks(poll_interval_seconds):
            delete_task = False
            try:
                self.process_task(task)
                delete_task = True
            except Exception as e:
                print(f"An error occurred while processing task {task}: {e}")
                queue_dead_letter(REDIS_CLIENT, task, queue_name, str(e))
                delete_task = True
            finally:
                if delete_task:
                    REDIS_CLIENT.lpop(queue_name)
                    print(f"Removed task from {queue_name}: {task}")


class TranscriptionWorker(BaseWorker):
    """Base class for transcriber workers.
    
    Transcription workers consume slot-specific active queues, resolve media
    files to concrete paths, and apply a transcriber-specific implementation
    for subtitle generation.
    """

    def __init__(self, transcriber: TranscriberType, slot: str) -> None:
        """Initialize the transcription worker.

        Args:
            transcriber: Transcriber whose pending and active queues should be
                processed.
            slot: Active-slot identifier owned by the worker process.
        """
        self.transcriber = transcriber
        self.slot = slot
        self.active_queue_name = get_active_queue_name(self.transcriber, slot)
        self.pending_queue_name = get_pending_queue_name(self.transcriber)

    def get_queue_name(self) -> str:
        """Return the active queue name configured for this transcriber slot.

        Returns:
            The Redis key string for the active slot queue.
        """
        return self.active_queue_name

    def yield_tasks(self, poll_interval_seconds: int) -> Generator[Task, None, None]:
        """Yield tasks assigned to the worker's active slot or pending queue.

        Args:
            poll_interval_seconds: Number of seconds to wait before checking again when the queues are empty.

        Yields:
            Tasks claimed into the worker's active slot.
        """
        print(f"{self.transcriber.value.title()} worker started with slot {self.slot}")
        return yield_active_slot_task(REDIS_CLIENT, self.pending_queue_name, self.active_queue_name, poll_interval_seconds)

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


