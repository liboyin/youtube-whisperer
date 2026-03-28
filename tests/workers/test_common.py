import json
import os
from pathlib import Path

import pytest
from pathlib_extensions import OverwriteMode

from youtube_whisperer.adaptors.lang_code_adaptor import LanguageCode
from youtube_whisperer.fastapi.models import Task
from youtube_whisperer.utils import TranscriberMode, TranscriberType
import youtube_whisperer.workers.common as testee


@pytest.fixture
def mock_redis(mocker):
    """Fixture to mock the Redis client and connection context manager."""
    mock_redis_client = mocker.MagicMock()
    mocker.patch.object(testee, 'REDIS_CLIENT', mock_redis_client)
    return mock_redis_client


def test_yield_task(mock_redis, mocker):
    """Test the task generator for correct yielding, polling, and validation."""
    task_dict = {'source': 'http://example.com', 'language': 'en'}
    task_json = json.dumps(task_dict).encode('utf-8')
    expected_task = Task(
        source=task_dict['source'],
        language=LanguageCode(task_dict['language']),
        transcriber=TranscriberType.WHISPER,
        mode=TranscriberMode.TRANSCRIBE,
    )
    mock_sleep = mocker.patch('time.sleep')
    mock_redis.lrange.side_effect = [
        [task_json],
        None,
        Exception("Test exception"),
    ]

    task_generator = testee.yield_task(mock_redis, 'tasks:youtube', poll_interval_seconds=1)

    assert next(task_generator) == expected_task
    with pytest.raises(Exception):
        next(task_generator)
    mock_sleep.assert_called_once_with(1)
    assert mock_redis.lrange.call_args_list == [
        mocker.call('tasks:youtube', 0, 0),
        mocker.call('tasks:youtube', 0, 0),
        mocker.call('tasks:youtube', 0, 0),
    ]


def test_yield_active_slot_task_resumes_existing_task(mock_redis):
    """Test that an active-slot worker resumes the task already assigned to its slot."""
    task_json = Task(source='/tmp/audio.wav', language='en').model_dump_json().encode('utf-8')
    mock_redis.lrange.return_value = [task_json]

    task = next(testee.yield_active_slot_task(mock_redis, 'tasks:whisper:pending', 'tasks:whisper:active:gpu-0'))

    assert task == Task(source='/tmp/audio.wav', language='en')
    mock_redis.lmove.assert_not_called()


def test_yield_active_slot_task_claims_pending_task(mock_redis):
    """Test that an active-slot worker claims a new task when its slot is empty."""
    task_json = Task(source='/tmp/audio.wav', language='en').model_dump_json().encode('utf-8')
    mock_redis.lrange.return_value = []
    mock_redis.lmove.return_value = task_json

    task = next(testee.yield_active_slot_task(mock_redis, 'tasks:whisper:pending', 'tasks:whisper:active:gpu-0'))

    assert task == Task(source='/tmp/audio.wav', language='en')
    mock_redis.lmove.assert_called_once_with('tasks:whisper:pending', 'tasks:whisper:active:gpu-0', 'LEFT', 'RIGHT')


def test_resolve_waveform_file_path_for_url(mocker):
    """Test resolving a task source from a URL."""
    mock_is_url = mocker.patch.object(testee, 'is_url', return_value=True)
    mock_download = mocker.patch.object(
        testee,
        'download_video_and_transcript_with_default_title',
        return_value=(Path('/path/to/video.mp4'), False),
    )
    task = Task(source='http://example.com', language='en')

    path, transcript_found = testee.resolve_waveform_file_path(task)

    mock_is_url.assert_called_once_with(task.source)
    mock_download.assert_called_once_with(task.source, task.language, overwrite=OverwriteMode.NEVER)
    assert path == Path('/path/to/video.mp4')
    assert transcript_found is False


def test_resolve_waveform_file_path_for_filesystem_file(mocker):
    """Test resolving a task source from a filesystem file path."""
    mock_is_url = mocker.patch.object(testee, 'is_url', return_value=False)
    mock_download = mocker.patch.object(testee, 'download_video_and_transcript_with_default_title')
    task = Task(source='/local/path.mp4', language='en')

    path, transcript_found = testee.resolve_waveform_file_path(task)

    mock_is_url.assert_called_once_with(task.source)
    mock_download.assert_not_called()
    assert path == Path('/local/path.mp4')
    assert transcript_found is False


def test_create_transcription_task_preserves_task_metadata():
    """Test that follow-up transcription tasks keep the original task metadata."""
    task = Task(
        source='https://example.com/watch?v=1',
        language='en',
        transcriber=TranscriberType.AZURE,
        mode=TranscriberMode.TRANSLATE,
    )

    result = testee.create_transcription_task(task, Path('/tmp/audio.wav'))

    assert result == Task(
        source='/tmp/audio.wav',
        language='en',
        transcriber=TranscriberType.AZURE,
        mode=TranscriberMode.TRANSLATE,
    )


