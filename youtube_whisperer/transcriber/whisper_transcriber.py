import functools
import logging
from pathlib import Path
from typing import Iterable

from faster_whisper import WhisperModel
from faster_whisper.transcribe import Segment
from faster_whisper.utils import format_timestamp
import numpy as np
from pathlib_extensions import OverwriteMode, overwrite_existing_path

from youtube_whisperer.adaptors.lang_code_adaptor import LanguageCode
from youtube_whisperer.adaptors.srt_deduplicator import SrtBlock, save_segments_as_srt
from youtube_whisperer.transcriber.model_parameters import get_default_whisper_model_parameters
from youtube_whisperer.transcriber.rejection_policy import reject_bad_segments
from youtube_whisperer.transcriber.waveform_loader import load_whisper_waveform_from_file
from youtube_whisperer.utils import TranscriberMode

logger = logging.getLogger(__name__)


def segment_to_srt_block(segment: Segment) -> SrtBlock:
    """
    Convert a faster-whisper Segment into an SrtBlock.

    Args:
        segment (Segment): A Whisper transcription segment with `start`, `end`, and `text` attributes.

    Returns:
        SrtBlock: The SrtBlock representation of the input segment.
    """
    return SrtBlock(
        format_timestamp(segment.start, always_include_hours=True, decimal_marker=','),
        format_timestamp(segment.end, always_include_hours=True, decimal_marker=','),
        segment.text.strip().split('\n'),
    )


def transcribe_waveform(model: WhisperModel, waveform: np.ndarray, mode: TranscriberMode, language: LanguageCode) -> Iterable[Segment]:
    """
    Transcribe the given waveform using the provided Whisper model.

    Args:
        model (WhisperModel): The Whisper model to use.
        waveform (np.ndarray): The waveform to transcribe/translate.
        mode (TranscriberMode): Whether to run Whisper in transcribe mode or translate mode.
        language (LanguageCode): Whisper's output language.

    Returns:
        Iterable[Segment]: An iterable of lazy-evaluated Segments.
    """
    lang_code = language.get_source_as_ISO()
    # Whisper only supports translation to English
    if lang_code == 'en' and mode == TranscriberMode.TRANSLATE:
        mode = TranscriberMode.TRANSCRIBE
    segments_generator, info = model.transcribe(waveform, lang_code, mode.value)
    logger.info("%s", info)
    return segments_generator


@functools.lru_cache(maxsize=1)
def get_default_whisper_model() -> WhisperModel:
    """Build the default WhisperModel once per process and cache it.

    The model can be several GB (e.g. `large-v3`); on a dedicated GPU worker it is loaded once
    and kept resident across tasks instead of being rebuilt for every queued file. The cache is
    keyed on nothing, so the model is shared for the process lifetime.

    Returns:
        WhisperModel: The process-wide default model built from resolved parameters.
    """
    return WhisperModel(**get_default_whisper_model_parameters())


def transcribe_waveform_with_default_model(waveform: np.ndarray, mode: TranscriberMode, language: LanguageCode) -> Iterable[Segment]:
    """
    Transcribe the given waveform using the cached default WhisperModel.

    Args:
        waveform (np.ndarray): The waveform to transcribe/translate.
        mode (TranscriberMode): Whether to run Whisper in transcribe mode or translate mode.
        language (LanguageCode): Whisper's output language.

    Returns:
        Iterable[Segment]: An iterable of lazy-evaluated Segments.
    """
    return transcribe_waveform(get_default_whisper_model(), waveform, mode, language)


def transcribe_file_with_default_model(input_file_path: Path, language: LanguageCode, output_file_path: Path | None = None, overwrite: OverwriteMode = OverwriteMode.PROMPT, mode: TranscriberMode = TranscriberMode.TRANSCRIBE) -> Path | None:
    """
    Transcribe a waveform file using default model parameters and save the output to an SRT file.

    Args:
        input_file_path (Path): Input waveform file path.
        language (LanguageCode): Whisper's output language.
        output_file_path (Path | None, optional): Output SRT file path. If `None`, it will be the input file path with a `.srt` extension. Defaults to `None`.
        overwrite (OverwriteMode, optional): Whether to overwrite existing SRT files. Defaults to `prompt`.
        mode (TranscriberMode, optional): Whether to run Whisper in transcribe mode or translate mode. Defaults to `transcribe`.

    Returns:
        Path | None: Output SRT file path, or `None` if the input decodes to an empty waveform.

    Raises:
        RejectedTranscriptionError: If Whisper emits a known bad output substring.
        Exception: If loading the waveform or transcription otherwise fails; the error propagates
            so callers (e.g. the worker loop) can dead-letter the task instead of silently dropping it.
    """
    output_file_path = output_file_path or input_file_path.with_suffix('.srt')
    if output_file_path.is_file() and not overwrite_existing_path(output_file_path, overwrite):
        return output_file_path
    waveform = load_whisper_waveform_from_file(input_file_path)
    if len(waveform) == 0:
        logger.warning("Skipping %s because empty waveform is loaded", input_file_path)
        return None
    segments_generator = reject_bad_segments(transcribe_waveform_with_default_model(waveform, mode, language))
    save_segments_as_srt(map(segment_to_srt_block, segments_generator), output_file_path, overwrite=overwrite)
    return output_file_path
