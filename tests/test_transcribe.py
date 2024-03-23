import numpy as np
from youtube_whisperer.transcribe import get_default_whisper_model_parameters, transcribe, transcribe_with_default_model


def test_get_default_whisper_model_parameters_cpu(mocker):
    mocker.patch('os.getenv', return_value='test')
    mocker.patch('ctranslate2.get_cuda_device_count', return_value=0)
    mocker.patch('multiprocessing.cpu_count', return_value=8)
    result = get_default_whisper_model_parameters()
    assert result['model_size_or_path'] == 'test'
    assert result['download_root'] == 'test'
    assert result['device'] == 'cpu'
    assert result['compute_type'] == 'int8'
    assert result["cpu_threads"] == 8


def test_get_default_whisper_model_parameters_gpu(mocker):
    mocker.patch('os.getenv', return_value='test')
    mocker.patch('ctranslate2.get_cuda_device_count', return_value=1)
    result = get_default_whisper_model_parameters()
    assert result['model_size_or_path'] == 'test'
    assert result['download_root'] == 'test'
    assert result['device'] == 'cuda'
    assert result['compute_type'] == 'float32'
