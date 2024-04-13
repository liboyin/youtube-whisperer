from pathlib import Path

import ffmpeg
import numpy as np

DEFAULT_SAMPLE_RATE = 16000


def load_waveform_from_bytes(data: bytes, sample_rate: int = DEFAULT_SAMPLE_RATE) -> np.ndarray:
    """
    Load audio from a bytes object and return it as a 1D float32 np.ndarray with a range of [-1, 1].

    Simplified from https://github.com/openai/whisper/blob/main/whisper/audio.py

    cmd = [
        "ffmpeg",
        "-nostdin",  # disables interaction on the standard input (stdin)
        "-threads", "0",  # allows FFmpeg to choose the optimal number of threads automatically
        "-i", input_file,
        "-f", "s16le",  # signed 16-bit little-endian
        "-ac", "1",  # downmix to mono channel
        "-acodec", "pcm_s16le",  # PCM (Pulse-code Modulation) signed 16-bit little-endian
        "-ar", str(sr),  # sample rate
        "-"  # output to stdout instead of a file
    ]
    """
    stream = ffmpeg.input("pipe:", threads=0).output("-", format="s16le", acodec="pcm_s16le", ac=1, ar=sample_rate)
    print(f'ffmpeg args: {stream.get_args()}')
    out, err = stream.run(cmd="ffmpeg", capture_stdout=True, capture_stderr=True, input=data)
    print(err.decode())
    return np.frombuffer(out, np.int16).flatten().astype(np.float32) / 32768


def load_waveform_from_file(path: Path, sample_rate: int = DEFAULT_SAMPLE_RATE) -> np.ndarray:
    """
    Load audio from a binary file and return it as a 1D float32 np.ndarray with a range of [-1, 1].
    """
    return load_waveform_from_bytes(path.read_bytes(), sample_rate)
