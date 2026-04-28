import argparse
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
from youtube_whisperer.transcriber.rejection_policy import RejectedTranscriptionError, reject_bad_segments
from youtube_whisperer.transcriber.waveform_loader import load_whisper_waveform_from_file
from youtube_whisperer.utils import TranscriberMode


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
    print(info)
    return segments_generator


def transcribe_waveform_with_default_model(waveform: np.ndarray, mode: TranscriberMode, language: LanguageCode) -> Iterable[Segment]:
    """
    Transcribe the given waveform using the default WhisperModel.

    Args:
        waveform (np.ndarray): The waveform to transcribe/translate.
        mode (TranscriberMode): Whether to run Whisper in transcribe mode or translate mode.
        language (LanguageCode): Whisper's output language.

    Returns:
        Iterable[Segment]: An iterable of lazy-evaluated Segments.
    """
    model = WhisperModel(**get_default_whisper_model_parameters())
    return transcribe_waveform(model, waveform, mode, language)


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
        Path | None: Output SRT file path, or `None` if transcription failed.
    """
    output_file_path = output_file_path or input_file_path.with_suffix('.srt')
    if output_file_path.is_file() and not overwrite_existing_path(output_file_path, overwrite):
        return output_file_path
    waveform = load_whisper_waveform_from_file(input_file_path)
    if len(waveform) == 0:
        print(f'Skipping {input_file_path} because empty waveform is loaded')
        return None
    try:
        segments_generator = reject_bad_segments(transcribe_waveform_with_default_model(waveform, mode, language))
        save_segments_as_srt(map(segment_to_srt_block, segments_generator), output_file_path, overwrite=overwrite)
        return output_file_path
    except RejectedTranscriptionError as e:
        print(f"Rejected Whisper transcription for {input_file_path}: {e}")
        return None
    except Exception as e:
        print(f"An error occurred while transcribing {input_file_path}: {e}")
        return None


def main() -> None:
    """
    CLI entry point to transcribe waveform files with Whisper and save each result to an SRT file.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", type=Path, nargs='+', metavar='path', help="Waveform file paths to transcribe.")
    parser.add_argument("-l", "--language", type=LanguageCode.from_str, help="Language to transcribe waveform files.")
    parser.add_argument("-m", "--mode", type=TranscriberMode, choices=TranscriberMode.values(), default=TranscriberMode.TRANSCRIBE, help="Whether to run Whisper in transcribe mode or translate mode. Defaults to `transcribe`.")
    parser.add_argument("-o", "--overwrite", type=OverwriteMode, choices=OverwriteMode.values(), default=OverwriteMode.PROMPT, help="Whether to overwrite existing SRT files. Defaults to `prompt`.")
    args = parser.parse_args()
    for path in args.paths:
        transcribe_file_with_default_model(path, args.language, overwrite=args.overwrite, mode=args.mode)


if __name__ == "__main__":
    main()
