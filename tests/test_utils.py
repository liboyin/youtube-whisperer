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


def test_create_redis_pool_defaults_observe_current_settings(monkeypatch):
    """Invocation defaults observe current endpoint and preserve blocking-read options."""
    for host, port in [('first.invalid', 6381), ('second.invalid', 6382)]:
        monkeypatch.setenv('REDIS_HOST', host)
        monkeypatch.setenv('REDIS_PORT', str(port))
        pool = testee.create_redis_pool()
        try:
            assert pool.connection_kwargs['host'] == host
            assert pool.connection_kwargs['port'] == port
            assert pool.connection_kwargs['socket_timeout'] is None
            assert pool.connection_kwargs['socket_connect_timeout'] == 5
            assert pool.connection_kwargs['health_check_interval'] == 60
        finally:
            pool.disconnect()


def test_collected_settings_use_synthetic_environment():
    """Test that collection never retains inherited settings or host paths."""
    settings = testee.Settings()
    assert settings.redis_host == 'queue.test.invalid'
    assert settings.redis_port == 6389
    assert settings.azure_speech_api_key is None
    assert settings.azure_service_region is None
    assert testee.WHISPER_ASSETS_DIR == Path(os.environ['WHISPER_ASSETS_DIR'])
    assert testee.WHISPER_MODELS_DIR == Path(os.environ['WHISPER_MODELS_DIR'])
    assert testee.WHISPER_ASSETS_DIR.is_relative_to(Path(os.environ['HOME']))
    assert testee.WHISPER_MODELS_DIR.is_relative_to(Path(os.environ['HOME']))


@pytest.mark.parametrize('host, port', [
    ('queue-one.invalid', 6381),
    ('queue-two.invalid', 6382),
])
def test_exported_redis_client_uses_configured_pool_in_fresh_process(tmp_path, host, port):
    """Test lazy explicit Redis wiring under isolated settings without network access."""
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
        utils._compat_runtime.close()
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



def test_lazy_redis_exports_share_only_test_owned_compatibility_runtime(mocker, monkeypatch):
    """Explicit Redis exports initialize once without leaking cache state or exit callbacks."""
    import youtube_whisperer.runtime as runtime_testee

    assert testee._compat_runtime is None
    monkeypatch.setattr(testee, '_compat_runtime', None)
    owner = mocker.Mock()
    factory = mocker.patch.object(runtime_testee, 'Runtime', return_value=owner)
    register = mocker.patch.object(testee.atexit, 'register')
    settings = mocker.patch.object(testee, 'Settings', side_effect=AssertionError('ambient settings'))
    try:
        assert testee.REDIS_CLIENT is owner.client
        assert testee.REDIS_POOL is owner.client.connection_pool
        assert testee.REDIS_CLIENT is owner.client
        factory.assert_called_once_with()
        register.assert_called_once_with(owner.close)
        settings.assert_not_called()
    finally:
        owner.close()
        testee._compat_runtime = None
    owner.close.assert_called_once_with()

def test_lazy_path_exports_observe_invocation_settings_without_redis(monkeypatch, tmp_path, mocker):
    """Explicit path access resolves owned environment without initializing Redis compatibility."""
    constructor = mocker.patch.object(testee.redis, 'StrictRedis', side_effect=AssertionError('client construction'))
    for name in ['first', 'second']:
        monkeypatch.setenv('WHISPER_ASSETS_DIR', str(tmp_path / name / 'assets'))
        monkeypatch.setenv('WHISPER_MODELS_DIR', str(tmp_path / name / 'models'))
        assert testee.WHISPER_ASSETS_DIR == tmp_path / name / 'assets'
        assert testee.WHISPER_MODELS_DIR == tmp_path / name / 'models'
    constructor.assert_not_called()


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


def test_ordinary_runtime_imports_construct_no_ambient_resources(tmp_path):
    """Fresh imports trap Settings and Redis construction before any compatibility access."""
    script = '''
from unittest.mock import patch
import pydantic_settings
import redis
import ctranslate2
from faster_whisper import WhisperModel

with patch.object(pydantic_settings.BaseSettings, '__init__', side_effect=AssertionError('Settings construction')), \
     patch.object(redis.ConnectionPool, '__init__', side_effect=AssertionError('pool construction')), \
     patch.object(redis.StrictRedis, '__init__', side_effect=AssertionError('client construction')), \
     patch.object(WhisperModel, '__init__', side_effect=AssertionError('model construction')), \
     patch.object(ctranslate2, 'get_cuda_device_count', side_effect=AssertionError('GPU probe')):
    import youtube_whisperer.utils
    import youtube_whisperer.runtime
    import youtube_whisperer.api.app
    import youtube_whisperer.workers.__main__
    import youtube_whisperer.downloaders
    import youtube_whisperer.downloaders.playlist_downloader
    import youtube_whisperer.downloaders.transcript_downloader
    import youtube_whisperer.downloaders.video_downloader
    import youtube_whisperer.transcriber.azure_transcriber
    import youtube_whisperer.transcriber.whisper_transcriber
    assert youtube_whisperer.utils._compat_runtime is None
'''
    environment = {
        'HOME': str(tmp_path), 'TMPDIR': str(tmp_path),
        'PYTHONPATH': str(Path(__file__).resolve().parents[1]),
        'PYTHONDONTWRITEBYTECODE': '1',
        'WHISPER_ASSETS_DIR': str(tmp_path / 'assets'),
        'WHISPER_MODELS_DIR': str(tmp_path / 'models'),
        'WHISPER_USE_CUDA': 'false', 'WHISPER_MODEL': 'import-test',
        'REDIS_HOST': 'import.test.invalid', 'REDIS_PORT': '6384',
    }
    result = subprocess.run(
        [sys.executable, '-c', script], cwd=tmp_path, env=environment,
        capture_output=True, text=True, timeout=15, check=False,
    )
    assert result.returncode == 0, result.stderr
