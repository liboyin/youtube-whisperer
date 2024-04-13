from typing import Iterable

from faster_whisper import WhisperModel
from faster_whisper.transcribe import Segment
import numpy as np

from youtube_whisperer.model_parameters import get_default_whisper_model_parameters
from youtube_whisperer.segment_to_srt_adaptor import yield_srt_blocks_from_segments
from youtube_whisperer.srt_deduplicator import SrtBlock, deduplicate_srt_blocks


def get_transcription_generator(model: WhisperModel, waveform: np.ndarray, **kwargs) -> Iterable[Segment]:
    """
    Return a transcription generator for the given waveform using the specified Whisper model.

    Args:
        model (WhisperModel): The Whisper model used for transcription.
        waveform (np.ndarray): The waveform to transcribe.
        kwargs: Additional arguments to pass to model.transcribe().

    Returns:
        Iterable[Segment]: An iterable of Segments of the transcription.
    """
    segments, info = model.transcribe(waveform, **kwargs)
    print(info)
    return segments


def transcribe_waveform(model: WhisperModel, waveform: np.ndarray, **kwargs) -> list[SrtBlock]:
    """
    Transcribe the given waveform using the provided WhisperModel.

    Args:
        model (WhisperModel): The Whisper model to use for transcription.
        waveform (np.ndarray): The waveform to transcribe.
        kwargs: Additional arguments to pass to model.transcribe().

    Returns:
        list[SrtBlock]: Transcription of the waveform as a list of SRT blocks.
    """
    return deduplicate_srt_blocks(yield_srt_blocks_from_segments(get_transcription_generator(model, waveform, **kwargs)))


def transcribe_waveform_with_default_model(waveform: np.ndarray, **kwargs) -> list[SrtBlock]:
    """
    Transcribe the given waveform using the default WhisperModel.

    Args:
        waveform (np.ndarray): The waveform to transcribe.
        kwargs: Additional arguments to pass to model.transcribe().

    Returns:
        list[SrtBlock]: Transcription of the waveform as a list of SRT blocks.
    """
    model = WhisperModel(**get_default_whisper_model_parameters())
    return transcribe_waveform(model, waveform, **kwargs)
