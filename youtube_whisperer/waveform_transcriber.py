from typing import Iterable, Generator

from faster_whisper import WhisperModel
from faster_whisper.transcribe import Segment
from faster_whisper.utils import format_timestamp
import numpy as np

from .model_parameters import get_default_whisper_model_parameters
from .srt_deduplicator import SrtBlock, deduplicate_srt_blocks


def yield_srt_blocks_from_segments(segments: Iterable[Segment]) -> Generator[SrtBlock, None, None]:
    """
    Generate SrtBlock objects from an iterable of segments.
    """
    for segment in segments:
        print(segment)
        result = SrtBlock(
            format_timestamp(segment.start),
            format_timestamp(segment.end),
            segment.text.strip().split('\n'),
        )
        print(result)
        yield result


def get_transcription_generator(model: WhisperModel, waveform: np.ndarray, language: str) -> Iterable[Segment]:
    """
    Return a transcription generator for the given waveform using the specified Whisper model.

    Args:
        model (WhisperModel): The Whisper model used for transcription.
        waveform (np.ndarray): The waveform to transcribe.
        language (str): The language of the transcription.

    Returns:
        Iterable[Segment]: An iterable of Segments of the transcription.
    """
    segments, info = model.transcribe(waveform, beam_size=5, task='transcribe', language=language)
    print(info)
    return segments


def transcribe_waveform(model: WhisperModel, waveform: np.ndarray, language: str) -> list[SrtBlock]:
    """
    Transcribe the given waveform using the provided WhisperModel.

    Args:
        model (WhisperModel): The Whisper model to use for transcription.
        waveform (np.ndarray): The waveform to transcribe.
        language (str): The language of the waveform.

    Returns:
        list[SrtBlock]: Transcription of the waveform as a list of SRT blocks.
    """
    return deduplicate_srt_blocks(yield_srt_blocks_from_segments(get_transcription_generator(model, waveform, language)))


def transcribe_waveform_with_default_model(waveform: np.ndarray, language: str) -> list[SrtBlock]:
    """
    Transcribe the given waveform using the default WhisperModel.

    Args:
        waveform (np.ndarray): The waveform to transcribe.
        language (str): The language of the waveform.

    Returns:
        list[SrtBlock]: Transcription of the waveform as a list of SRT blocks.
    """
    model = WhisperModel(**get_default_whisper_model_parameters())
    return transcribe_waveform(model, waveform, language)
