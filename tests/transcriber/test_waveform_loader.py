from pathlib import Path

import ffmpeg
import numpy as np
import pytest
from pathlib_extensions import OverwriteMode

import youtube_whisperer.transcriber.waveform_loader as testee


class FakeFFmpegError(ffmpeg.Error):
    def __init__(self, stderr: bytes) -> None:
        self.stderr = stderr


class FakeStream:
    def __init__(self, *, stdout: bytes = b"", stderr: bytes = b"", error: Exception | None = None) -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.error = error
        self.run_calls = []

    def output(self, *args, **kwargs):
        self.output_args = args
        self.output_kwargs = kwargs
        return self

    def get_args(self):
        return ["ffmpeg", "-i", "pipe:"]

    def run(self, **kwargs):
        self.run_calls.append(kwargs)
        if self.error:
            raise self.error
        return self.stdout, self.stderr


def test_load_whisper_waveform_from_bytes_decodes_pcm_stream(mocker):
    """Test that PCM bytes are decoded and normalized to a float32 waveform."""
    pcm = np.array([0, 16384, -16384], dtype=np.int16).tobytes()
    stream = FakeStream(stdout=pcm)
    mocker.patch.object(testee.ffmpeg, "input", return_value=stream)

    waveform = testee.load_whisper_waveform_from_bytes(b"audio-bytes")

    np.testing.assert_allclose(waveform, np.array([0.0, 0.5, -0.5], dtype=np.float32))
    assert stream.output_kwargs == {
        "format": "s16le",
        "acodec": "pcm_s16le",
        "ac": 1,
        "ar": testee.DEFAULT_SAMPLE_RATE,
    }
    assert stream.run_calls == [{
        "input": b"audio-bytes",
        "capture_stdout": True,
        "capture_stderr": True,
    }]


def test_load_whisper_waveform_from_bytes_reraises_ffmpeg_error(mocker, capsys):
    """Test that ffmpeg decode errors on bytes input are logged and re-raised."""
    stream = FakeStream(error=FakeFFmpegError(b"decoder failed"))
    mocker.patch.object(testee.ffmpeg, "input", return_value=stream)

    with pytest.raises(FakeFFmpegError):
        testee.load_whisper_waveform_from_bytes(b"audio-bytes")

    assert "decoder failed" in capsys.readouterr().out


def test_load_whisper_waveform_from_file_streams_path_through_ffmpeg(mocker, tmp_path):
    """Test that a file path is streamed through ffmpeg without buffering bytes in Python."""
    input_path = tmp_path / "audio.raw"
    pcm = np.array([0, 16384, -16384], dtype=np.int16).tobytes()
    stream = FakeStream(stdout=pcm)
    mock_prepare = mocker.patch.object(testee, "prepare_input_file", return_value=input_path)
    mock_input = mocker.patch.object(testee.ffmpeg, "input", return_value=stream)

    waveform = testee.load_whisper_waveform_from_file(Path("ignored.raw"), sample_rate=8000)

    np.testing.assert_allclose(waveform, np.array([0.0, 0.5, -0.5], dtype=np.float32))
    mock_prepare.assert_called_once_with(Path("ignored.raw"))
    mock_input.assert_called_once_with(str(input_path), threads=0)
    assert stream.output_kwargs == {
        "format": "s16le",
        "acodec": "pcm_s16le",
        "ac": 1,
        "ar": 8000,
    }
    assert stream.run_calls == [{"capture_stdout": True, "capture_stderr": True}]


def test_load_whisper_waveform_from_file_reraises_ffmpeg_error(mocker, tmp_path, capsys):
    """Test that ffmpeg decode errors on file input are logged and re-raised."""
    input_path = tmp_path / "audio.raw"
    stream = FakeStream(error=FakeFFmpegError(b"decoder failed"))
    mocker.patch.object(testee, "prepare_input_file", return_value=input_path)
    mocker.patch.object(testee.ffmpeg, "input", return_value=stream)

    with pytest.raises(FakeFFmpegError):
        testee.load_whisper_waveform_from_file(Path("ignored.raw"))

    assert "decoder failed" in capsys.readouterr().out


def test_save_as_wav_file_returns_none_when_overwrite_denied(mocker, tmp_path):
    """Test that conversion is skipped when an existing WAV must not be overwritten."""
    input_path = tmp_path / "input.mp3"
    output_path = tmp_path / "output.wav"
    output_path.write_text("existing")
    mocker.patch.object(testee, "prepare_input_file", return_value=input_path)
    mock_overwrite = mocker.patch.object(testee, "overwrite_existing_path", return_value=False)
    mock_prepare = mocker.patch.object(testee, "prepare_output_file")
    mock_input = mocker.patch.object(testee.ffmpeg, "input")

    result = testee.save_as_wav_file(input_path, output_file_path=output_path, overwrite=OverwriteMode.NEVER)

    assert result is None
    mock_overwrite.assert_called_once_with(output_path, OverwriteMode.NEVER)
    mock_prepare.assert_not_called()
    mock_input.assert_not_called()


def test_save_as_wav_file_runs_ffmpeg_and_returns_output_path(mocker, tmp_path):
    """Test that a mono 16-bit PCM WAV is produced and its path returned."""
    input_path = tmp_path / "input.mp3"
    output_path = tmp_path / "output.wav"
    stream = FakeStream()
    mocker.patch.object(testee, "prepare_input_file", return_value=input_path)
    mocker.patch.object(testee, "prepare_output_file", return_value=output_path)
    mocker.patch.object(testee.ffmpeg, "input", return_value=stream)

    result = testee.save_as_wav_file(input_path, output_file_path=output_path, overwrite=OverwriteMode.ALWAYS)

    assert result == output_path
    assert stream.output_args == (str(output_path),)
    assert stream.output_kwargs == {
        "acodec": "pcm_s16le",
        "ac": 1,
        "ar": testee.DEFAULT_SAMPLE_RATE,
    }
    assert stream.run_calls == [{
        "overwrite_output": True,
        "capture_stdout": True,
        "capture_stderr": True,
    }]


def test_save_as_wav_file_reraises_ffmpeg_error(mocker, tmp_path, capsys):
    """Test that ffmpeg conversion errors are logged and re-raised."""
    input_path = tmp_path / "input.mp3"
    output_path = tmp_path / "output.wav"
    stream = FakeStream(error=FakeFFmpegError(b"conversion failed"))
    mocker.patch.object(testee, "prepare_input_file", return_value=input_path)
    mocker.patch.object(testee, "prepare_output_file", return_value=output_path)
    mocker.patch.object(testee.ffmpeg, "input", return_value=stream)

    with pytest.raises(FakeFFmpegError):
        testee.save_as_wav_file(input_path, output_file_path=output_path, overwrite=OverwriteMode.ALWAYS)

    assert "conversion failed" in capsys.readouterr().out
