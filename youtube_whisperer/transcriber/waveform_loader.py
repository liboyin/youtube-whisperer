import logging
import os
import stat
from pathlib import Path
from uuid import uuid4

import ffmpeg
import numpy as np
from pathlib_extensions import (
    OverwriteMode,
    overwrite_existing_path,
    prepare_input_file,
    prepare_output_file,
)

logger = logging.getLogger(__name__)

DEFAULT_SAMPLE_RATE = 16000


def load_whisper_waveform_from_file(path: Path, sample_rate: int = DEFAULT_SAMPLE_RATE) -> np.ndarray:
    """
    Load Whisper-style waveform from a file and return it as a NumPy array.

    ffmpeg receives the input path; Python captures the complete decoded PCM byte
    buffer before converting its one-dimensional int16 view to float32 samples.

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
    return np.frombuffer(out, np.int16).astype(np.float32) / 32768


def _convert_audio_to_stage(input_file_path: Path, stage: Path) -> None:
    """Finish ffmpeg conversion while owning child cancellation and pipe cleanup.

    Only a successfully reaped child permits publication. On interruption or
    failure, kill any still-running child and drain/reap it before the caller
    removes its stage. This lifecycle is specific to sidecar conversion.

    Args:
        input_file_path (Path): Validated input audio or video file.
        stage (Path): Exclusively owned sibling with the destination suffix.

    Raises:
        ffmpeg.Error: If conversion fails, retaining captured output diagnostics.
        BaseException: Startup errors or interruptions propagate after cleanup.
    """
    stream = (
        ffmpeg
        .input(str(input_file_path))
        .output(str(stage), acodec='pcm_s16le', ac=1, ar=DEFAULT_SAMPLE_RATE)
    )
    process = stream.run_async(overwrite_output=True, pipe_stdout=True, pipe_stderr=True)
    try:
        out, err = process.communicate()
        if process.poll():
            raise ffmpeg.Error('ffmpeg', out, err)
    except BaseException:
        if process.poll() is None:
            process.kill()
        process.communicate()
        raise
    finally:
        for pipe in (process.stdin, process.stdout, process.stderr):
            if pipe is not None:
                pipe.close()


def save_as_wav_file(input_file_path: Path, output_file_path: Path | None = None, overwrite: OverwriteMode = OverwriteMode.PROMPT) -> Path | None:
    """Convert audio to a completed sidecar before atomically publishing it.

    Early overwrite preflight avoids conversion and duplicate prompts. Staging
    retains the destination suffix for ffmpeg container inference. Publication
    follows symlink targets and preserves existing modes, but replaces the inode:
    hardlinked aliases retain old contents; ownership, ACLs and xattrs may change.
    NEVER/RENAME preserve late competing files using same-filesystem hard links;
    other collisions and unsupported links raise without an unsafe fallback.
    Only owned stages are cleaned; abrupt exit may leave one. This protects
    process interruption, not power-loss durability, and does not repair old WAVs.

    Args:
        input_file_path (Path): Audio or video input, validated by the input helper.
        output_file_path (Path | None): Destination, defaulting to input with `.wav`.
        overwrite (OverwriteMode): Existing-file policy, defaulting to PROMPT.

    Returns:
        Path | None: Original prepared destination path on completion (including
        a late competing file), or None when preflight declines replacement.

    Raises:
        ffmpeg.Error: Failed conversion, logged with captured stderr diagnostics.
        OSError: Input/output validation, staging, startup or publication failure.
    """
    input_file_path = prepare_input_file(input_file_path)
    output_file_path = output_file_path or input_file_path.with_suffix('.wav')
    if output_file_path.is_file() and not overwrite_existing_path(output_file_path, overwrite):
        return None
    output_file_path = prepare_output_file(output_file_path)
    target = output_file_path.resolve()
    prepare_output_file(target)
    try:
        mode = stat.S_IMODE(target.stat().st_mode)
    except FileNotFoundError:
        mode = None
    stage = target.parent / f'.wav-{uuid4().hex}{output_file_path.suffix}'
    owned = False
    try:
        # Exclusive creation uses ordinary 0666 permissions filtered by umask.
        writer = stage.open('xb')
        owned = True
        writer.close()
        _convert_audio_to_stage(input_file_path, stage)
        if mode is not None:
            stage.chmod(mode)
        if overwrite in (OverwriteMode.NEVER, OverwriteMode.RENAME):
            try:
                os.link(stage, target)
            except FileExistsError:
                if not target.is_file():
                    raise
        else:
            stage.replace(target)
    except ffmpeg.Error as e:
        logger.error("ffmpeg failed: %s", e.stderr.decode())
        raise
    finally:
        if owned:
            stage.unlink(missing_ok=True)
    return output_file_path
