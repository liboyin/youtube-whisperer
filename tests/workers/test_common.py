import json
from pathlib import Path

import pytest
import redis

from youtube_whisperer.adaptors.lang_code_adaptor import LanguageCode
from youtube_whisperer.fastapi.models import Task
from youtube_whisperer.utils import TranscriberMode, TranscriberType
import youtube_whisperer.workers.common as testee


@pytest.fixture
def mock_redis(mocker):
    """Fixture providing a mock Redis client to inject into workers and queue helpers."""
    return mocker.MagicMock()


def test_yield_task(mock_redis, mocker):
    """Test the streaming task generator connects properly and resolves messages natively."""
    task_dict = {'source': 'http://example.com', 'language': 'en'}
    task_json = json.dumps(task_dict).encode('utf-8')
    expected_task = Task(
        source=task_dict['source'],
        language=LanguageCode(task_dict['language']),
        transcriber=TranscriberType.WHISPER,
        mode=TranscriberMode.TRANSCRIBE,
    )
    mocker.patch('time.sleep')

    # > new message scrape yields task.
    mock_redis.xreadgroup.side_effect = [
        [], # 0-0 call: empty PEL
        [[b'stream:name', [[b'1234-0', {b'payload': task_json}]]]], # > call: new msg
        Exception("Test exception"), # next loop
    ]

    task_generator = testee.yield_task(mock_redis, 'stream:name', 'group_name', 'consumer', poll_interval_seconds=1)

    msg_id, task = next(task_generator)
    assert msg_id == b'1234-0'
    assert task == expected_task

    with pytest.raises(Exception):
        next(task_generator)

    assert mock_redis.xreadgroup.call_args_list == [
        mocker.call('group_name', 'consumer', {'stream:name': '0-0'}, count=1),
        mocker.call('group_name', 'consumer', {'stream:name': '>'}, count=1, block=1000),
        mocker.call('group_name', 'consumer', {'stream:name': '0-0'}, count=1),
    ]


def test_yield_task_recovers_orphaned_tasks(mock_redis, mocker):
    """Test that yield_task recovers messages stuck inside PEL before fetching newly queued assignments."""
    task_json = Task(source='/tmp/audio.wav', language='en').model_dump_json().encode('utf-8')

    # Return orphaned task on 0-0
    mock_redis.xreadgroup.side_effect = [
        [[b'stream:name', [[b'9999-0', {b'payload': task_json}]]]], # 0-0 call finds orphaned msg
    ]

    task_generator = testee.yield_task(mock_redis, 'stream:name', 'group_name', 'consumer')
    msg_id, task = next(task_generator)

    assert msg_id == b'9999-0'
    assert task == Task(source='/tmp/audio.wav', language='en')
    mock_redis.xreadgroup.assert_called_once_with('group_name', 'consumer', {'stream:name': '0-0'}, count=1)


def test_yield_task_self_heals_after_nogroup_on_pel_read(mock_redis, mocker):
    """Test that a NOGROUP error on the PEL read path triggers consumer group recreation."""
    task_json = Task(source='/tmp/audio.wav', language='en').model_dump_json().encode('utf-8')
    mock_ensure = mocker.patch.object(testee, 'ensure_consumer_group')

    mock_redis.xreadgroup.side_effect = [
        redis.exceptions.ResponseError("NOGROUP No such key 'stream:name'"),   # 0-0: group gone
        [],                                                                      # 0-0: empty PEL after heal
        [[b'stream:name', [[b'5555-0', {b'payload': task_json}]]]],             # >: new msg
    ]

    gen = testee.yield_task(mock_redis, 'stream:name', 'grp', 'c1', poll_interval_seconds=1)
    msg_id, task = next(gen)

    assert msg_id == b'5555-0'
    assert task.source == '/tmp/audio.wav'
    assert mock_ensure.call_count == 2  # once at startup + once after NOGROUP


def test_yield_task_raises_non_nogroup_errors(mock_redis, mocker):
    """Test that non-NOGROUP ResponseErrors are propagated instead of swallowed."""
    mocker.patch.object(testee, 'ensure_consumer_group')

    mock_redis.xreadgroup.side_effect = redis.exceptions.ResponseError("WRONGTYPE unexpected")

    gen = testee.yield_task(mock_redis, 'stream:name', 'grp', 'c1')
    with pytest.raises(redis.exceptions.ResponseError, match="WRONGTYPE"):
        next(gen)


def test_model_copy_preserves_non_source_fields():
    """Test copying a task while only replacing its source."""
    task = Task(
        source='https://example.com/playlist',
        language='en',
        transcriber=TranscriberType.AZURE,
        mode=TranscriberMode.TRANSLATE,
    )
    result = task.model_copy(update={'source': 'https://example.com/video'})
    assert result == Task(
        source='https://example.com/video',
        language='en',
        transcriber=TranscriberType.AZURE,
        mode=TranscriberMode.TRANSLATE,
    )


class MockWorker(testee.TranscriptionWorker):
    def dispatch_task(self, task: Task, source: Path) -> None:
        pass


