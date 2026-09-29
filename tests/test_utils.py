import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import youtube_whisperer.utils as testee
from youtube_whisperer.config import Settings


def test_create_redis_pool_uses_configured_endpoint():
    """Test that the Redis pool targets the host and port from settings so the endpoint is configurable."""
    settings = SimpleNamespace(redis_host="example-host", redis_port=6380)

    pool = testee.create_redis_pool(settings)
    try:
        assert pool.connection_kwargs["host"] == "example-host"
        assert pool.connection_kwargs["port"] == 6380
        # socket_timeout must stay None so blocking XREADGROUP reads are not raced by redis-py's default.
        assert pool.connection_kwargs["socket_timeout"] is None
    finally:
        pool.disconnect()


def test_redis_pool_defaults_to_compose_service_endpoint():
    """Test that declared Redis defaults configure a new, test-owned pool."""
    host = Settings.model_fields['redis_host'].default
    port = Settings.model_fields['redis_port'].default
    settings = SimpleNamespace(redis_host=host, redis_port=port)
    pool = testee.create_redis_pool(settings)
    try:
        assert pool.connection_kwargs["host"] == "redis"
        assert pool.connection_kwargs["port"] == 6379
    finally:
        pool.disconnect()


def test_collected_settings_use_synthetic_environment():
    """Test that collection never retains inherited settings or host paths."""
    assert testee._settings.redis_host == 'queue.test.invalid'
    assert testee._settings.redis_port == 6389
    assert testee._settings.azure_speech_api_key is None
    assert testee._settings.azure_service_region is None
    assert testee.WHISPER_ASSETS_DIR == Path(os.environ['WHISPER_ASSETS_DIR'])
    assert testee.WHISPER_MODELS_DIR == Path(os.environ['WHISPER_MODELS_DIR'])
    assert testee.WHISPER_ASSETS_DIR.is_relative_to(Path(os.environ['HOME']))
    assert testee.WHISPER_MODELS_DIR.is_relative_to(Path(os.environ['HOME']))


@pytest.mark.parametrize('host, port', [
    ('queue-one.invalid', 6381),
    ('queue-two.invalid', 6382),
])
def test_exported_redis_client_uses_configured_pool_in_fresh_process(tmp_path, host, port):
    """Test import-time Redis wiring under isolated settings without network access."""
    script = """
import os
import socket
from pathlib import Path
from unittest.mock import patch

with patch.object(socket, 'socket', side_effect=AssertionError('network access')):
    import youtube_whisperer.utils as utils
    try:
        assert utils.REDIS_POOL.connection_kwargs['host'] == os.environ['REDIS_HOST']
        assert utils.REDIS_POOL.connection_kwargs['port'] == int(os.environ['REDIS_PORT'])
        assert utils.REDIS_POOL.connection_kwargs['socket_timeout'] is None
        assert utils.REDIS_CLIENT.connection_pool is utils.REDIS_POOL
        assert utils.WHISPER_ASSETS_DIR == Path(os.environ['WHISPER_ASSETS_DIR'])
        assert utils.WHISPER_MODELS_DIR == Path(os.environ['WHISPER_MODELS_DIR'])
    finally:
        utils.REDIS_CLIENT.connection_pool.disconnect()
        utils.REDIS_POOL.disconnect()
"""
    environment = {
        'HOME': str(tmp_path),
        'PYTHONPATH': str(Path(__file__).resolve().parents[1]),
        'PYTHONDONTWRITEBYTECODE': '1',
        'TMPDIR': str(tmp_path),
        'REDIS_HOST': host,
        'REDIS_PORT': str(port),
        'WHISPER_ASSETS_DIR': str(tmp_path / 'assets'),
        'WHISPER_MODELS_DIR': str(tmp_path / 'models'),
    }

    result = subprocess.run(
        [sys.executable, '-c', script],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr


def test_removed_transcriber_mode_is_unavailable():
    """Test that the retired operation enum cannot be imported by Python callers."""
    assert not hasattr(testee, 'TranscriberMode')


def test_domain_exports_forward_the_same_objects():
    """Test that the established utils import paths retain canonical domain identities."""
    from youtube_whisperer import domain

    assert testee.TranscriberType is domain.TranscriberType
    assert testee.is_url is domain.is_url


def test_transcriber_type_values():
    """Test that the transcriber enum exposes the supported transcriber names, including download-only `none`."""
    assert testee.TranscriberType.values() == ('whisper', 'azure', 'none')


def test_transcriber_type_rejects_legacy_local_alias():
    """Test that the legacy local transcriber alias is rejected."""
    with pytest.raises(ValueError, match="'local' is not a valid TranscriberType"):
        testee.TranscriberType('local')


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