def test_copy_task_with_source_preserves_non_source_fields():
    """Test copying a task while only replacing its source."""
    task = Task(
        source='https://example.com/playlist',
        language='en',
        transcriber=TranscriberType.AZURE,
        mode=TranscriberMode.TRANSLATE,
    )

    result = testee.copy_task_with_source(task, 'https://example.com/video')

    assert result == Task(
        source='https://example.com/video',
        language='en',
        transcriber=TranscriberType.AZURE,
        mode=TranscriberMode.TRANSLATE,
    )


def test_resolve_worker_slot_prefers_explicit_slot(mocker):
    """Test that an explicit slot overrides environment-derived slot names."""
    mocker.patch.dict(os.environ, {'WORKER_SLOT': 'env-slot', 'HOSTNAME': 'host-slot'})

    assert testee.resolve_worker_slot('explicit-slot', TranscriberType.WHISPER.value) == 'explicit-slot'


def test_resolve_worker_slot_falls_back_to_environment(mocker):
    """Test that the worker slot falls back to `WORKER_SLOT` when not provided explicitly."""
    mocker.patch.dict(os.environ, {'WORKER_SLOT': 'env-slot', 'HOSTNAME': 'host-slot'})

    assert testee.resolve_worker_slot(None, TranscriberType.WHISPER.value) == 'env-slot'


def test_resolve_worker_slot_falls_back_to_hostname_and_role_default(mocker):
    """Test that slot resolution falls back to `HOSTNAME`, then a role-specific default."""
    mocker.patch.dict(os.environ, {'HOSTNAME': 'host-slot'}, clear=True)
    assert testee.resolve_worker_slot(None, TranscriberType.WHISPER.value) == 'host-slot'

    mocker.patch.dict(os.environ, {}, clear=True)
    assert testee.resolve_worker_slot(None, TranscriberType.AZURE.value) == 'azure-0'


def test_process_active_slot_queue_full_flow(mocker, mock_redis):
    """Test successful end-to-end processing of a transcription slot task."""
    task = Task(source='/tmp/audio.wav', language='en', transcriber=TranscriberType.WHISPER)
    mocker.patch.object(testee, 'yield_active_slot_task', return_value=iter([task]))
    mocker.patch.object(testee, 'is_url', return_value=False)
    dispatch_task = mocker.MagicMock()
    mock_dead_letter = mocker.patch.object(testee, 'queue_dead_letter')

    testee.process_active_slot_queue(TranscriberType.WHISPER, 'gpu-0', dispatch_task)

    dispatch_task.assert_called_once_with(task, Path('/tmp/audio.wav'))
    mock_dead_letter.assert_not_called()
    mock_redis.lpop.assert_called_once_with(testee.get_active_queue_name(TranscriberType.WHISPER, 'gpu-0'))


def test_process_active_slot_queue_dead_letters_failures(mocker, mock_redis):
    """Test that transcription failures are moved to the dead-letter queue."""
    task = Task(source='/tmp/audio.wav', language='en', transcriber=TranscriberType.WHISPER)
    mocker.patch.object(testee, 'yield_active_slot_task', return_value=iter([task]))
    mocker.patch.object(testee, 'is_url', return_value=False)
    dispatch_task = mocker.MagicMock(side_effect=RuntimeError('boom'))
    mock_dead_letter = mocker.patch.object(testee, 'queue_dead_letter')

    testee.process_active_slot_queue(TranscriberType.WHISPER, 'gpu-0', dispatch_task)

    dispatch_task.assert_called_once_with(task, Path('/tmp/audio.wav'))
    mock_dead_letter.assert_called_once_with(
        mock_redis,
        task,
        testee.get_active_queue_name(TranscriberType.WHISPER, 'gpu-0'),
        'boom',
    )
    mock_redis.lpop.assert_called_once_with(testee.get_active_queue_name(TranscriberType.WHISPER, 'gpu-0'))


def test_process_active_slot_queue_dead_letters_url_tasks(mocker, mock_redis):
    """Test that unexpected URL tasks are rejected by transcription workers."""
    task = Task(source='https://example.com/video', language='en', transcriber=TranscriberType.WHISPER)
    mocker.patch.object(testee, 'yield_active_slot_task', return_value=iter([task]))
    mocker.patch.object(testee, 'is_url', return_value=True)
    dispatch_task = mocker.MagicMock()
    mock_dead_letter = mocker.patch.object(testee, 'queue_dead_letter')

    testee.process_active_slot_queue(TranscriberType.WHISPER, 'gpu-0', dispatch_task)

    dispatch_task.assert_not_called()
    mock_dead_letter.assert_called_once()
    mock_redis.lpop.assert_called_once_with(testee.get_active_queue_name(TranscriberType.WHISPER, 'gpu-0'))
