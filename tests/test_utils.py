import pytest

from youtube_whisperer.utils import is_url, redis_connection, strtobool


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


def test_redis_connection(mocker):
    mock_redis = mocker.patch('redis.StrictRedis')
    mock_client = mock_redis.return_value
    mock_client.ping.return_value = True
    with redis_connection() as client:
        assert client == mock_client
        mock_client.ping.assert_called_once()
    mock_client.close.assert_called_once()
