import redis
from typing import cast
from redis import StrictRedis

from youtube_whisperer.fastapi.models import DeadLetter, Task, TaskQueues
from youtube_whisperer.utils import TranscriberType

YOUTUBE_STREAM = 'stream:youtube'
WHISPER_STREAM = 'stream:whisper'
AZURE_STREAM = 'stream:azure'
DEAD_LETTER_QUEUE = 'tasks:dead-letter'
WORKERS_GROUP = 'workers'


def decode_redis_value(value: str | bytes) -> str:
    """
    Convert a Redis string payload into a normalized Python string.
    """
    if isinstance(value, bytes):
        return value.decode('utf-8')
    return value


def get_stream_name(transcriber: TranscriberType) -> str:
    """
    Resolve the stream name for a transcriber type.

    Args:
        transcriber: Transcriber whose stream is being requested.

    Returns:
        The Redis stream name that stores tasks for the transcriber.

    Raises:
        ValueError: If the transcriber type is not supported.
    """
    match transcriber:
        case TranscriberType.WHISPER:
            return WHISPER_STREAM
        case TranscriberType.AZURE:
            return AZURE_STREAM
        case _:
            raise ValueError(f'Unsupported transcriber type: {transcriber}')


def ensure_consumer_group(redis_client: StrictRedis, stream_name: str, group_name: str) -> None:
    """
    Ensure the continuous Stream and Consumer Group topology is instantiated idempotently.
    """
    try:
        redis_client.xgroup_create(stream_name, group_name, mkstream=True)
    except redis.exceptions.ResponseError as e:
        if "BUSYGROUP" not in str(e):
            raise


def list_stream_tasks(redis_client: StrictRedis, stream_name: str, group_name: str) -> tuple[list[Task], list[Task]]:
    """
    Load all tasks currently in the stream and partition them by pending vs active state.
    """
    try:
        all_msgs = cast(list[tuple[bytes, dict[bytes, bytes]]], redis_client.xrange(stream_name))
    except redis.exceptions.ResponseError:
        return [], []
    try:
        pending_info = redis_client.xpending_range(stream_name, group_name, '-', '+', 100000)
        active_ids = {p['message_id'] for p in pending_info}
    except redis.exceptions.ResponseError:
        active_ids = set()
    pending_tasks: list[Task] = []
    active_tasks: list[Task] = []
    for msg_id, fields in all_msgs:
        task = Task.model_validate_json(decode_redis_value(fields[b'payload']))
        if msg_id in active_ids:
            active_tasks.append(task)
        else:
            pending_tasks.append(task)
    return pending_tasks, active_tasks


def list_dead_letters(redis_client: StrictRedis) -> list[DeadLetter]:
    """
    Load and deserialize every entry in the dead-letter queue.
    """
    items = redis_client.lrange(DEAD_LETTER_QUEUE, 0, -1)
    return [DeadLetter.model_validate_json(decode_redis_value(item)) for item in items]


def list_task_queues(redis_client: StrictRedis) -> TaskQueues:
    """
    Build a snapshot of all user-visible task streams.
    This maintains the original TaskQueues API contract by mapping Unclaimed -> Pending, and Claimed (PEL) -> Active.
    """
    yt_pending, yt_active = list_stream_tasks(redis_client, YOUTUBE_STREAM, WORKERS_GROUP)
    wh_pending, wh_active = list_stream_tasks(redis_client, WHISPER_STREAM, WORKERS_GROUP)
    az_pending, az_active = list_stream_tasks(redis_client, AZURE_STREAM, WORKERS_GROUP)
    return TaskQueues(
        youtube=yt_pending + yt_active,
        whisper_pending=wh_pending,
        whisper_active=wh_active,
        azure_pending=az_pending,
        azure_active=az_active,
    )


def queue_youtube_task(redis_client: StrictRedis, task: Task) -> None:
    """
    Append a single serialized YouTube extraction task to its dedicated stream.
    """
    ensure_consumer_group(redis_client, YOUTUBE_STREAM, WORKERS_GROUP)
    redis_client.xadd(YOUTUBE_STREAM, {'payload': task.model_dump_json()})


def queue_transcription_tasks(redis_client: StrictRedis, tasks: list[Task]) -> None:
    """
    Append tasks to their transcriber-specific streams in bulk.
    """
    ensure_consumer_group(redis_client, WHISPER_STREAM, WORKERS_GROUP)
    ensure_consumer_group(redis_client, AZURE_STREAM, WORKERS_GROUP)
    pipeline = redis_client.pipeline()
    for task in tasks:
        stream_name = get_stream_name(task.transcriber)
        pipeline.xadd(stream_name, {'payload': task.model_dump_json()})
    pipeline.execute()


def queue_dead_letter(redis_client: StrictRedis, task: Task, stream_name: str, error_message: str) -> DeadLetter:
    """
    Record a failed task in the dead-letter queue list.
    """
    dead_letter = DeadLetter(task=task, queue=stream_name, error=error_message)
    redis_client.rpush(DEAD_LETTER_QUEUE, dead_letter.model_dump_json())
    return dead_letter


def clear_task_queues(redis_client: StrictRedis) -> TaskQueues:
    """
    Delete all routing streams after snapshotting them.
    """
    tasks = list_task_queues(redis_client)
    redis_client.delete(YOUTUBE_STREAM, WHISPER_STREAM, AZURE_STREAM)
    return tasks
