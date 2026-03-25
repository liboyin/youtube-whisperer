from pathlib import Path
from types import SimpleNamespace

import pytest
from pathlib_extensions import OverwriteMode

import youtube_whisperer.worker as testee
from youtube_whisperer.fastapi.models import Task
from youtube_whisperer.utils import TranscriberType


def test_is_gpu_healthy_returns_true_when_nvidia_smi_succeeds(mocker):
    mocker.patch.object(testee.subprocess, "run", return_value=SimpleNamespace(returncode=0))

    assert testee.is_gpu_healthy() is True


def test_is_gpu_healthy_returns_false_when_subprocess_raises(mocker):
    mocker.patch.object(testee.subprocess, "run", side_effect=OSError("missing"))

    assert testee.is_gpu_healthy() is False


def test_dispatch_transcription_task_for_azure_returns_early_when_wav_conversion_fails(mocker, capsys):
    mock_save = mocker.patch.object(testee, "save_as_wav_file", return_value=None)
    mock_transcribe = mocker.patch.object(testee, "transcribe_audio_file_fire_and_forget")
    task = Task(source="/tmp/audio.mp3", language="en", transcriber=TranscriberType.AZURE)

    testee.dispatch_transcription_task(task, Path("/tmp/audio.mp3"))

    mock_save.assert_called_once_with(Path("/tmp/audio.mp3"), overwrite=OverwriteMode.NEVER)
    mock_transcribe.assert_not_called()
    assert "Skipping transcription for None as WAV conversion failed" in capsys.readouterr().out


def test_dispatch_transcription_task_rejects_unknown_transcriber():
    task = SimpleNamespace(transcriber="remote", mode="transcribe", language="en")

    with pytest.raises(ValueError, match="Unsupported transcriber type"):
        testee.dispatch_transcription_task(task, Path("/tmp/audio.wav"))


def test_process_queue_deletes_failed_tasks(mocker):
    mock_redis = mocker.MagicMock()
    mocker.patch.object(testee, "REDIS_CLIENT", mock_redis)
    task = Task(source="http://example.com/video", language="en")
    mocker.patch.object(testee, "yield_task", return_value=iter([task]))
    mocker.patch.object(testee, "resolve_waveform_file_path", side_effect=RuntimeError("boom"))
    mock_dispatch = mocker.patch.object(testee, "dispatch_transcription_task")

    testee.process_queue()

    mock_dispatch.assert_not_called()
    mock_redis.lpop.assert_called_once_with("tasks")
