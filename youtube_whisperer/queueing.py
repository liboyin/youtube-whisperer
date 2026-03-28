from typing import cast

from redis import StrictRedis

from youtube_whisperer.fastapi.models import DeadLetter, Task, TaskQueues
from youtube_whisperer.utils import TranscriberType

YOUTUBE_QUEUE = 'tasks:youtube'
WHISPER_PENDING_QUEUE = 'tasks:whisper:pending'
AZURE_PENDING_QUEUE = 'tasks:azure:pending'
DEAD_LETTER_QUEUE = 'tasks:dead-letter'
WHISPER_ACTIVE_QUEUE_PREFIX = 'tasks:whisper:active:'
AZURE_ACTIVE_QUEUE_PREFIX = 'tasks:azure:active:'


def decode_redis_value(value: str | bytes) -> str:
    """
    Convert a Redis string payload into a normalized Python string.

    Args:
        value: Redis payload returned as either `str` or `bytes`.

    Returns:
        A UTF-8 decoded Python string suitable for JSON validation and logging.
    """
    if isinstance(value, bytes):
        return value.decode('utf-8')
    return value


def get_pending_queue_name(transcriber: TranscriberType) -> str:
    """
    Resolve the pending queue name for a transcriber type.

    Args:
        transcriber: Transcriber whose pending queue is being requested.

    Returns:
        The Redis queue name that stores pending tasks for the transcriber.

    Raises:
        ValueError: If the transcriber type is not supported.
    """
    match transcriber:
        case TranscriberType.WHISPER:
            return WHISPER_PENDING_QUEUE
        case TranscriberType.AZURE:
            return AZURE_PENDING_QUEUE
        case _:
            raise ValueError(f'Unsupported transcriber type: {transcriber}')


def get_active_queue_prefix(transcriber: TranscriberType) -> str:
    """
    Resolve the active-slot queue prefix for a transcriber type.

    Args:
        transcriber: Transcriber whose active queue prefix is being requested.

    Returns:
        The Redis key prefix used for active-slot queues for the transcriber.

    Raises:
        ValueError: If the transcriber type is not supported.
    """
    match transcriber:
        case TranscriberType.WHISPER:
            return WHISPER_ACTIVE_QUEUE_PREFIX
        case TranscriberType.AZURE:
            return AZURE_ACTIVE_QUEUE_PREFIX
        case _:
            raise ValueError(f'Unsupported transcriber type: {transcriber}')


def get_active_queue_name(transcriber: TranscriberType, slot: str) -> str:
    """
    Build the Redis queue name for a specific active worker slot.

    Args:
        transcriber: Transcriber whose active-slot queue is being named.
        slot: Slot identifier for the worker process claiming the task.

    Returns:
        The fully qualified Redis queue name for the active slot.
    """
    return f'{get_active_queue_prefix(transcriber)}{slot}'


def list_queue_tasks(redis_client: StrictRedis, queue_name: str) -> list[Task]:
    """
    Load and deserialize every task stored in a Redis queue.

    Args:
        redis_client: Redis client used to read the queue contents.
        queue_name: Redis key for the queue being inspected.

    Returns:
        A list of validated task models in queue order.
    """
    items = cast(list[str | bytes], redis_client.lrange(queue_name, 0, -1))
    return [Task.model_validate_json(decode_redis_value(task)) for task in items]


def list_dead_letters(redis_client: StrictRedis) -> list[DeadLetter]:
    """
    Load and deserialize every entry in the dead-letter queue.

    Args:
        redis_client: Redis client used to read dead-letter entries.

    Returns:
        A list of validated dead-letter models in queue order.
    """
    items = cast(list[str | bytes], redis_client.lrange(DEAD_LETTER_QUEUE, 0, -1))
    return [DeadLetter.model_validate_json(decode_redis_value(item)) for item in items]


