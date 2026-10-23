from pathlib import Path

import pytest
from pathlib_extensions import OverwritePolicy

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

    mock_save_wav.assert_called_once_with(source_path, output_file_path=wav_path, overwrite=OverwritePolicy.NEVER)
    mock_transcribe.assert_called_once_with(wav_path, task.language, overwrite=OverwritePolicy.NEVER, settings=worker.settings)


def test_dispatch_task_reuses_existing_sidecar_wav(mocker, tmp_path, worker):
    """An existing sidecar WAV is transcribed unchanged, without converting the source again."""
    source_path = tmp_path / 'path.mp3'
    source_path.write_bytes(b'not decodable audio')
    wav_path = tmp_path / 'path.wav'
    wav_path.write_bytes(b'existing wav')
    mock_transcribe = mocker.patch.object(testee, 'transcribe_audio_file')
    task = Task(source=str(source_path), transcriber=TranscriberType.AZURE)

    worker.dispatch_task(task, source_path)

    assert wav_path.read_bytes() == b'existing wav'
    assert sorted(tmp_path.iterdir()) == [source_path, wav_path]
    mock_transcribe.assert_called_once_with(wav_path, task.language, overwrite=OverwritePolicy.NEVER, settings=worker.settings)


def test_dispatch_task_requires_source_even_when_sidecar_wav_exists(mocker, tmp_path, worker):
    """A missing source fails input validation before Azure, even though its sidecar WAV exists."""
    source_path = tmp_path / 'path.mp3'
    wav_path = tmp_path / 'path.wav'
    wav_path.write_bytes(b'existing wav')
    mock_transcribe = mocker.patch.object(testee, 'transcribe_audio_file')
    task = Task(source=str(source_path), transcriber=TranscriberType.AZURE)

    with pytest.raises(FileNotFoundError):
        worker.dispatch_task(task, source_path)

    assert wav_path.read_bytes() == b'existing wav'
    assert list(tmp_path.iterdir()) == [wav_path]
    mock_transcribe.assert_not_called()


def test_dispatch_task_without_conversion(mocker, worker):
    """Test dispatching to Azure when the source is already WAV."""
    mock_save_wav = mocker.patch.object(testee, 'save_as_wav_file')
    mock_transcribe = mocker.patch.object(testee, 'transcribe_audio_file')
    task = Task(source='/path.wav', transcriber=TranscriberType.AZURE)
    source_path = Path('/path.wav')

    worker.dispatch_task(task, source_path)

    mock_save_wav.assert_not_called()
    mock_transcribe.assert_called_once_with(source_path, task.language, overwrite=OverwritePolicy.NEVER, settings=worker.settings)


def test_dispatch_task_transcribes_sidecar_when_conversion_keeps_existing_wav(mocker, tmp_path, owned_path_probes, worker):
    """A None result, meaning NEVER kept an existing sidecar WAV, still transcribes that sidecar."""
    mock_save = mocker.patch.object(testee, "save_as_wav_file", return_value=None)
    mock_transcribe = mocker.patch.object(testee, "transcribe_audio_file")
    source_path = tmp_path / "audio.mp3"
    task = Task(source=str(source_path), language="en", transcriber=TranscriberType.AZURE)

    with owned_path_probes():
        worker.dispatch_task(task, source_path)

    mock_save.assert_called_once_with(
        source_path,
        output_file_path=tmp_path / "audio.wav",
        overwrite=OverwritePolicy.NEVER,
    )
    mock_transcribe.assert_called_once_with(tmp_path / "audio.wav", task.language, overwrite=OverwritePolicy.NEVER, settings=worker.settings)
