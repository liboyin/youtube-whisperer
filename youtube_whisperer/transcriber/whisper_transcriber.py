import argparse
from pathlib import Path
from typing import Iterable

from faster_whisper import WhisperModel
from faster_whisper.transcribe import Segment
import numpy as np
from pathlib_extensions import OverwriteMode, overwrite_existing_path

from youtube_whisperer.adaptors.whisper_adaptor import WhisperSegmentAdaptor
from youtube_whisperer.transcriber.model_parameters import get_default_whisper_model_parameters
from youtube_whisperer.transcriber.waveform_loader import load_whisper_waveform_from_file
from youtube_whisperer.utils import TranscriberMode, verify_language_code


def transcribe_waveform(model: WhisperModel, waveform: np.ndarray, mode: TranscriberMode, **kwargs) -> Iterable[Segment]:
    """
    Transcribe the given waveform using the provided WhisperModel.

    Args:
        model (WhisperModel): The Whisper model to use for transcription.
        waveform (np.ndarray): The waveform to transcribe.
        mode (TranscriberMode): Whether to run Whisper in transcribe mode or translate mode.
        kwargs: Additional arguments to pass to `model.transcribe()`.

    Returns:
        Iterable[Segment]: An iterable of Segments of the transcription.
    """
    segments_generator, info = model.transcribe(waveform, task=mode.value, **kwargs)
    print(info)
    return segments_generator


def transcribe_waveform_with_default_model(waveform: np.ndarray, mode: TranscriberMode, **kwargs) -> Iterable[Segment]:
    """
    Transcribe the given waveform using the default WhisperModel.

    Args:
        waveform (np.ndarray): The waveform to transcribe.
        mode (TranscriberMode): Whether to run Whisper in transcribe mode or translate mode.
        kwargs: Additional arguments to pass to `model.transcribe()`.

    Returns:
        Iterable[Segment]: An iterable of Segments of the transcription.
    """
    model = WhisperModel(**get_default_whisper_model_parameters())
    return transcribe_waveform(model, waveform, mode, **kwargs)


def early_stopper(segments_generator: Iterable[Segment]) -> Iterable[Segment]:
    """
    Stop transcription upon a known error case.
    """
    for x in segments_generator:
        print(x)
        if x.text == '请不吝点赞 订阅 转发 打赏支持明镜与点点栏目':
            return
        yield x


def transcribe_file_with_default_model(input_file_path: Path, output_file_path: Path | None = None, overwrite: OverwriteMode = OverwriteMode.PROMPT, mode: TranscriberMode = TranscriberMode.TRANSCRIBE, **kwargs) -> Path | None:
    """
    Transcribe a waveform file using default model parameters and save the output to an SRT file.

    Args:
        input_file_path (Path): The path to the input file containing the waveform.
        output_file_path (Path | None, optional): The path to the output SRT file. If `None`, it will be the input file path with a `.srt` extension. Defaults to `None`.
        overwrite (OverwriteMode, optional): Whether to overwrite existing SRT files. Defaults to `prompt`.
        mode (TranscriberMode, optional): Whether to run Whisper in transcribe mode or translate mode. Defaults to `transcribe`.
        kwargs: Additional arguments to pass to `model.transcribe()`.

    Returns:
        Path | None: The path to the output SRT file, or `None` if transcription failed.
    """
    # Whisper only supports translation to English
    if kwargs.get('language') == 'en' and mode == TranscriberMode.TRANSLATE:
        print('Resetting Whisper mode to TRANSCRIBE because the language spoken in the waveform is English.')
        mode = TranscriberMode.TRANSCRIBE
    output_file_path = output_file_path or input_file_path.with_suffix('.srt')
    if output_file_path.is_file() and not overwrite_existing_path(output_file_path, overwrite):
        return output_file_path
    waveform = load_whisper_waveform_from_file(input_file_path)
    if len(waveform) == 0:
        print(f'Skipping {input_file_path} because empty waveform is loaded')
        return None
    try:
        segments_generator = early_stopper(transcribe_waveform_with_default_model(waveform, mode=mode, **kwargs))
        WhisperSegmentAdaptor(segments_generator).save_as_srt_file(output_file_path, overwrite=overwrite)
        return output_file_path
    except Exception as e:
        print(f"An error occurred while transcribing {input_file_path}: {e}")
        return None


def main() -> None:
    """
    CLI entry point to transcribe waveform files with Whisper and save each result to an SRT file.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", type=Path, nargs='+', metavar='path', help="Waveform file paths to transcribe.")
    parser.add_argument("-l", "--language", type=str, default=None, help="Language to transcribe waveform files. Defaults to auto detection.")
    parser.add_argument("-m", "--mode", type=TranscriberMode, choices=TranscriberMode.values(), default=TranscriberMode.TRANSCRIBE, help="Whether to run Whisper in transcribe mode or translate mode. Defaults to `transcribe`.")
    parser.add_argument("-o", "--overwrite", type=OverwriteMode, choices=OverwriteMode.values(), default=OverwriteMode.PROMPT, help="Whether to overwrite existing SRT files. Defaults to `prompt`.")
    args = parser.parse_args()
    language = args.language
    verify_language_code(language)
    mode = args.mode
    overwrite = args.overwrite
    for path in args.paths:
        transcribe_file_with_default_model(path, language=language, overwrite=overwrite, mode=mode)


if __name__ == "__main__":
    main()
