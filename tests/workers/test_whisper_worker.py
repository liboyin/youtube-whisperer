from pathlib import Path
from types import SimpleNamespace

from pathlib_extensions import OverwriteMode
import pytest

from youtube_whisperer.models import Task
from youtube_whisperer.transcriber.rejection_policy import RejectedTranscriptionError
from youtube_whisperer.utils import TranscriberMode, TranscriberType
import youtube_whisperer.workers.whisper_worker as testee


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


def test_dispatch_task_for_whisper_transcriber(mocker):
    """Test dispatching to the Whisper transcriber."""
    mock_validate_gpu = mocker.patch.object(testee, 'validate_gpu_health_or_exit')
    mock_transcribe = mocker.patch.object(testee, 'transcribe_file_with_default_model')
    task = Task(source='/path.mp4', transcriber=TranscriberType.WHISPER, mode=TranscriberMode.TRANSCRIBE)
    source_path = Path('/path.mp4')

    testee.WhisperWorker('gpu-0').dispatch_task(task, source_path)

    mock_validate_gpu.assert_called_once()
    mock_transcribe.assert_called_once_with(source_path, task.language, mode=task.mode, overwrite=OverwriteMode.NEVER)


def test_dispatch_task_propagates_transcription_failure(mocker):
    """Test that a Whisper transcription failure propagates so the worker loop can dead-letter the task."""
    mocker.patch.object(testee, 'validate_gpu_health_or_exit')
    mocker.patch.object(testee, 'transcribe_file_with_default_model', side_effect=RejectedTranscriptionError('bad output'))
    task = Task(source='/path.mp4', transcriber=TranscriberType.WHISPER)

    with pytest.raises(RejectedTranscriptionError, match='bad output'):
        testee.WhisperWorker('gpu-0').dispatch_task(task, Path('/path.mp4'))



