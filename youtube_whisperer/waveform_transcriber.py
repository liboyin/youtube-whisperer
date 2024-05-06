import argparse
from pathlib import Path
from typing import Iterable

from faster_whisper import WhisperModel
from faster_whisper.transcribe import Segment
import numpy as np

from youtube_whisperer.model_parameters import get_default_whisper_model_parameters
from youtube_whisperer.segment_handler import duplicate_segments_to_file
from youtube_whisperer.waveform_loader import load_waveform_from_file


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


def transcribe_file_with_default_model(input_file_path: Path, output_file_path: Path | None = None) -> Path:
    """
    Transcribe a waveform file using default model parameters and save the transcribed Segments to a file.

    Args:
        input_file_path (Path): The path to the input file containing the waveform.
        output_file_path (Path, optional): The path to the output file where the transcribed Segments will be saved.
            If not provided, a file with the same name as the input file and a '.seg' extension will be created.

    Returns:
        Path: The path to the output file containing the transcribed Segments.
    """
    output_file_path = output_file_path or input_file_path.with_suffix('.seg')
    print('Saving Segments to:', output_file_path)
    segments_generator = transcribe_waveform_with_default_model(load_waveform_from_file(input_file_path))
    for segment in duplicate_segments_to_file(segments_generator, output_file_path):
        print(segment)
    return output_file_path


def main() -> None:
    """
    CLI entry point to transcribe a waveform file and save the transcribed Segments to a file.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path, help="Waveform file path to transcribe.")
    transcribe_file_with_default_model(parser.parse_args().path)


if __name__ == "__main__":
    main()