def test_process_active_slot_queue_full_flow(mocker, mock_redis):
    """Test successful end-to-end processing guarantees message acknowledging and deletion."""
    task = Task(source='/tmp/audio.wav', language='en', transcriber=TranscriberType.WHISPER)
    mocker.patch.object(testee.TranscriptionWorker, 'yield_tasks', return_value=iter([(b'000-1', task)]))
    mocker.patch.object(testee, 'is_url', return_value=False)
    worker = MockWorker(TranscriberType.WHISPER, 'gpu-0', client=mock_redis)
    dispatch_task = mocker.patch.object(worker, 'dispatch_task')
    mock_dead_letter = mocker.patch.object(testee, 'queue_dead_letter')

    worker.process_queue()

    dispatch_task.assert_called_once_with(task, Path('/tmp/audio.wav'))
    mock_dead_letter.assert_not_called()
    mock_pipe = mock_redis.pipeline.return_value
    mock_pipe.xack.assert_called_once_with(testee.get_stream_name(TranscriberType.WHISPER), testee.WORKERS_GROUP, b'000-1')
    mock_pipe.xdel.assert_called_once_with(testee.get_stream_name(TranscriberType.WHISPER), b'000-1')
    mock_pipe.execute.assert_called_once()


def test_process_active_slot_queue_dead_letters_failures(mocker, mock_redis):
    """Test that transcription failures fall strictly to dead lettering but still invoke xack logic safely."""
    task = Task(source='/tmp/audio.wav', language='en', transcriber=TranscriberType.WHISPER)
    mocker.patch.object(testee.TranscriptionWorker, 'yield_tasks', return_value=iter([(b'999-8', task)]))
    mocker.patch.object(testee, 'is_url', return_value=False)
    worker = MockWorker(TranscriberType.WHISPER, 'gpu-0', client=mock_redis)
    dispatch_task = mocker.patch.object(worker, 'dispatch_task', side_effect=RuntimeError('boom'))
    mock_dead_letter = mocker.patch.object(testee, 'queue_dead_letter')

    worker.process_queue()

    dispatch_task.assert_called_once_with(task, Path('/tmp/audio.wav'))
    mock_dead_letter.assert_called_once_with(
        mock_redis,
        task,
        testee.get_stream_name(TranscriberType.WHISPER),
        'boom',
    )
    mock_pipe = mock_redis.pipeline.return_value
    mock_pipe.xack.assert_called_once_with(testee.get_stream_name(TranscriberType.WHISPER), testee.WORKERS_GROUP, b'999-8')
    mock_pipe.execute.assert_called_once()


def test_process_active_slot_queue_dead_letters_url_tasks(mocker, mock_redis):
    """Test that unexpected URL tasks identically invoke safe xack pipeline behavior to discard format mismatches."""
    task = Task(source='https://example.com/video', language='en', transcriber=TranscriberType.WHISPER)
    mocker.patch.object(testee.TranscriptionWorker, 'yield_tasks', return_value=iter([(b'123-1', task)]))
    mocker.patch.object(testee, 'is_url', return_value=True)
    worker = MockWorker(TranscriberType.WHISPER, 'gpu-0', client=mock_redis)
    dispatch_task = mocker.patch.object(worker, 'dispatch_task')
    mock_dead_letter = mocker.patch.object(testee, 'queue_dead_letter')

    worker.process_queue()

    dispatch_task.assert_not_called()
    mock_dead_letter.assert_called_once_with(
        mock_redis,
        task,
        testee.get_stream_name(TranscriberType.WHISPER),
        f"Transcription worker received URL task: {task.source}",
    )
    mock_pipe = mock_redis.pipeline.return_value
    mock_pipe.xack.assert_called_once_with(testee.get_stream_name(TranscriberType.WHISPER), testee.WORKERS_GROUP, b'123-1')
    mock_pipe.xdel.assert_called_once_with(testee.get_stream_name(TranscriberType.WHISPER), b'123-1')
    mock_pipe.execute.assert_called_once()


def test_process_queue_leaves_task_pending_on_base_exception(mocker, mock_redis):
    """Test that a BaseException mid-task leaves the message un-acked so a restart can recover it."""
    task = Task(source='/tmp/audio.wav', language='en', transcriber=TranscriberType.WHISPER)
    mocker.patch.object(testee.TranscriptionWorker, 'yield_tasks', return_value=iter([(b'777-7', task)]))
    mocker.patch.object(testee, 'is_url', return_value=False)
    worker = MockWorker(TranscriberType.WHISPER, 'gpu-0', client=mock_redis)
    mocker.patch.object(worker, 'dispatch_task', side_effect=KeyboardInterrupt)
    mock_dead_letter = mocker.patch.object(testee, 'queue_dead_letter')

    with pytest.raises(KeyboardInterrupt):
        worker.process_queue()

    mock_dead_letter.assert_not_called()
    mock_redis.pipeline.assert_not_called()


def test_process_queue_leaves_task_pending_when_dead_letter_fails(mocker, mock_redis):
    """Test that a failed dead-letter write leaves the message un-acked instead of dropping it."""
    task = Task(source='/tmp/audio.wav', language='en', transcriber=TranscriberType.WHISPER)
    mocker.patch.object(testee.TranscriptionWorker, 'yield_tasks', return_value=iter([(b'888-8', task)]))
    mocker.patch.object(testee, 'is_url', return_value=False)
    worker = MockWorker(TranscriberType.WHISPER, 'gpu-0', client=mock_redis)
    mocker.patch.object(worker, 'dispatch_task', side_effect=RuntimeError('boom'))
    mocker.patch.object(testee, 'queue_dead_letter', side_effect=RuntimeError('redis down'))

    with pytest.raises(RuntimeError, match='redis down'):
        worker.process_queue()

    mock_redis.pipeline.assert_not_called()
