from types import SimpleNamespace

import pytest

import youtube_whisperer.utils as testee


def test_create_redis_pool_uses_configured_endpoint():
    """Test that the Redis pool targets the host and port from settings so the endpoint is configurable."""
    settings = SimpleNamespace(redis_host="example-host", redis_port=6380)

    pool = testee.create_redis_pool(settings)

    assert pool.connection_kwargs["host"] == "example-host"
    assert pool.connection_kwargs["port"] == 6380
    # socket_timeout must stay None so blocking XREADGROUP reads are not raced by redis-py's default.
    assert pool.connection_kwargs["socket_timeout"] is None


def test_redis_pool_defaults_to_compose_service_endpoint():
    """Test that the shared Redis pool defaults to the compose service host and standard port."""
    assert testee.REDIS_POOL.connection_kwargs["host"] == "redis"
    assert testee.REDIS_POOL.connection_kwargs["port"] == 6379


def test_transcriber_type_values():
    """Test that the transcriber enum exposes the supported transcriber names."""
    assert testee.TranscriberType.values() == ('whisper', 'azure')


def test_transcriber_type_rejects_legacy_local_alias():
    """Test that the legacy local transcriber alias is rejected."""
    with pytest.raises(ValueError, match="'local' is not a valid TranscriberType"):
        testee.TranscriberType('local')


def test_transcriber_mode_values():
    """Test that the transcriber mode enum exposes the supported mode names."""
    assert testee.TranscriberMode.values() == ('transcribe', 'translate')


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
    """Test that URL detection distinguishes valid HTTP URLs from other strings."""
    assert testee.is_url(input_text) == expected
