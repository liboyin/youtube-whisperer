from unittest.mock import call

import pytest

from youtube_whisperer.fastapi.models import DeadLetter, Task, TaskQueues
import youtube_whisperer.queueing as testee
from youtube_whisperer.utils import TranscriberMode, TranscriberType


@pytest.fixture
def mock_redis(mocker):
    return mocker.MagicMock()


def test_decode_redis_value_decodes_bytes():
    """Test that Redis byte payloads are normalized to strings."""
    assert testee.decode_redis_value(b'task') == 'task'
    assert testee.decode_redis_value('task') == 'task'


def test_get_pending_queue_name_returns_queue_for_supported_transcriber():
    """Test that supported transcribers resolve to their pending queue names."""
    assert testee.get_pending_queue_name(TranscriberType.WHISPER) == testee.WHISPER_PENDING_QUEUE
    assert testee.get_pending_queue_name(TranscriberType.AZURE) == testee.AZURE_PENDING_QUEUE

    with pytest.raises(ValueError, match='Unsupported transcriber type'):
        testee.get_pending_queue_name('remote')


def test_get_active_queue_prefix_returns_prefix_for_supported_transcriber():
    """Test that supported transcribers resolve to their active queue prefixes."""
    assert testee.get_active_queue_prefix(TranscriberType.WHISPER) == testee.WHISPER_ACTIVE_QUEUE_PREFIX
    assert testee.get_active_queue_prefix(TranscriberType.AZURE) == testee.AZURE_ACTIVE_QUEUE_PREFIX

    with pytest.raises(ValueError, match='Unsupported transcriber type'):
        testee.get_active_queue_prefix('remote')


def test_get_active_queue_name_appends_slot():
    """Test that active queue names include the requested worker slot."""
    assert testee.get_active_queue_name(TranscriberType.WHISPER, 'gpu-0') == 'tasks:whisper:active:gpu-0'


def test_list_queue_tasks_deserializes_tasks(mock_redis):
    """Test that queued task payloads are deserialized into task models."""
    task = Task(source='/tmp/audio.wav', language='en')
    mock_redis.lrange.return_value = [task.model_dump_json().encode('utf-8')]

    result = testee.list_queue_tasks(mock_redis, testee.WHISPER_PENDING_QUEUE)

    assert result == [task]
    mock_redis.lrange.assert_called_once_with(testee.WHISPER_PENDING_QUEUE, 0, -1)


def test_list_dead_letters_deserializes_entries(mock_redis):
    """Test that dead-letter payloads are deserialized into dead-letter models."""
    dead_letter = DeadLetter(task=Task(source='/tmp/audio.wav', language='en'), queue='tasks:whisper:active:gpu-0', error='boom')
    mock_redis.lrange.return_value = [dead_letter.model_dump_json().encode('utf-8')]

    result = testee.list_dead_letters(mock_redis)

    assert result == [dead_letter]
    mock_redis.lrange.assert_called_once_with(testee.DEAD_LETTER_QUEUE, 0, -1)


def test_list_active_queue_names_returns_sorted_matches(mock_redis):
    """Test that active queue discovery returns sorted queue names."""
    mock_redis.scan_iter.return_value = iter([b'tasks:whisper:active:gpu-1', b'tasks:whisper:active:gpu-0'])

    result = testee.list_active_queue_names(mock_redis, TranscriberType.WHISPER)

    assert result == ['tasks:whisper:active:gpu-0', 'tasks:whisper:active:gpu-1']
    mock_redis.scan_iter.assert_called_once_with(match='tasks:whisper:active:*')


def test_list_active_tasks_reads_each_active_queue(mocker, mock_redis):
    """Test that active task listing aggregates tasks from every active queue."""
    task_1 = Task(source='/tmp/one.wav', language='en')
    task_2 = Task(source='/tmp/two.wav', language='en', transcriber=TranscriberType.AZURE)
    mocker.patch.object(testee, 'list_active_queue_names', return_value=['tasks:whisper:active:gpu-0', 'tasks:whisper:active:gpu-1'])
    mock_list_queue_tasks = mocker.patch.object(testee, 'list_queue_tasks', side_effect=[[task_1], [task_2]])

    result = testee.list_active_tasks(mock_redis, TranscriberType.WHISPER)

    assert result == [task_1, task_2]
    assert mock_list_queue_tasks.call_args_list == [
        call(mock_redis, 'tasks:whisper:active:gpu-0'),
        call(mock_redis, 'tasks:whisper:active:gpu-1'),
    ]


