from pathlib import Path
from unittest import mock

from youtube_whisperer.model_parameters import get_default_cuda_flag, get_default_whisper_model_parameters


@mock.patch('ctranslate2.get_cuda_device_count')
def test_get_default_cuda_flag_with_env_var(mock_get_cuda_device_count, monkeypatch):
    monkeypatch.setenv("ASR_USE_CUDA", "true")
    assert get_default_cuda_flag() is True
    mock_get_cuda_device_count.assert_not_called()


@mock.patch('ctranslate2.get_cuda_device_count', return_value=0)
def test_get_default_cuda_flag_without_env_var_cpu(mock_get_cuda_device_count, monkeypatch):
    monkeypatch.delenv("ASR_USE_CUDA", raising=False)
    assert get_default_cuda_flag() is False
    mock_get_cuda_device_count.assert_called_once()


@mock.patch('ctranslate2.get_cuda_device_count', return_value=1)
def test_get_default_cuda_flag_without_env_var_cuda(mock_get_cuda_device_count, monkeypatch):
    monkeypatch.delenv("ASR_USE_CUDA", raising=False)
    assert get_default_cuda_flag() is True
    mock_get_cuda_device_count.assert_called_once()


def test_get_default_whisper_model_parameters_with_env_var_cpu(monkeypatch, mocker):
    monkeypatch.setenv("ASR_MODEL", "small")
    monkeypatch.setenv("ASR_MODEL_PATH", "test/path")
    monkeypatch.setenv("ASR_USE_CUDA", "false")
    mocker.patch('multiprocessing.cpu_count', return_value=8)
    assert get_default_whisper_model_parameters() == {
        "model_size_or_path": "small",
        "download_root": "test/path",
        "device": "cpu",
        "compute_type": "int8",
        "cpu_threads": 8,
    }


def test_get_default_whisper_model_parameters_with_env_var_cuda(monkeypatch):
    monkeypatch.setenv("ASR_MODEL", "small")
    monkeypatch.setenv("ASR_MODEL_PATH", "test/path")
    monkeypatch.setenv("ASR_USE_CUDA", "true")
    assert get_default_whisper_model_parameters() == {
        "model_size_or_path": "small",
        "download_root": "test/path",
        "device": "cuda",
        "compute_type": "float32",
    }


def test_get_default_whisper_model_parameters_without_env_var_cpu(mocker):
    mocker.patch('youtube_whisperer.model_parameters.get_default_cuda_flag', return_value=False)
    mocker.patch('pathlib.Path.home', return_value=Path("/test"))
    mocker.patch('multiprocessing.cpu_count', return_value=8)
    assert get_default_whisper_model_parameters() == {
        "model_size_or_path": "large-v3",
        "download_root": "/test/.whisper",
        "device": "cpu",
        "compute_type": "int8",
        "cpu_threads": 8,
    }


def test_get_default_whisper_model_parameters_without_env_var_cuda(mocker):
    mocker.patch('youtube_whisperer.model_parameters.get_default_cuda_flag', return_value=True)
    mocker.patch('pathlib.Path.home', return_value=Path("/test"))
    assert get_default_whisper_model_parameters() == {
        "model_size_or_path": "large-v3",
        "download_root": "/test/.whisper",
        "device": "cuda",
        "compute_type": "float32",
    }
