from pathlib import Path

import pytest
from pathlib_extensions import OverwriteMode

from youtube_whisperer.models import Task
from youtube_whisperer.utils import TranscriberType
import youtube_whisperer.workers.azure_worker as testee


def test_dispatch_task_with_conversion(mocker):
    """Test dispatching to Azure when WAV conversion is needed."""
    mock_save_wav = mocker.patch.object(testee, 'save_as_wav_file', return_value=Path('/path.wav'))
    mock_transcribe = mocker.patch.object(testee, 'transcribe_audio_file')
    task = Task(source='/path.mp4', transcriber=TranscriberType.AZURE)
    source_path = Path('/path.mp4')

    testee.AzureWorker('azure-0').dispatch_task(task, source_path)

    mock_save_wav.assert_called_once_with(source_path, output_file_path=Path('/path.wav'), overwrite=OverwriteMode.NEVER)
    mock_transcribe.assert_called_once_with(Path('/path.wav'), task.language, overwrite=OverwriteMode.NEVER)


def test_dispatch_task_reuses_existing_sidecar_wav(mocker, tmp_path):
    """Test dispatching to Azure reuses an existing sidecar WAV file."""
    source_path = tmp_path / 'path.mp3'
    wav_path = tmp_path / 'path.wav'
    wav_path.write_text('wav')
    mock_save_wav = mocker.patch.object(testee, 'save_as_wav_file')
    mock_transcribe = mocker.patch.object(testee, 'transcribe_audio_file')
    task = Task(source=str(source_path), transcriber=TranscriberType.AZURE)

    testee.AzureWorker('azure-0').dispatch_task(task, source_path)

    mock_save_wav.assert_not_called()
    mock_transcribe.assert_called_once_with(wav_path, task.language, overwrite=OverwriteMode.NEVER)


def test_dispatch_task_without_conversion(mocker):
    """Test dispatching to Azure when the source is already WAV."""
    mock_save_wav = mocker.patch.object(testee, 'save_as_wav_file')
    mock_transcribe = mocker.patch.object(testee, 'transcribe_audio_file')
    task = Task(source='/path.wav', transcriber=TranscriberType.AZURE)
    source_path = Path('/path.wav')

    testee.AzureWorker('azure-0').dispatch_task(task, source_path)

    mock_save_wav.assert_not_called()
    mock_transcribe.assert_called_once_with(source_path, task.language, overwrite=OverwriteMode.NEVER)


def test_dispatch_task_raises_when_wav_conversion_returns_no_path(mocker):
    """Test that Azure dispatch raises if WAV conversion does not produce a file path."""
    mock_save = mocker.patch.object(testee, "save_as_wav_file", return_value=None)
    mock_transcribe = mocker.patch.object(testee, "transcribe_audio_file")
    task = Task(source="/tmp/audio.mp3", language="en", transcriber=TranscriberType.AZURE)

    with pytest.raises(RuntimeError, match="Failed to create WAV file"):
        testee.AzureWorker('azure-0').dispatch_task(task, Path("/tmp/audio.mp3"))

    mock_save.assert_called_once_with(
        Path("/tmp/audio.mp3"),
        output_file_path=Path("/tmp/audio.wav"),
        overwrite=OverwriteMode.NEVER,
    )
    mock_transcribe.assert_not_called()



