import json
from pathlib import Path

import pytest
from pathlib_extensions import OverwriteMode

from youtube_whisperer.adaptors.lang_code_adaptor import LanguageCode
import youtube_whisperer.worker as testee
from youtube_whisperer.fastapi.models import Task
from youtube_whisperer.utils import TranscriberMode, TranscriberType


@pytest.fixture
def mock_redis(mocker):
    """Fixture to mock the Redis client and connection context manager."""
    mock_redis_client = mocker.MagicMock()
    mocker.patch.object(testee, 'redis_connection').return_value.__enter__.return_value = mock_redis_client
    return mock_redis_client


def test_yield_task(mock_redis, mocker):
    """Test the task generator for correct yielding, polling, and validation."""
    task_dict = {'source': 'http://example.com', 'language': 'en'}
    task_json = json.dumps(task_dict).encode('utf-8')
    expected_task = Task(
        source=task_dict['source'],
        language=LanguageCode(task_dict['language']),
        transcriber=TranscriberType.LOCAL,
        mode=TranscriberMode.TRANSCRIBE
    )
    mock_sleep = mocker.patch('time.sleep')
    # Simulate Redis returning a task, then nothing, then raising an exception
    mock_redis.lrange.side_effect = [
        [task_json],
        None,
        Exception("Test exception"),
    ]
    task_generator = testee.yield_task(mock_redis, poll_interval_seconds=1)
    # First iteration should yield the task
    yielded_task = next(task_generator)
    assert yielded_task == expected_task
    # Second iteration should sleep, continue, and then raise an exception on the next lrange call
    with pytest.raises(Exception):
        next(task_generator)
    mock_sleep.assert_called_once_with(1)
    assert mock_redis.lrange.call_count == 3


def test_validate_gpu_health_or_exit_healthy(mocker):
    """Test that sys.exit is not called when the GPU is healthy."""
    mocker.patch.object(testee, 'use_cuda', return_value=True)
    mocker.patch.object(testee, 'is_gpu_healthy', return_value=True)
    mock_exit = mocker.patch('sys.exit')
    testee.validate_gpu_health_or_exit()
    mock_exit.assert_not_called()


def test_validate_gpu_health_or_exit_unhealthy(mocker):
    """Test that sys.exit is called when the GPU is unhealthy."""
    mocker.patch.object(testee, 'use_cuda', return_value=True)
    mocker.patch.object(testee, 'is_gpu_healthy', return_value=False)
    mock_exit = mocker.patch('sys.exit')
    testee.validate_gpu_health_or_exit()
    mock_exit.assert_called_once_with(2)


def test_validate_gpu_health_or_exit_no_cuda(mocker):
    """Test that is_gpu_healthy and sys.exit are not called when CUDA is not used."""
    mocker.patch.object(testee, 'use_cuda', return_value=False)
    mock_is_gpu_healthy = mocker.patch.object(testee, 'is_gpu_healthy')
    mock_exit = mocker.patch('sys.exit')
    testee.validate_gpu_health_or_exit()
    mock_is_gpu_healthy.assert_not_called()
    mock_exit.assert_not_called()


def test_resolve_waveform_file_path_for_url(mocker):
    """Test resolving a task source from a URL."""
    mock_is_url = mocker.patch.object(testee, 'is_url', return_value=True)
    mock_download = mocker.patch.object(testee, 'download_video_and_transcript_with_default_title', return_value=(Path('/path/to/video.mp4'), False))
    task = Task(source='http://example.com', language='en')
    path, transcript_found = testee.resolve_waveform_file_path(task)
    mock_is_url.assert_called_once_with(task.source)
    mock_download.assert_called_once_with(task.source, task.language, overwrite=OverwriteMode.NEVER)
    assert path == Path('/path/to/video.mp4')
    assert not transcript_found


def test_resolve_waveform_file_path_for_local_file(mocker):
    """Test resolving a task source from a local file path."""
    mock_is_url = mocker.patch.object(testee, 'is_url', return_value=False)
    mock_download = mocker.patch.object(testee, 'download_video_and_transcript_with_default_title')
    task = Task(source='/local/path.mp4', language='en')
    path, transcript_found = testee.resolve_waveform_file_path(task)
    mock_is_url.assert_called_once_with(task.source)
    mock_download.assert_not_called()
    assert path == Path('/local/path.mp4')
    assert not transcript_found


