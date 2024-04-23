from pathlib import Path
from typing import Generator, Iterable

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


def duplicate_segments_to_file(segments: Iterable[Segment], file_path: Path, flush: bool = True) -> Generator[Segment, None, None]:
    """
    Write Segments to a file, and yield them.

    Args:
        segments (Iterable[Segment]): The Segments to write.
        file_path (Path): The path to the file to write to.
        flush (bool, optional): Whether to flush the file after writing each Segment. Defaults to True.

    Yields:
        Generator[Segment, None, None]: A generator of Segments as-is.
    """
    with prepare_output_file(file_path).open('w') as file_handler:
        for i, x in enumerate(segments):
            # write a newline between Segments, but not after the last one
            if i:
                file_handler.write(f'\n{x}')
            else:
                file_handler.write(str(x))
            if flush:
                # wait until the current Segment is written to disk
                file_handler.flush()
            yield x


def write_segments_to_file(segments: Iterable[Segment], file_path: Path) -> None:
    """
    Write Segments to a file.

    Args:
        segments (Iterable[Segment]): The Segments to write.
        file_path (Path): The path to the file to write to.
    """
    prepare_output_file(file_path).write_text('\n'.join(map(str, segments)))
