from pathlib import Path
from typing import Iterable

from faster_whisper import WhisperModel
from faster_whisper.transcribe import Segment
import numpy as np

from youtube_whisperer.model_parameters import get_default_whisper_model_parameters
from youtube_whisperer.pathlib_extensions import prepare_output_file


def transcribe_waveform(model: WhisperModel, waveform: np.ndarray, **kwargs) -> Iterable[Segment]:
    """
    Transcribe the given waveform using the provided WhisperModel.

    Args:
        model (WhisperModel): The Whisper model to use for transcription.
        waveform (np.ndarray): The waveform to transcribe.
        kwargs: Additional arguments to pass to model.transcribe().

    Returns:
        Iterable[Segment]: An iterable of Segments of the transcription.
    """
    segments_generator, info = model.transcribe(waveform, **kwargs)
    print(info)
    return segments_generator


def transcribe_waveform_with_default_model(waveform: np.ndarray, **kwargs) -> Iterable[Segment]:
    """
    Transcribe the given waveform using the default WhisperModel.

    Args:
        waveform (np.ndarray): The waveform to transcribe.
        kwargs: Additional arguments to pass to model.transcribe().

    Returns:
        Iterable[Segment]: An iterable of Segments of the transcription.
    """
    model = WhisperModel(**get_default_whisper_model_parameters())
    return transcribe_waveform(model, waveform, **kwargs)


def write_segments_to_file(segments: Iterable[Segment], file_path: Path) -> None:
    """
    Write Segments to a file.

    Args:
        segments (Iterable[Segment]): The Segments to write.
        file_path (Path): The path to the file to write to.
    """
    prepare_output_file(file_path).write_text('\n'.join(map(str, segments)))