def test_dispatch_transcription_task_for_local_transcriber(mocker):
    """Test dispatching to the local Whisper transcriber."""
    mock_validate_gpu = mocker.patch.object(testee, 'validate_gpu_health_or_exit')
    mock_transcribe = mocker.patch.object(testee, 'transcribe_to_srt_files')
    task = Task(source='/path.mp4', transcriber=TranscriberType.LOCAL, mode=TranscriberMode.TRANSCRIBE)
    source_path = Path('/path.mp4')
    testee.dispatch_transcription_task(task, source_path)
    mock_validate_gpu.assert_called_once()
    mock_transcribe.assert_called_once_with([source_path], task.language, mode=task.mode, overwrite=OverwriteMode.NEVER)


def test_dispatch_transcription_task_for_azure_transcriber_with_conversion(mocker):
    """Test dispatching to the Azure transcriber when WAV conversion is needed."""
    mock_validate_gpu = mocker.patch.object(testee, 'validate_gpu_health_or_exit')
    mock_save_wav = mocker.patch.object(testee, 'save_as_wav_file', return_value=Path('/path.wav'))
    mock_transcribe_azure = mocker.patch.object(testee, 'transcribe_audio_file')
    task = Task(source='/path.mp4', transcriber=TranscriberType.AZURE)
    source_path = Path('/path.mp4')
    testee.dispatch_transcription_task(task, source_path)
    mock_validate_gpu.assert_not_called()  # No GPU validation for Azure transcriber
    mock_save_wav.assert_called_once_with(source_path, overwrite=OverwriteMode.NEVER)
    mock_transcribe_azure.assert_called_once_with(Path('/path.wav'), task.language, overwrite=OverwriteMode.NEVER)


def test_dispatch_transcription_task_for_azure_transcriber_no_conversion(mocker):
    """Test dispatching to the Azure transcriber when no WAV conversion is needed."""
    mock_validate_gpu = mocker.patch.object(testee, 'validate_gpu_health_or_exit')
    mock_save_wav = mocker.patch.object(testee, 'save_as_wav_file')
    mock_transcribe_azure = mocker.patch.object(testee, 'transcribe_audio_file')
    task = Task(source='/path.wav', transcriber=TranscriberType.AZURE)
    source_path = Path('/path.wav')
    testee.dispatch_transcription_task(task, source_path)
    mock_validate_gpu.assert_not_called()  # No GPU validation for Azure transcriber
    mock_save_wav.assert_not_called()
    mock_transcribe_azure.assert_called_once_with(source_path, task.language, overwrite=OverwriteMode.NEVER)


def test_process_queue_full_flow(mocker, mock_redis):
    """Test the integration of functions within process_queue for a successful transcription."""
    mock_yield_task = mocker.patch.object(testee, 'yield_task')
    mock_resolve_path = mocker.patch.object(testee, 'resolve_waveform_file_path')
    mock_dispatch = mocker.patch.object(testee, 'dispatch_transcription_task')
    task = Task(source='http://example.com', language='en')
    waveform_path = Path('/path/to/video.mp4')
    mock_yield_task.return_value = iter([task])  # Yield one task and stop
    mock_resolve_path.return_value = (waveform_path, False)  # Simulate no existing transcript
    testee.process_queue()
    mock_resolve_path.assert_called_once_with(task)
    mock_dispatch.assert_called_once_with(task, waveform_path)
    mock_redis.lpop.assert_called_once_with('tasks')


def test_process_queue_skips_transcription_if_transcript_ready(mocker, mock_redis):
    """Test that transcription is skipped if a transcript is already available."""
    mock_yield_task = mocker.patch.object(testee, 'yield_task')
    mock_resolve_path = mocker.patch.object(testee, 'resolve_waveform_file_path')
    mock_dispatch = mocker.patch.object(testee, 'dispatch_transcription_task')
    task = Task(source='http://example.com', language='en')
    waveform_path = Path('/path/to/video.mp4')
    mock_yield_task.return_value = iter([task])
    mock_resolve_path.return_value = (waveform_path, True)  # Simulate transcript exists
    testee.process_queue()
    mock_resolve_path.assert_called_once_with(task)
    mock_dispatch.assert_not_called()  # The key assertion
    mock_redis.lpop.assert_called_once_with('tasks')
