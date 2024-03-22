import multiprocessing
import os
from pathlib import Path
from typing import Any

from ctranslate2 import get_cuda_device_count
from faster_whisper import WhisperModel
import numpy as np

def get_default_whisper_model_parameters() -> dict[str, Any]:
    result = {
        "model_size_or_path": os.getenv("ASR_MODEL", "large-v3"),
        "download_root": os.getenv("ASR_MODEL_PATH", str(Path.home() / ".cache" / "whisper")),
    }
    result["device"] = device = "cuda" if get_cuda_device_count() else "cpu"
    # More about available quantization levels is here: https://opennmt.net/CTranslate2/quantization.html
    if device == "cuda":
        result["compute_type"] = "float32"
    elif device == "cpu":
        result["compute_type"] = "int8"
        result["cpu_threads"] = multiprocessing.cpu_count()
    else:
        raise ValueError(f"Unknown device: {device}")
    return result

def transcribe(model: WhisperModel, waveform: np.ndarray, language: str) -> dict[str, Any]:
    segment_generator, _ = model.transcribe(waveform, beam_size=5, task='transcribe', language=language)
    return {"segments": list(segment_generator)}

def transcribe_with_default_model(waveform: np.ndarray, language: str) -> dict[str, Any]:
    model = WhisperModel(**get_default_whisper_model_parameters())
    return transcribe(model, waveform, language)