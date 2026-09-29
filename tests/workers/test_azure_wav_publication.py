import io
import wave
from pathlib import Path

import pytest
from pathlib_extensions import OverwriteMode

import youtube_whisperer.workers.azure_worker as testee
from youtube_whisperer.models import Task
from youtube_whisperer.transcriber import waveform_loader
from youtube_whisperer.utils import TranscriberType


def test_dispatch_task_failed_conversion_retries_complete_wav_and_reuses_good_sidecar(mocker, tmp_path):
    """Azure is never called after conversion failure and retry dispatches completed audio."""
    source = tmp_path / 'input.mp3'
    source.write_bytes(b'synthetic source')
    sidecar = source.with_suffix('.wav')
    payload = io.BytesIO()
    with wave.open(payload, 'wb') as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(16000)
        writer.writeframes(b'\x00\x00' * 160)
    complete_wav = payload.getvalue()
    graph = mocker.MagicMock()
    graph.output.return_value = graph
    mocker.patch.object(waveform_loader.ffmpeg, 'input', return_value=graph)
    children = []

    def start(**kwargs):
        """Give each attempt a separate controlled process with stage-only writes."""
        stage = Path(graph.output.call_args.args[0])
        process = mocker.MagicMock()
        process.stdin = None
        process.stdout = io.BytesIO()
        process.stderr = io.BytesIO()
        returncode = 1 if not children else 0
        children.append(process)
        process.poll.return_value = returncode

        def communicate():
            """Write partial failure or a complete WAV without exposing the final path."""
            assert not sidecar.exists()
            stage.write_bytes(b'partial' if returncode else complete_wav)
            return b'', b'conversion failed'

        process.communicate.side_effect = communicate
        return process

    graph.run_async.side_effect = start
    worker = testee.AzureWorker('azure-test', client=mocker.MagicMock(name='owned-redis-client'))
    task = Task(source=str(source), transcriber=TranscriberType.AZURE)
    completed_calls = []

    def transcribe(audio_path, language, *, overwrite):
        """Verify complete WAV bytes synchronously at the mocked Azure boundary."""
        assert audio_path == sidecar
        assert language == task.language
        assert overwrite == OverwriteMode.NEVER
        assert audio_path.read_bytes() == complete_wav
        assert not list(tmp_path.glob('.wav-*'))
        with wave.open(str(audio_path), 'rb') as reader:
            assert (reader.getnchannels(), reader.getsampwidth(), reader.getframerate(), reader.getnframes()) == (1, 2, 16000, 160)
        completed_calls.append(audio_path)

    service = mocker.patch.object(testee, 'transcribe_audio_file', side_effect=transcribe)
    with pytest.raises(waveform_loader.ffmpeg.Error):
        worker.dispatch_task(task, source)
    service.assert_not_called()
    assert not sidecar.exists()
    assert not list(tmp_path.glob('.wav-*'))

    worker.dispatch_task(task, source)
    assert completed_calls == [sidecar]
    assert len(children) == 2
    assert all(child.stdout.closed and child.stderr.closed for child in children)
    worker.dispatch_task(task, source)
    assert completed_calls == [sidecar, sidecar]
    assert len(children) == 2
    assert sidecar.read_bytes() == complete_wav