def test_list_task_queues_returns_queue_snapshot(mocker, mock_redis):
    """Test that queue snapshots group YouTube, Whisper, and Azure tasks separately."""
    youtube_task = Task(source='https://example.com/video', language='en')
    whisper_pending_task = Task(source='/tmp/whisper.wav', language='en')
    whisper_active_task = Task(source='/tmp/whisper-active.wav', language='en')
    azure_pending_task = Task(source='/tmp/azure.wav', language='en', transcriber=TranscriberType.AZURE)
    azure_active_task = Task(
        source='/tmp/azure-active.wav',
        language='en',
        transcriber=TranscriberType.AZURE,
        mode=TranscriberMode.TRANSLATE,
    )
    mocker.patch.object(
        testee,
        'list_queue_tasks',
        side_effect=[
            [youtube_task],
            [whisper_pending_task],
            [azure_pending_task],
        ],
    )
    mocker.patch.object(
        testee,
        'list_active_tasks',
        side_effect=[
            [whisper_active_task],
            [azure_active_task],
        ],
    )

    result = testee.list_task_queues(mock_redis)

    assert result == TaskQueues(
        youtube=[youtube_task],
        whisper_pending=[whisper_pending_task],
        whisper_active=[whisper_active_task],
        azure_pending=[azure_pending_task],
        azure_active=[azure_active_task],
    )


def test_queue_task_pushes_json_payload(mock_redis):
    """Test that queue_task pushes a serialized task into Redis."""
    task = Task(source='/tmp/audio.wav', language='en')

    testee.queue_task(mock_redis, testee.WHISPER_PENDING_QUEUE, task)

    mock_redis.rpush.assert_called_once_with(testee.WHISPER_PENDING_QUEUE, task.model_dump_json())


def test_queue_tasks_groups_payloads_by_pending_queue(mock_redis):
    """Test that queue_tasks batches payloads by each transcriber's pending queue."""
    whisper_task = Task(source='/tmp/whisper.wav', language='en')
    azure_task = Task(source='/tmp/azure.wav', language='en', transcriber=TranscriberType.AZURE)

    testee.queue_tasks(mock_redis, [whisper_task, azure_task])

    assert mock_redis.rpush.call_args_list == [
        call(testee.WHISPER_PENDING_QUEUE, whisper_task.model_dump_json()),
        call(testee.AZURE_PENDING_QUEUE, azure_task.model_dump_json()),
    ]


def test_queue_dead_letter_serializes_entry(mock_redis):
    """Test that queue_dead_letter stores the serialized failure context in Redis."""
    task = Task(source='/tmp/audio.wav', language='en')

    result = testee.queue_dead_letter(mock_redis, task, 'tasks:whisper:active:gpu-0', 'boom')

    assert result == DeadLetter(task=task, queue='tasks:whisper:active:gpu-0', error='boom')
    mock_redis.rpush.assert_called_once_with(testee.DEAD_LETTER_QUEUE, result.model_dump_json())


def test_clear_task_queues_returns_snapshot_and_deletes_known_queues(mocker, mock_redis):
    """Test that clearing queues returns the prior snapshot and deletes known queue keys."""
    snapshot = TaskQueues(youtube=[], whisper_pending=[], whisper_active=[], azure_pending=[], azure_active=[])
    mocker.patch.object(testee, 'list_task_queues', return_value=snapshot)
    mocker.patch.object(testee, 'list_active_queue_names', side_effect=[['tasks:whisper:active:gpu-0'], ['tasks:azure:active:slot-0']])

    result = testee.clear_task_queues(mock_redis)

    assert result == snapshot
    mock_redis.delete.assert_called_once_with(
        testee.YOUTUBE_QUEUE,
        testee.WHISPER_PENDING_QUEUE,
        testee.AZURE_PENDING_QUEUE,
        'tasks:whisper:active:gpu-0',
        'tasks:azure:active:slot-0',
    )
