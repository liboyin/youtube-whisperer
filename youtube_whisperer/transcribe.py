import multiprocessing
import os
from pathlib import Path
from typing import Any

import ctranslate2
from faster_whisper import WhisperModel
import numpy as np


def strtobool(val: str) -> bool:
    """
    Convert a string representation of truth (case insensitive) to boolean type.

    Replaces distutils.util.strtobool, which is no longer included in the standard library since Python 3.10.

    True values are 'y', 'yes', 't', 'true', 'on', and '1'.
    False values are 'n', 'no', 'f', 'false', 'off', and '0'.
    Raises ValueError if 'val' is anything else.
    """
    match val.lower():
        case 'y' | 'yes' | 't' | 'true' | 'on' | '1':
            return True
        case 'n' | 'no' | 'f' | 'false' | 'off' | '0':
            return False
        case _:
            raise ValueError(f"invalid truth value '{val}' of type {type(val)}")


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


def transcribe(model: WhisperModel, waveform: np.ndarray, language: str) -> dict[str, Any]:
    """
    Transcribe the given waveform using the provided WhisperModel.

    Args:
        model (WhisperModel): The model to use for transcription.
        waveform (np.ndarray): The waveform to transcribe.
        language (str): The language of the waveform.

    Returns:
        dict: A dictionary containing the transcribed segments.
    """
    segment_generator, _ = model.transcribe(waveform, beam_size=5, task='transcribe', language=language)
    return {"segments": list(segment_generator)}


def transcribe_with_default_model(waveform: np.ndarray, language: str) -> dict[str, Any]:
    """
    Transcribe the given waveform using the default WhisperModel.

    Args:
        waveform (np.ndarray): The waveform to transcribe.
        language (str): The language of the waveform.

    Returns:
        dict: A dictionary containing the transcribed segments.
    """
    model = WhisperModel(**get_default_whisper_model_parameters())
    return transcribe(model, waveform, language)
