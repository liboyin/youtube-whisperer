"""Tests for loading Whisper waveforms from audio files."""

from pathlib import Path

import ffmpeg
import numpy as np
import pytest

import youtube_whisperer.transcriber.waveform_loader as testee


class FakeFFmpegError(ffmpeg.Error):
    """An ffmpeg error that carries only its stderr output."""

    def __init__(self, stderr: bytes) -> None:
        """Store the stderr output without calling the base constructor."""
        self.stderr = stderr


class FakeStream:
    """An ffmpeg stream stand-in that records its calls and returns canned output."""

    def __init__(self, *, stdout: bytes = b"", stderr: bytes = b"", error: Exception | None = None) -> None:
        """Store the canned output, or the error that `run` raises."""
        self.stdout = stdout
        self.stderr = stderr
        self.error = error
        self.run_calls = []

    def output(self, *args, **kwargs):
        """Record the output arguments and return this stream."""
        self.output_args = args
        self.output_kwargs = kwargs
        return self

    def get_args(self):
        """Return a fixed ffmpeg command line."""
        return ["ffmpeg", "-i", "pipe:"]

    def run(self, **kwargs):
        """Record the call, then raise the configured error or return the canned output."""
        self.run_calls.append(kwargs)
        if self.error:
            raise self.error
        return self.stdout, self.stderr


@pytest.mark.parametrize("sample_rate", [testee.DEFAULT_SAMPLE_RATE, 8000])
@pytest.mark.parametrize("samples", [[-32768, -16384, -1, 0, 1, 16384, 32767], []])
def test_load_whisper_waveform_from_file_captures_pcm_and_normalizes_samples(mocker, tmp_path, sample_rate, samples):
    """Pass a file path to ffmpeg and convert its captured mono PCM buffer to float32."""
    input_path = tmp_path / "audio.raw"
    pcm = np.array(samples, dtype=np.int16).tobytes()
    stream = FakeStream(stdout=pcm)
    mock_prepare = mocker.patch.object(testee, "prepare_input_file", return_value=input_path)
    mock_input = mocker.patch.object(testee.ffmpeg, "input", return_value=stream)

    waveform = (
        testee.load_whisper_waveform_from_file(Path("ignored.raw"))
        if sample_rate == testee.DEFAULT_SAMPLE_RATE
        else testee.load_whisper_waveform_from_file(Path("ignored.raw"), sample_rate=sample_rate)
    )

    np.testing.assert_array_equal(waveform, np.array(samples, dtype=np.float32) / 32768)
    assert waveform.shape == (len(samples),)
    assert waveform.dtype == np.float32
    mock_prepare.assert_called_once_with(Path("ignored.raw"))
    mock_input.assert_called_once_with(str(input_path), threads=0)
    assert stream.output_args == ("pipe:",)
    assert stream.output_kwargs == {
        "format": "s16le",
        "acodec": "pcm_s16le",
        "ac": 1,
        "ar": sample_rate,
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
