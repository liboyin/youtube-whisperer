from typing import Iterable, Generator

from faster_whisper import WhisperModel
from faster_whisper.transcribe import Segment
from faster_whisper.utils import format_timestamp
import numpy as np

from model_parameters import get_default_whisper_model_parameters


def yield_segments(generator: Iterable[Segment]) -> Generator[Segment, None, None]:
    """
    Yield segments from the given transcription generator.
    """
    for segment in generator:
        print(f'{segment.id} {format_timestamp(segment.start)} -> {format_timestamp(segment.end)}: {segment.text}')
        yield segment


def get_transcription_generator(model: WhisperModel, waveform: np.ndarray, language: str) -> Iterable[Segment]:
    """
    Generates transcriptions for the given waveform using the specified Whisper model.

    Args:
        model (WhisperModel): The Whisper model used for transcription.
        waveform (np.ndarray): The waveform to transcribe.
        language (str): The language of the transcription.

    Returns:
        Iterable[Segment]: A generator that yields Segments of the transcription.
    """
    generator, info = model.transcribe(waveform, beam_size=5, task='transcribe', language=language)
    print(info)
    return generator


def transcribe(model: WhisperModel, waveform: np.ndarray, language: str) -> list[Segment]:
    """
    Transcribe the given waveform using the provided WhisperModel.

    Args:
        model (WhisperModel): The Whisper model to use for transcription.
        waveform (np.ndarray): The waveform to transcribe.
        language (str): The language of the waveform.

    Returns:
        list[Segment]: Segments of the transcription.
    """
    return list(yield_segments(get_transcription_generator(model, waveform, language)))


def transcribe_with_default_model(waveform: np.ndarray, language: str) -> list[Segment]:
    """
    Transcribe the given waveform using the default WhisperModel.

    Args:
        waveform (np.ndarray): The waveform to transcribe.
        language (str): The language of the waveform.

    Returns:
        list[Segment]: Segments of the transcription.
    """
    model = WhisperModel(**get_default_whisper_model_parameters())
    return transcribe(model, waveform, language)
