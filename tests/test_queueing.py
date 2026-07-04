from unittest.mock import call
import redis
import pytest

from youtube_whisperer.models import DeadLetter, Task, TaskQueues
import youtube_whisperer.queueing as testee
from youtube_whisperer.utils import TranscriberType


@pytest.fixture
def mock_redis(mocker):
    return mocker.MagicMock()


def test_decode_redis_value_decodes_bytes():
    """Test that Redis byte payloads are normalized to strings."""
    assert testee.decode_redis_value(b'task') == 'task'
    assert testee.decode_redis_value('task') == 'task'


def test_get_stream_name_returns_queue_for_supported_transcriber():
    """Test that supported transcribers resolve to their stream names."""
    assert testee.get_stream_name(TranscriberType.WHISPER) == testee.WHISPER_STREAM
    assert testee.get_stream_name(TranscriberType.AZURE) == testee.AZURE_STREAM

    with pytest.raises(ValueError, match='Unsupported transcriber type'):
        testee.get_stream_name('remote')


def test_ensure_consumer_group_creates_group(mock_redis):
    """Test that a consumer group is properly created if it didn't exist."""
    testee.ensure_consumer_group(mock_redis, 'stream:name', 'group_name')
    mock_redis.xgroup_create.assert_called_once_with('stream:name', 'group_name', mkstream=True)


def test_ensure_consumer_group_ignores_busygroup(mock_redis):
    """Test that initialization ignores existing active group errors."""
    mock_redis.xgroup_create.side_effect = redis.exceptions.ResponseError("BUSYGROUP")
    testee.ensure_consumer_group(mock_redis, 'stream:name', 'group_name')


def test_ensure_consumer_group_raises_other_errors(mock_redis):
    """Test that missing endpoints or logic errors raise correctly."""
    mock_redis.xgroup_create.side_effect = redis.exceptions.ResponseError("OTHER ERROR")
    with pytest.raises(redis.exceptions.ResponseError):
        testee.ensure_consumer_group(mock_redis, 'stream:name', 'group_name')


def test_list_stream_tasks_separates_pending_and_active(mock_redis):
    """Test that queued tasks map across Unclaimed (Pending) and Claimed (Active) buckets via PEL logic."""
    task1 = Task(source='/tmp/one.wav')
    task2 = Task(source='/tmp/two.wav')

    mock_redis.xrange.return_value = [
        (b'123-0', {b'payload': task1.model_dump_json().encode()}),
        (b'124-0', {b'payload': task2.model_dump_json().encode()}),
    ]

    mock_redis.xpending_range.return_value = [{'message_id': b'123-0'}]

    pending, active = testee.list_stream_tasks(mock_redis, 'stream:name', 'group')
    assert pending == [task2]
    assert active == [task1]


def test_list_dead_letters_deserializes_entries(mock_redis):
    """Test that dead-letter payloads are deserialized into dead-letter models."""
    dead_letter = DeadLetter(task=Task(source='/tmp/audio.wav', language='en'), queue='stream:whisper', error='boom')
    mock_redis.lrange.return_value = [dead_letter.model_dump_json().encode('utf-8')]

    result = testee.list_dead_letters(mock_redis)

    assert result == [dead_letter]
    mock_redis.lrange.assert_called_once_with(testee.DEAD_LETTER_QUEUE, 0, -1)


def test_list_task_queues_returns_queue_snapshot(mocker, mock_redis):
    """Test that streaming snapshot maintains original pending and active routing API interfaces."""
    task1 = Task(source='bar')
    task2 = Task(source='foo')
    mocker.patch.object(testee, 'list_stream_tasks', side_effect=[
        ([task1], [task2]), # YOUTUBE
        ([], [task1]), # WHISPER
        ([task2], []), # AZURE
    ])

    result = testee.list_task_queues(mock_redis)

    assert result.youtube == [task1, task2]
    assert result.whisper_pending == []
    assert result.whisper_active == [task1]
    assert result.azure_pending == [task2]
    assert result.azure_active == []


def test_queue_youtube_task_pushes_json_payload(mocker, mock_redis):
    """Test that queue_youtube_task pushes a serialized task into Redis Native streams."""
    mocker.patch.object(testee, 'ensure_consumer_group')
    task = Task(source='https://youtube.com/watch?v=123', language='en')

    testee.queue_youtube_task(mock_redis, task)

    mock_redis.xadd.assert_called_once_with(testee.YOUTUBE_STREAM, {'payload': task.model_dump_json()})


def test_queue_transcription_tasks_uses_pipeline(mocker, mock_redis):
    """Test that multiqueueing applies pipeline functionality for batch throughput."""
    mock_ensure = mocker.patch.object(testee, 'ensure_consumer_group')
    whisper_task = Task(source='/tmp/whisper.wav', language='en')
    azure_task = Task(source='/tmp/azure.wav', language='en', transcriber=TranscriberType.AZURE)

    testee.queue_transcription_tasks(mock_redis, [whisper_task, azure_task])

    # Both transcriber streams ensured upfront, before the pipeline
    assert mock_ensure.call_count == 2
    mock_ensure.assert_any_call(mock_redis, testee.WHISPER_STREAM, testee.WORKERS_GROUP)
    mock_ensure.assert_any_call(mock_redis, testee.AZURE_STREAM, testee.WORKERS_GROUP)
    mock_pipeline = mock_redis.pipeline.return_value
    assert mock_pipeline.xadd.call_args_list == [
        call(testee.WHISPER_STREAM, {'payload': whisper_task.model_dump_json()}),
        call(testee.AZURE_STREAM, {'payload': azure_task.model_dump_json()}),
    ]
    mock_pipeline.execute.assert_called_once()


def test_queue_dead_letter_serializes_entry(mock_redis):
    """Test that queue_dead_letter stores the serialized failure context in Redis natively."""
    task = Task(source='/tmp/audio.wav', language='en')

    result = testee.queue_dead_letter(mock_redis, task, 'stream:whisper', 'boom')

    assert result == DeadLetter(task=task, queue='stream:whisper', error='boom')
    mock_redis.rpush.assert_called_once_with(testee.DEAD_LETTER_QUEUE, result.model_dump_json())


def test_clear_task_queues_returns_snapshot_and_deletes_known_queues(mocker, mock_redis):
    """Test that clearing queues returns the prior snapshot and strictly truncates streams."""
    snapshot = TaskQueues(youtube=[], whisper_pending=[], whisper_active=[], azure_pending=[], azure_active=[])
    mocker.patch.object(testee, 'list_task_queues', return_value=snapshot)

    result = testee.clear_task_queues(mock_redis)

    assert result == snapshot
    mock_redis.delete.assert_called_once_with(
        testee.YOUTUBE_STREAM, testee.WHISPER_STREAM, testee.AZURE_STREAM
    )
