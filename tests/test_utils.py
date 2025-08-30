from pathlib import Path
import pytest

import youtube_whisperer.utils as testee
from youtube_whisperer.utils import TranscriberMode, TranscriberType, get_redis_client, is_url, load_and_get_env_vars, strtobool


def test_transcriber_type_values():
    assert TranscriberType.values() == ('local', 'azure')


def test_transcriber_mode_values():
    assert TranscriberMode.values() == ('transcribe', 'translate')


@pytest.mark.parametrize("input_text, expected", [
    ("y", True),
    ("yes", True),
    ("t", True),
    ("true", True),
    ("on", True),
    ("1", True),
])
def test_strtobool_true(input_text, expected):
    assert strtobool(input_text) is expected


@pytest.mark.parametrize("input_text, expected", [
    ("n", False),
    ("no", False),
    ("f", False),
    ("false", False),
    ("off", False),
    ("0", False),
])
def test_strtobool_false(input_text, expected):
    assert strtobool(input_text) is expected


@pytest.mark.parametrize("input_text", [
    "invalid",
    "maybe",
    "2",
    "yesno",
])
def test_strtobool_invalid(input_text):
    with pytest.raises(ValueError):
        strtobool(input_text)


@pytest.mark.parametrize("input_text, expected", [
    ("http://example.com", True),
    ("https://example.com", True),
    ("http://www.example.com", True),
    ("https://www.example.com", True),
    ("http://example.com/path?query=1", True),
    ("https://example.com/path?query=1", True),
    ("ftp://example.com", False),
    ("example.com", False),
    ("http:/example.com", False),
    ("http://", False),
    ("", False),
    ("not a url", False),
])
def test_is_url(input_text, expected):
    assert is_url(input_text) == expected


def test_get_redis_client(mocker):
    mock_redis = mocker.patch('redis.StrictRedis')
    mock_client = mock_redis.return_value
    mock_client.ping.return_value = True
    client = get_redis_client()
    mock_redis.assert_called_once_with(host='redis', socket_connect_timeout=5, health_check_interval=60)
    mock_client.ping.assert_called_once()
    assert client == mock_client


def test_load_and_get_env_vars_no_keys():
    with pytest.raises(AssertionError):
        load_and_get_env_vars()


def test_load_and_get_env_vars_missing_env_file(mocker):
    mocker.patch('dotenv.find_dotenv', return_value='')
    with pytest.raises(FileNotFoundError):
        load_and_get_env_vars('TEST_VAR')


def test_load_and_get_env_vars_missing_env_var(mocker):
    mocker.patch.object(testee, 'prepare_input_file', return_value=Path('/fake/.env'))
    mocker.patch('dotenv.load_dotenv', return_value=True)
    mocker.patch.dict('os.environ', {})
    with pytest.raises(KeyError):
        load_and_get_env_vars('NONEXISTENT_VAR')


def test_load_and_get_env_vars_single_var(mocker):
    mocker.patch.object(testee, 'prepare_input_file', return_value=Path('/fake/.env'))
    mocker.patch('dotenv.load_dotenv', return_value=True)
    mocker.patch.dict('os.environ', {'TEST_VAR': 'test_value'})
    result = load_and_get_env_vars('TEST_VAR')
    assert result == 'test_value'


def test_load_and_get_env_vars_multiple_vars(mocker):
    mocker.patch.object(testee, 'prepare_input_file', return_value=Path('/fake/.env'))
    mocker.patch('dotenv.load_dotenv', return_value=True)
    env_vars = {'VAR1': 'value1', 'VAR2': 'value2', 'VAR3': 'value3'}
    mocker.patch.dict('os.environ', env_vars)
    result = load_and_get_env_vars('VAR1', 'VAR2', 'VAR3')
    assert result == ['value1', 'value2', 'value3']
