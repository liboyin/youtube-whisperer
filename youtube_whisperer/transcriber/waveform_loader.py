import logging
from pathlib import Path

import ffmpeg
import numpy as np
from pathlib_extensions import OverwriteMode, overwrite_existing_path, prepare_input_file, prepare_output_file

logger = logging.getLogger(__name__)

DEFAULT_SAMPLE_RATE = 16000


def load_whisper_waveform_from_file(path: Path, sample_rate: int = DEFAULT_SAMPLE_RATE) -> np.ndarray:
    """
    Load Whisper-style waveform from a file and return it as a NumPy array.

    ffmpeg streams the file directly so the raw bytes never reside in Python memory.

    Args:
        path (Path): Path to the audio/video file to decode.
        sample_rate (int, optional): Target sample rate in Hz. Defaults to `DEFAULT_SAMPLE_RATE`.

    Returns:
        np.ndarray: Mono float32 waveform normalized to the range [-1, 1).

    Raises:
        ffmpeg.Error: If ffmpeg fails to decode the input file.
    """
    input_path = prepare_input_file(path)
    stream = (
        ffmpeg
        .input(str(input_path), threads=0)
        .output("pipe:", format="s16le", acodec="pcm_s16le", ac=1, ar=sample_rate)
    )
    logger.debug("ffmpeg args: %s", stream.get_args())
    try:
        out, _ = stream.run(capture_stdout=True, capture_stderr=True)
    except ffmpeg.Error as e:
        logger.error("ffmpeg failed: %s", e.stderr.decode())
        raise
    return np.frombuffer(out, np.int16).flatten().astype(np.float32) / 32768


def save_as_wav_file(input_file_path: Path, output_file_path: Path | None = None, overwrite: OverwriteMode = OverwriteMode.PROMPT) -> Path | None:
    """
    Converts an audio or video file to a WAV file using ffmpeg. This is required by Azure Speech Recognition API.

    Args:
        input_file_path (Path): The path to the input file.
        output_file_path (Path | None, optional): The path to the output WAV file. If `None`, it will be the input file path with a `.wav` extension. Defaults to `None`.
        overwrite (OverwriteMode, optional): Whether to overwrite an existing file. Defaults to `prompt`.

    Returns:
        Path | None: The path to the created WAV file, or None if the operation was skipped.
    """
    input_file_path = prepare_input_file(input_file_path)
    output_file_path = output_file_path or input_file_path.with_suffix('.wav')
    if output_file_path.is_file() and not overwrite_existing_path(output_file_path, overwrite):
        return None
    output_file_path = prepare_output_file(output_file_path)
    stream = (
        ffmpeg
        .input(str(input_file_path))
        .output(str(output_file_path), acodec='pcm_s16le', ac=1, ar=DEFAULT_SAMPLE_RATE)
    )
    try:
        # The overwrite logic is handled by overwrite_existing_path, so we can always overwrite here.
        stream.run(overwrite_output=True, capture_stdout=True, capture_stderr=True)
    except ffmpeg.Error as e:
        logger.error("ffmpeg failed: %s", e.stderr.decode())
        raise
    return output_file_path
