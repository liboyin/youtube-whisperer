from pathlib import Path
from types import SimpleNamespace

import pytest
from pathlib_extensions import OverwriteMode

import youtube_whisperer.workers.whisper_worker as testee
from youtube_whisperer.models import Task
from youtube_whisperer.transcriber.rejection_policy import RejectedTranscriptionError
from youtube_whisperer.utils import TranscriberType


@pytest.fixture
def client(mocker):
    """Give each Whisper worker test an isolated Redis double."""
    return mocker.MagicMock(name='redis-client')


@pytest.fixture
def worker(client):
    """Bind the Whisper worker to the test-owned Redis client."""
    instance = testee.WhisperWorker('gpu-0', client=client)
    assert instance.client is client
    return instance


def test_is_gpu_healthy_returns_true_when_nvidia_smi_succeeds(mocker):
    """Test that the GPU health check succeeds when `nvidia-smi` exits cleanly."""
    mocker.patch.object(testee.subprocess, "run", return_value=SimpleNamespace(returncode=0))

    assert testee.is_gpu_healthy() is True


def test_is_gpu_healthy_returns_false_when_subprocess_raises(mocker):
    """Test that the GPU health check fails when `nvidia-smi` cannot be executed."""
    mocker.patch.object(testee.subprocess, "run", side_effect=OSError("missing"))

    assert testee.is_gpu_healthy() is False


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


def test_dispatch_task_for_whisper_transcriber(mocker, worker):
    """Test dispatching to the Whisper transcriber."""
    mock_validate_gpu = mocker.patch.object(testee, 'validate_gpu_health_or_exit')
    mock_transcribe = mocker.patch.object(testee, 'transcribe_file_with_default_model')
    task = Task(source='/path.mp4', transcriber=TranscriberType.WHISPER)
    source_path = Path('/path.mp4')

    worker.dispatch_task(task, source_path)

    mock_validate_gpu.assert_called_once()
    mock_transcribe.assert_called_once_with(source_path, task.language, overwrite=OverwriteMode.NEVER, settings=worker.settings)


def test_dispatch_task_propagates_transcription_failure(mocker, worker):
    """Test that a Whisper transcription failure propagates so the worker loop can dead-letter the task."""
    mocker.patch.object(testee, 'validate_gpu_health_or_exit')
    mocker.patch.object(testee, 'transcribe_file_with_default_model', side_effect=RejectedTranscriptionError('bad output'))
    task = Task(source='/path.mp4', transcriber=TranscriberType.WHISPER)

    with pytest.raises(RejectedTranscriptionError, match='bad output'):
        worker.dispatch_task(task, Path('/path.mp4'))



def test_dispatch_task_rechecks_gpu_for_each_task_using_supplied_snapshot(mocker, client, tmp_path, monkeypatch):
    """Resident model policy does not cache away per-task GPU health checks."""
    snapshot = testee.Settings(whisper_use_cuda=True, whisper_model='owned-model')
    worker = testee.WhisperWorker('owned', client, settings=snapshot)
    probe = mocker.patch.object(testee, 'is_gpu_healthy', side_effect=[True, False])
    use_cuda = mocker.patch.object(testee, 'use_cuda', return_value=True)
    transcribe = mocker.patch.object(testee, 'transcribe_file_with_default_model')
    source = tmp_path / 'owned.wav'
    task = Task(source=str(source))
    monkeypatch.setenv('WHISPER_USE_CUDA', 'false')
    worker.dispatch_task(task, source)
    with pytest.raises(SystemExit) as error:
        worker.dispatch_task(task, source)
    assert error.value.code == 2
    assert probe.call_count == 2
    assert use_cuda.call_count == 2
    use_cuda.assert_called_with(snapshot)
    transcribe.assert_called_once_with(source, task.language, overwrite=OverwriteMode.NEVER, settings=snapshot)
