import multiprocessing
import pprint
from typing import Any

import ctranslate2

from youtube_whisperer.config import Settings


def get_default_cuda_flag() -> bool:
    """
    Determines whether to use CUDA for GPU acceleration.

    Returns:
        bool: True if CUDA should be used, False otherwise.
    """
    gpu = Settings().whisper_use_cuda
    if gpu is None:
        return ctranslate2.get_cuda_device_count() > 0
    return gpu


def get_default_whisper_model_parameters() -> dict[str, Any]:
    """
    Returns default parameters for the WhisperModel.

    The parameters are determined based on the environment variables and the available hardware.
    """
    settings = Settings()
    result: dict[str, Any] = {
        "model_size_or_path": settings.whisper_model,
        "download_root": str(settings.whisper_models_dir),
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


if __name__ == "__main__":
    pprint.pprint(get_default_whisper_model_parameters())
