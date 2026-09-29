import multiprocessing
from typing import TypedDict

import ctranslate2

from youtube_whisperer.config import Settings


class _RequiredModelParameters(TypedDict):
    """Resolved constructor values; CPU threads are absent for CUDA models."""

    model_size_or_path: str
    download_root: str
    device: str
    compute_type: str


class WhisperModelParameters(_RequiredModelParameters, total=False):
    """Constructor parameters with an optional CPU-only thread count."""

    cpu_threads: int


def get_default_cuda_flag(settings: Settings | None = None) -> bool:
    """
    Determines whether to use CUDA for GPU acceleration.

    Args:
        settings: Supplied snapshot, or environment settings resolved at invocation.

    Returns:
        bool: True if CUDA should be used, False otherwise.
    """
    settings = settings if settings is not None else Settings()
    gpu = settings.whisper_use_cuda
    if gpu is None:
        return ctranslate2.get_cuda_device_count() > 0
    return gpu


def get_default_whisper_model_parameters(settings: Settings | None = None) -> WhisperModelParameters:
    """
    Returns default parameters for the WhisperModel.

    Resolve one snapshot and preserve explicit CUDA overrides and hardware auto-probing.

    Args:
        settings: Supplied snapshot, or environment settings resolved at invocation.

    Returns:
        Constructor values with CPU int8/thread count or CUDA float32.
    """
    settings = settings if settings is not None else Settings()
    use_cuda = get_default_cuda_flag(settings)
    result: WhisperModelParameters = {
        "model_size_or_path": settings.whisper_model,
        "download_root": str(settings.whisper_models_dir),
        "device": "cuda" if use_cuda else "cpu",
        "compute_type": "float32" if use_cuda else "int8",
    }
    # More about available quantization levels is here: https://opennmt.net/CTranslate2/quantization.html
    if not use_cuda:
        result["cpu_threads"] = multiprocessing.cpu_count()
    return result
