from pathlib import Path

import pytest
from pathlib_extensions import OverwriteMode

import youtube_whisperer.workers.azure_worker as testee
from youtube_whisperer.models import Task
from youtube_whisperer.utils import TranscriberType


@pytest.fixture
def client(mocker):
    """Give each Azure worker test an isolated Redis double."""
    return mocker.MagicMock(name='redis-client')


@pytest.fixture
def worker(client):
    """Bind the Azure worker to the test-owned Redis client."""
    instance = testee.AzureWorker('azure-0', client=client)
    assert instance.client is client
    return instance


def test_dispatch_task_with_conversion(mocker, tmp_path, owned_path_probes, worker):
    """Test dispatching to Azure when WAV conversion is needed."""
    source_path = tmp_path / 'path.mp4'
    wav_path = tmp_path / 'path.wav'
    mock_save_wav = mocker.patch.object(testee, 'save_as_wav_file', return_value=wav_path)
    mock_transcribe = mocker.patch.object(testee, 'transcribe_audio_file')
    task = Task(source=str(source_path), transcriber=TranscriberType.AZURE)

    with owned_path_probes():
        worker.dispatch_task(task, source_path)

    mock_save_wav.assert_called_once_with(source_path, output_file_path=wav_path, overwrite=OverwriteMode.NEVER)
    mock_transcribe.assert_called_once_with(wav_path, task.language, overwrite=OverwriteMode.NEVER, settings=worker.settings)


def test_dispatch_task_reuses_existing_sidecar_wav(mocker, tmp_path, worker):
    """Test dispatching to Azure reuses an existing sidecar WAV file."""
    source_path = tmp_path / 'path.mp3'
    wav_path = tmp_path / 'path.wav'
    wav_path.write_text('wav')
    mock_save_wav = mocker.patch.object(testee, 'save_as_wav_file')
    mock_transcribe = mocker.patch.object(testee, 'transcribe_audio_file')
    task = Task(source=str(source_path), transcriber=TranscriberType.AZURE)

    worker.dispatch_task(task, source_path)

    mock_save_wav.assert_not_called()
    mock_transcribe.assert_called_once_with(wav_path, task.language, overwrite=OverwriteMode.NEVER, settings=worker.settings)


def test_dispatch_task_without_conversion(mocker, worker):
    """Test dispatching to Azure when the source is already WAV."""
    mock_save_wav = mocker.patch.object(testee, 'save_as_wav_file')
    mock_transcribe = mocker.patch.object(testee, 'transcribe_audio_file')
    task = Task(source='/path.wav', transcriber=TranscriberType.AZURE)
    source_path = Path('/path.wav')

    worker.dispatch_task(task, source_path)

    mock_save_wav.assert_not_called()
    mock_transcribe.assert_called_once_with(source_path, task.language, overwrite=OverwriteMode.NEVER, settings=worker.settings)


def test_dispatch_task_raises_when_wav_conversion_returns_no_path(mocker, tmp_path, owned_path_probes, worker):
    """Test that Azure dispatch raises if WAV conversion does not produce a file path."""
    mock_save = mocker.patch.object(testee, "save_as_wav_file", return_value=None)
    mock_transcribe = mocker.patch.object(testee, "transcribe_audio_file")
    source_path = tmp_path / "audio.mp3"
    task = Task(source=str(source_path), language="en", transcriber=TranscriberType.AZURE)

    with owned_path_probes(), pytest.raises(RuntimeError, match="Failed to create WAV file"):
        worker.dispatch_task(task, source_path)

    mock_save.assert_called_once_with(
        source_path,
        output_file_path=tmp_path / "audio.wav",
        overwrite=OverwriteMode.NEVER,
    )
    mock_transcribe.assert_not_called()
