import pytest

from youtube_whisperer.transcribe import strtobool, get_default_whisper_model_parameters


def test_strtobool_true():
    assert strtobool('y') == True
    assert strtobool('yes') == True
    assert strtobool('t') == True
    assert strtobool('true') == True
    assert strtobool('on') == True
    assert strtobool('1') == True

def test_strtobool_false():
    assert strtobool('n') == False
    assert strtobool('no') == False
    assert strtobool('f') == False
    assert strtobool('false') == False
    assert strtobool('off') == False
    assert strtobool('0') == False

def test_strtobool_invalid():
    with pytest.raises(ValueError):
        strtobool('invalid')


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
