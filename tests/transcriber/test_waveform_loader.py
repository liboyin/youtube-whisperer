from pathlib import Path

import ffmpeg
import numpy as np
import pytest

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


def test_load_whisper_waveform_from_file_reraises_ffmpeg_error(mocker, tmp_path, caplog):
    """Test that ffmpeg decode errors on file input are logged and re-raised."""
    input_path = tmp_path / "audio.raw"
    stream = FakeStream(error=FakeFFmpegError(b"decoder failed"))
    mocker.patch.object(testee, "prepare_input_file", return_value=input_path)
    mocker.patch.object(testee.ffmpeg, "input", return_value=stream)

    with pytest.raises(FakeFFmpegError):
        testee.load_whisper_waveform_from_file(Path("ignored.raw"))

    assert "decoder failed" in caplog.text
