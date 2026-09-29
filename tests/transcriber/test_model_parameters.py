from unittest import mock

import pytest

import youtube_whisperer.transcriber.model_parameters as testee


@pytest.fixture
def model_cache_dir(tmp_path, monkeypatch):
    """Own the model-cache setting for each parameter test."""
    cache_dir = tmp_path / 'models'
    monkeypatch.setenv('WHISPER_MODELS_DIR', str(cache_dir))
    return cache_dir


@mock.patch('ctranslate2.get_cuda_device_count')
def test_get_default_cuda_flag_with_env_var(mock_get_cuda_device_count, monkeypatch):
    """Test that the WHISPER_USE_CUDA env var overrides hardware probing."""
    monkeypatch.setenv("WHISPER_USE_CUDA", "true")
    assert testee.get_default_cuda_flag() is True
    mock_get_cuda_device_count.assert_not_called()


@mock.patch('ctranslate2.get_cuda_device_count', return_value=0)
def test_get_default_cuda_flag_without_env_var_cpu(mock_get_cuda_device_count, monkeypatch):
    """Test that absent CUDA devices fall back to CPU when the env var is unset."""
    monkeypatch.delenv("WHISPER_USE_CUDA", raising=False)
    assert testee.get_default_cuda_flag() is False
    mock_get_cuda_device_count.assert_called_once()


@mock.patch('ctranslate2.get_cuda_device_count', return_value=1)
def test_get_default_cuda_flag_without_env_var_cuda(mock_get_cuda_device_count, monkeypatch):
    """Test that a present CUDA device enables GPU when the env var is unset."""
    monkeypatch.delenv("WHISPER_USE_CUDA", raising=False)
    assert testee.get_default_cuda_flag() is True
    mock_get_cuda_device_count.assert_called_once()


def test_supplied_auto_cuda_snapshot_probes_hardware_without_environment_override(mocker, monkeypatch):
    """Hardware auto-detection remains available when the supplied snapshot requests it."""
    settings = testee.Settings(whisper_use_cuda=None)
    monkeypatch.setenv('WHISPER_USE_CUDA', 'false')
    probe = mocker.patch.object(testee.ctranslate2, 'get_cuda_device_count', return_value=2)
    assert testee.get_default_cuda_flag(settings) is True
    probe.assert_called_once_with()


def test_get_default_whisper_model_parameters_with_env_var_cpu(monkeypatch, mocker, model_cache_dir):
    """Test that CPU parameters use int8 compute and the detected CPU thread count."""
    monkeypatch.setenv("WHISPER_MODEL", "test_model")
    monkeypatch.setenv("WHISPER_USE_CUDA", "false")
    mocker.patch('multiprocessing.cpu_count', return_value=8)
    assert testee.get_default_whisper_model_parameters() == {
        "model_size_or_path": "test_model",
        "download_root": str(model_cache_dir),
        "device": "cpu",
        "compute_type": "int8",
        "cpu_threads": 8,
    }


def test_get_default_whisper_model_parameters_with_env_var_cuda(monkeypatch, model_cache_dir):
    """Test that CUDA parameters use float32 compute and omit the CPU thread count."""
    monkeypatch.setenv("WHISPER_MODEL", "test_model")
    monkeypatch.setenv("WHISPER_USE_CUDA", "true")
    assert testee.get_default_whisper_model_parameters() == {
        "model_size_or_path": "test_model",
        "download_root": str(model_cache_dir),
        "device": "cuda",
        "compute_type": "float32",
    }


def test_get_default_whisper_model_parameters_without_env_var_cpu(monkeypatch, mocker, model_cache_dir):
    """Test that CPU parameters are derived when the CUDA flag resolves to False."""
    monkeypatch.setenv("WHISPER_MODEL", "test_model")
    mocker.patch.object(testee, 'get_default_cuda_flag', return_value=False)
    mocker.patch('multiprocessing.cpu_count', return_value=8)
    assert testee.get_default_whisper_model_parameters() == {
        "model_size_or_path": "test_model",
        "download_root": str(model_cache_dir),
        "device": "cpu",
        "compute_type": "int8",
        "cpu_threads": 8,
    }


def test_get_default_whisper_model_parameters_without_env_var_cuda(monkeypatch, mocker, model_cache_dir):
    """Test that CUDA parameters are derived when the CUDA flag resolves to True."""
    monkeypatch.setenv('WHISPER_MODEL', "test_model")
    mocker.patch.object(testee, 'get_default_cuda_flag', return_value=True)
    assert testee.get_default_whisper_model_parameters() == {
        "model_size_or_path": "test_model",
        "download_root": str(model_cache_dir),
        "device": "cuda",
        "compute_type": "float32",
    }


def test_supplied_snapshot_controls_model_cache_device_and_threads(monkeypatch, tmp_path, mocker):
    """CPU and CUDA parameters derive wholly from the supplied snapshot."""
    snapshots = [testee.Settings(
        whisper_model=name, whisper_models_dir=tmp_path / name, whisper_use_cuda=cuda,
    ) for name, cuda in [('one', False), ('two', True)]]
    probe = mocker.patch.object(testee.ctranslate2, 'get_cuda_device_count', side_effect=AssertionError('GPU probe'))
    mocker.patch.object(testee.multiprocessing, 'cpu_count', return_value=7)
    monkeypatch.setenv('WHISPER_MODEL', 'changed')
    monkeypatch.setenv('WHISPER_MODELS_DIR', str(tmp_path / 'changed'))
    for snapshot, expected in zip(snapshots, [
        {'device': 'cpu', 'compute_type': 'int8', 'cpu_threads': 7},
        {'device': 'cuda', 'compute_type': 'float32'},
    ], strict=True):
        assert testee.get_default_whisper_model_parameters(snapshot) == {
            'model_size_or_path': snapshot.whisper_model,
            'download_root': str(snapshot.whisper_models_dir), **expected,
        }
    probe.assert_not_called()