def list_active_queue_names(redis_client: StrictRedis, transcriber: TranscriberType) -> list[str]:
    """
    Discover active-slot queue keys for a transcriber.

    Args:
        redis_client: Redis client used to scan queue keys.
        transcriber: Transcriber whose active-slot queues should be listed.

    Returns:
        Sorted Redis key names for all matching active-slot queues.
    """
    prefix = get_active_queue_prefix(transcriber)
    keys = cast(list[str | bytes], list(redis_client.scan_iter(match=f'{prefix}*')))
    return sorted(decode_redis_value(key) for key in keys)


def list_active_tasks(redis_client: StrictRedis, transcriber: TranscriberType) -> list[Task]:
    """
    Collect tasks from all active-slot queues for a transcriber.

    Args:
        redis_client: Redis client used to read the active queues.
        transcriber: Transcriber whose active tasks should be collected.

    Returns:
        A flattened list of tasks currently assigned to active slots.
    """
    tasks: list[Task] = []
    for queue_name in list_active_queue_names(redis_client, transcriber):
        tasks.extend(list_queue_tasks(redis_client, queue_name))
    return tasks


def list_task_queues(redis_client: StrictRedis) -> TaskQueues:
    """
    Build a snapshot of all user-visible task queues.

    Args:
        redis_client: Redis client used to inspect queue contents.

    Returns:
        A grouped task snapshot containing YouTube, Whisper, and Azure queues.
    """
    return TaskQueues(
        youtube=list_queue_tasks(redis_client, YOUTUBE_QUEUE),
        whisper_pending=list_queue_tasks(redis_client, WHISPER_PENDING_QUEUE),
        whisper_active=list_active_tasks(redis_client, TranscriberType.WHISPER),
        azure_pending=list_queue_tasks(redis_client, AZURE_PENDING_QUEUE),
        azure_active=list_active_tasks(redis_client, TranscriberType.AZURE),
    )


def queue_task(redis_client: StrictRedis, queue_name: str, task: Task) -> None:
    """
    Append a single serialized task to a Redis queue.

    Args:
        redis_client: Redis client used to push the task.
        queue_name: Redis key for the destination queue.
        task: Task model to serialize and enqueue.

    Returns:
        None.
    """
    redis_client.rpush(queue_name, task.model_dump_json())


def queue_tasks(redis_client: StrictRedis, tasks: list[Task]) -> None:
    """
    Append tasks to their transcriber-specific pending queues.

    Args:
        redis_client: Redis client used to push the tasks.
        tasks: Task models to group by transcriber and enqueue.

    Returns:
        None.
    """
    payloads_by_queue: dict[str, list[str]] = {}
    for task in tasks:
        queue_name = get_pending_queue_name(task.transcriber)
        payloads_by_queue.setdefault(queue_name, []).append(task.model_dump_json())
    for queue_name, payloads in payloads_by_queue.items():
        redis_client.rpush(queue_name, *payloads)


def queue_dead_letter(redis_client: StrictRedis, task: Task, queue_name: str, error_message: str) -> DeadLetter:
    """
    Record a failed task in the dead-letter queue.

    Args:
        redis_client: Redis client used to persist the dead-letter entry.
        task: Task that failed processing.
        queue_name: Queue where the failure happened.
        error_message: Error message describing the failure.

    Returns:
        The dead-letter model that was serialized and pushed to Redis.
    """
    dead_letter = DeadLetter(task=task, queue=queue_name, error=error_message)
    redis_client.rpush(DEAD_LETTER_QUEUE, dead_letter.model_dump_json())
    return dead_letter


def clear_task_queues(redis_client: StrictRedis) -> TaskQueues:
    """
    Delete all pending and active task queues after snapshotting them.

    Args:
        redis_client: Redis client used to inspect and delete queue keys.

    Returns:
        A snapshot of the tasks that were present before deletion.
    """
    tasks = list_task_queues(redis_client)
    queue_names = [
        YOUTUBE_QUEUE,
        WHISPER_PENDING_QUEUE,
        AZURE_PENDING_QUEUE,
        *list_active_queue_names(redis_client, TranscriberType.WHISPER),
        *list_active_queue_names(redis_client, TranscriberType.AZURE),
    ]
    if queue_names:
        redis_client.delete(*queue_names)
    return tasks
