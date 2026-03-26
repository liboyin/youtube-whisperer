from unittest import mock

import youtube_whisperer.transcriber.model_parameters as testee
from youtube_whisperer.utils import WHISPER_MODELS_DIR


@mock.patch('ctranslate2.get_cuda_device_count')
def test_get_default_cuda_flag_with_env_var(mock_get_cuda_device_count, monkeypatch):
    monkeypatch.setenv("WHISPER_USE_CUDA", "true")
    assert testee.get_default_cuda_flag() is True
    mock_get_cuda_device_count.assert_not_called()


@mock.patch('ctranslate2.get_cuda_device_count', return_value=0)
def test_get_default_cuda_flag_without_env_var_cpu(mock_get_cuda_device_count, monkeypatch):
    monkeypatch.delenv("WHISPER_USE_CUDA", raising=False)
    assert testee.get_default_cuda_flag() is False
    mock_get_cuda_device_count.assert_called_once()


@mock.patch('ctranslate2.get_cuda_device_count', return_value=1)
def test_get_default_cuda_flag_without_env_var_cuda(mock_get_cuda_device_count, monkeypatch):
    monkeypatch.delenv("WHISPER_USE_CUDA", raising=False)
    assert testee.get_default_cuda_flag() is True
    mock_get_cuda_device_count.assert_called_once()


def test_get_default_whisper_model_parameters_with_env_var_cpu(monkeypatch, mocker):
    monkeypatch.setenv("WHISPER_MODEL", "test_model")
    monkeypatch.setenv("WHISPER_USE_CUDA", "false")
    mocker.patch('multiprocessing.cpu_count', return_value=8)
    assert testee.get_default_whisper_model_parameters() == {
        "model_size_or_path": "test_model",
        "download_root": str(WHISPER_MODELS_DIR),
        "device": "cpu",
        "compute_type": "int8",
        "cpu_threads": 8,
    }


def test_get_default_whisper_model_parameters_with_env_var_cuda(monkeypatch):
    monkeypatch.setenv("WHISPER_MODEL", "test_model")
    monkeypatch.setenv("WHISPER_USE_CUDA", "true")
    assert testee.get_default_whisper_model_parameters() == {
        "model_size_or_path": "test_model",
        "download_root": str(WHISPER_MODELS_DIR),
        "device": "cuda",
        "compute_type": "float32",
    }


def test_get_default_whisper_model_parameters_without_env_var_cpu(monkeypatch, mocker):
    monkeypatch.setenv("WHISPER_MODEL", "test_model")
    mocker.patch.object(testee, 'get_default_cuda_flag', return_value=False)
    mocker.patch('multiprocessing.cpu_count', return_value=8)
    assert testee.get_default_whisper_model_parameters() == {
        "model_size_or_path": "test_model",
        "download_root": str(WHISPER_MODELS_DIR),
        "device": "cpu",
        "compute_type": "int8",
        "cpu_threads": 8,
    }


def test_get_default_whisper_model_parameters_without_env_var_cuda(monkeypatch, mocker):
    monkeypatch.setenv('WHISPER_MODEL', "test_model")
    mocker.patch.object(testee, 'get_default_cuda_flag', return_value=True)
    assert testee.get_default_whisper_model_parameters() == {
        "model_size_or_path": "test_model",
        "download_root": str(WHISPER_MODELS_DIR),
        "device": "cuda",
        "compute_type": "float32",
    }
