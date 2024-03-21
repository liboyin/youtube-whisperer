import os
from pathlib import Path
from typing import Any

from faster_whisper import WhisperModel
import numpy as np
import torch


def get_model(model_name: str, model_path: str, device: str, quantization: str) -> WhisperModel:
    return WhisperModel(
        model_size_or_path=model_name,
        download_root=model_path,
        device=device,
        compute_type=quantization,
    )


def get_model_parameters_from_env() -> dict[str, str]:
    device = os.getenv("ASR_DEVICE", "cuda" if torch.cuda.is_available() else "cpu")
    quantization = os.getenv("ASR_QUANTIZATION", None)
    if not quantization:
        # More about available quantization levels is here: https://opennmt.net/CTranslate2/quantization.html
        if device == "cuda":
            quantization = "float32"
        elif device == "cpu":
            quantization = "int8"
        else:
            raise ValueError(f"Unknown device: {device}")
    return {
        "model_name": os.getenv("ASR_MODEL", "large-v3"),
        "model_path": os.getenv("ASR_MODEL_PATH", str(Path.home() / ".cache" / "whisper")),
        "device": device,
        "quantization": quantization,
    }


def transcribe(model: WhisperModel, waveform: np.ndarray, language: str) -> dict[str, Any]:
    segment_generator, _ = model.transcribe(waveform, beam_size=5, task='transcribe', language=language)
    return {"segments": list(segment_generator)}


def transcribe_with_model_from_env(waveform: np.ndarray, language: str) -> dict[str, Any]:
    model = get_model(**get_model_parameters_from_env())
    return transcribe(model, waveform, language)
