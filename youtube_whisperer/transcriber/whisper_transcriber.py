import functools
import logging
from collections.abc import Iterable
from pathlib import Path

import numpy as np
from faster_whisper import WhisperModel
from faster_whisper.transcribe import Segment
from pathlib_extensions import OverwriteMode, overwrite_existing_path

from youtube_whisperer.adaptors.lang_code_adaptor import LanguageCode
from youtube_whisperer.adaptors.srt_deduplicator import (
    SrtBlock,
    save_segments_as_srt,
    timestamps_to_srt_block,
)
from youtube_whisperer.config import Settings
from youtube_whisperer.transcriber.model_parameters import (
    get_default_whisper_model_parameters,
)
from youtube_whisperer.transcriber.rejection_policy import reject_bad_segments
from youtube_whisperer.transcriber.waveform_loader import (
    load_whisper_waveform_from_file,
)

logger = logging.getLogger(__name__)


def segment_to_srt_block(segment: Segment) -> SrtBlock:
    """
    Convert a faster-whisper Segment into an SrtBlock.

    Args:
        segment (Segment): A Whisper transcription segment with `start`, `end`, and `text` attributes.

    Returns:
        SrtBlock: The SrtBlock representation of the input segment.
    """
    return timestamps_to_srt_block(segment.start, segment.end, segment.text)


def transcribe_waveform(model: WhisperModel, waveform: np.ndarray, language: LanguageCode) -> Iterable[Segment]:
    """
    Transcribe the given waveform in its source language using the provided Whisper model.

    Args:
        model (WhisperModel): The Whisper model to use.
        waveform (np.ndarray): The waveform to transcribe.
        language (LanguageCode): The source language of the waveform.

    Returns:
        Iterable[Segment]: An iterable of lazy-evaluated Segments.
    """
    lang_code = language.get_source_as_ISO()
    segments_generator, info = model.transcribe(waveform, lang_code, 'transcribe')
    logger.info("%s", info)
    return segments_generator


@functools.cache
def get_default_whisper_model(*, parameters: tuple[str, str, str, str, int] | None = None) -> WhisperModel:
    """Build a lazy resident model cached by immutable resolved constructor identity.

    No-argument calls retain the initial uncached invocation's environment model.
    Explicit snapshots use a parameter tuple, so differing configurations cannot
    reuse the wrong model. cache_clear() releases all identities, including default.

    Args:
        parameters: Model name, cache path, device, compute type and CPU threads;
            None resolves defaults on initial uncached construction.

    Returns:
        A resident Whisper model shared only with matching constructor identity.
    """
    if parameters is None:
        return WhisperModel(**get_default_whisper_model_parameters())
    model_name, cache_dir, device, compute_type, cpu_threads = parameters
    return WhisperModel(
        model_size_or_path=model_name, download_root=cache_dir, device=device,
        compute_type=compute_type, cpu_threads=cpu_threads,
    )


def transcribe_waveform_with_default_model(waveform: np.ndarray, language: LanguageCode, *, settings: Settings | None = None) -> Iterable[Segment]:
    """
    Transcribe the given waveform using the cached default WhisperModel.

    Args:
        waveform (np.ndarray): The waveform to transcribe.
        language (LanguageCode): The source language of the waveform.
        settings: Supplied model snapshot; None uses the process default model.

    Returns:
        Iterable[Segment]: An iterable of lazy-evaluated Segments.
    """
    if settings is None:
        model = get_default_whisper_model()
    else:
        parameters = get_default_whisper_model_parameters(settings)
        model = get_default_whisper_model(parameters=(
            parameters['model_size_or_path'], parameters['download_root'],
            parameters['device'], parameters['compute_type'], parameters.get('cpu_threads', 0),
        ))
    return transcribe_waveform(model, waveform, language)


def transcribe_file_with_default_model(input_file_path: Path, language: LanguageCode, output_file_path: Path | None = None, overwrite: OverwriteMode = OverwriteMode.PROMPT, *, settings: Settings | None = None) -> Path | None:
    """
    Transcribe a waveform file using default model parameters and save the output to an SRT file.

    Existing-output consent is obtained before model work and reused for saving;
    complete lazy recognition and rejection finish before SRT publication.

    Args:
        input_file_path (Path): Input waveform file path.
        language (LanguageCode): The source language of the waveform.
        output_file_path (Path | None, optional): Output SRT file path. If `None`, it will be the input file path with a `.srt` extension. Defaults to `None`.
        settings: Supplied model snapshot; None uses the process default model.
        overwrite (OverwriteMode, optional): Whether to overwrite existing SRT files. Defaults to `prompt`.

    Returns:
        Path | None: Output SRT file path, including an existing output when overwrite is denied.

    Raises:
        ValueError: If decoding produces no audio samples, before model or SRT work.
        RejectedTranscriptionError: If Whisper emits a known bad output substring.
        Exception: If loading the waveform or transcription otherwise fails; the error propagates
            so callers (e.g. the worker loop) can dead-letter the task instead of silently dropping it.
    """
    output_file_path = output_file_path or input_file_path.with_suffix('.srt')
    if output_file_path.is_file():
        if not overwrite_existing_path(output_file_path, overwrite):
            return output_file_path
        if overwrite == OverwriteMode.PROMPT:
            overwrite = OverwriteMode.ALWAYS
    waveform = load_whisper_waveform_from_file(input_file_path)
    if len(waveform) == 0:
        raise ValueError(f"No audio samples decoded from {input_file_path}; check that the file contains a decodable audio track.")
    segments = transcribe_waveform_with_default_model(waveform, language) if settings is None else transcribe_waveform_with_default_model(waveform, language, settings=settings)
    segments_generator = reject_bad_segments(segments)
    save_segments_as_srt(map(segment_to_srt_block, segments_generator), output_file_path, overwrite=overwrite)
    return output_file_path
