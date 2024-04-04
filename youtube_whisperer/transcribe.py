import multiprocessing
import os
from pathlib import Path
from typing import Any, Iterable, Generator

import ctranslate2
from faster_whisper import WhisperModel
from faster_whisper.transcribe import Segment
from faster_whisper.utils import format_timestamp
import numpy as np

from utils import strtobool


def get_default_cuda_flag() -> bool:
    """
    This function checks the environment variable ASR_USE_CUDA to determine whether to use CUDA for GPU acceleration.
    If the environment variable is not set, it checks if there is a CUDA device available on the system.
    If a CUDA device is available, it returns True; otherwise, it returns False.

    Returns:
        bool: True if CUDA should be used, False otherwise.
    """
    gpu = os.getenv("ASR_USE_CUDA", None)
    if gpu is None:
        return ctranslate2.get_cuda_device_count() > 0
    return strtobool(gpu)


def get_default_whisper_model_parameters() -> dict[str, Any]:
    """
    Get the default parameters for the WhisperModel.

    The parameters are determined based on the environment variables and the available hardware.

    Returns:
        dict: A dictionary containing the parameters for the WhisperModel.
    """
    result: dict[str, Any] = {
        "model_size_or_path": os.getenv("ASR_MODEL", "large-v3"),
        "download_root": os.getenv("ASR_MODEL_PATH", str(Path.home() / ".whisper")),
    }
    use_cuda = get_default_cuda_flag()
    result["device"] = "cuda" if use_cuda else "cpu"
    # More about available quantization levels is here: https://opennmt.net/CTranslate2/quantization.html
    if use_cuda:
        result["compute_type"] = "float32"
    else:
        result["compute_type"] = "int8"
        result["cpu_threads"] = multiprocessing.cpu_count()
    return result


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
