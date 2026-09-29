from unittest.mock import Mock, patch

import pytest

import youtube_whisperer.runtime as testee


@pytest.fixture
def settings(tmp_path):
    """Own a complete settings snapshot independent of inherited configuration."""
    return testee.Settings(
        whisper_assets_dir=tmp_path / 'assets', whisper_models_dir=tmp_path / 'models',
        redis_host='runtime.test.invalid', redis_port=6382, whisper_use_cuda=False,
    )


def test_runtime_binds_supplied_settings_paths_and_client_without_construction(settings, monkeypatch):
    """Two runtimes retain their own snapshot and borrowed client after environment changes."""
    second = settings.model_copy(update={
        'whisper_assets_dir': settings.whisper_assets_dir.parent / 'second-assets',
        'whisper_models_dir': settings.whisper_models_dir.parent / 'second-models',
        'worker_claim_min_idle_seconds': 29,
    })
    clients = [Mock(), Mock()]
    with patch.object(testee, 'Settings', side_effect=AssertionError('ambient settings')), \
            patch.object(testee, 'create_redis_pool', side_effect=AssertionError('pool construction')), \
            testee.Runtime(settings, clients[0]) as first, testee.Runtime(second, clients[1]) as other:
        monkeypatch.setenv('WHISPER_ASSETS_DIR', str(settings.whisper_assets_dir.parent / 'changed'))
        monkeypatch.setenv('WORKER_CLAIM_MIN_IDLE_SECONDS', '999')
        assert first.settings is settings and other.settings is second
        assert first.client is clients[0] and other.client is clients[1]
        assert first.assets_dir == settings.whisper_assets_dir
        assert other.assets_dir == second.whisper_assets_dir
        assert first.models_dir == settings.whisper_models_dir
        assert other.models_dir == second.whisper_models_dir
        assert other.settings.worker_claim_min_idle_seconds == 29
    for client in clients:
        client.close.assert_not_called()


def test_runtime_default_settings_resolve_at_each_invocation(settings, monkeypatch):
    """Successive standalone owners observe current owned environment settings."""
    monkeypatch.setenv('WHISPER_MODEL', 'first')
    with testee.Runtime(client=Mock()) as first:
        monkeypatch.setenv('WHISPER_MODEL', 'second')
        with testee.Runtime(client=Mock()) as second:
            assert first.settings.whisper_model == 'first'
            assert second.settings.whisper_model == 'second'


@pytest.mark.parametrize('supplied_pool, owns_pool', [(False, False), (True, False), (True, True)])
def test_runtime_closes_created_client_and_only_owned_pool(settings, supplied_pool, owns_pool):
    """Created clients close independently of the supplied pool's ownership policy."""
    pool, client = Mock(), Mock()
    with patch.object(testee, 'create_redis_pool', return_value=pool) as factory, \
            patch.object(testee.redis, 'StrictRedis', return_value=client) as constructor:
        runtime = testee.Runtime(settings, pool=pool if supplied_pool else None, owns_pool=owns_pool)
        runtime.close()
        runtime.close()
    constructor.assert_called_once_with(connection_pool=pool)
    if supplied_pool:
        factory.assert_not_called()
    else:
        factory.assert_called_once_with(settings)
    client.close.assert_called_once_with()
    if not supplied_pool or owns_pool:
        pool.disconnect.assert_called_once_with()
    else:
        pool.disconnect.assert_not_called()


@pytest.mark.parametrize('failure', [None, RuntimeError('borrowed'), KeyboardInterrupt('borrowed')])
@pytest.mark.parametrize('owns_pool', [False, True])
def test_runtime_does_not_close_borrowed_client_or_implicitly_owned_pool(settings, owns_pool, failure):
    """Borrowed clients stay open while explicitly transferred pool ownership is honored."""
    from contextlib import nullcontext

    pool, client = Mock(), Mock()
    expected = pytest.raises(type(failure), match='borrowed') if failure is not None else nullcontext()
    with expected, testee.Runtime(settings, client, pool=pool, owns_pool=owns_pool):
        if failure is not None:
            raise failure
    client.close.assert_not_called()
    assert pool.disconnect.call_count == int(owns_pool)


@pytest.mark.parametrize('failure', [RuntimeError('startup'), KeyboardInterrupt('startup')])
@pytest.mark.parametrize('supplied_pool, owns_pool', [(False, False), (True, False), (True, True)])
def test_runtime_disconnects_owned_pool_when_client_construction_fails(settings, failure, supplied_pool, owns_pool):
    """Client startup failure and interruption disconnect every owned pool and no borrowed pool."""
    pool = Mock()
    with patch.object(testee, 'create_redis_pool', return_value=pool), \
            patch.object(testee.redis, 'StrictRedis', side_effect=failure), \
            pytest.raises(type(failure), match='startup'):
        testee.Runtime(settings, pool=pool if supplied_pool else None, owns_pool=owns_pool)
    assert pool.disconnect.call_count == int(not supplied_pool or owns_pool)


@pytest.mark.parametrize('failure', [RuntimeError('body'), KeyboardInterrupt('body'), SystemExit('body')])
def test_runtime_closes_created_resources_after_execution_failure(settings, failure):
    """Runtime execution failures including BaseException release created client and pool."""
    pool, client = Mock(), Mock()
    with patch.object(testee, 'create_redis_pool', return_value=pool), \
            patch.object(testee.redis, 'StrictRedis', return_value=client), \
            pytest.raises(type(failure), match='body'), testee.Runtime(settings):
        raise failure
    client.close.assert_called_once_with()
    pool.disconnect.assert_called_once_with()


@pytest.mark.parametrize('failure', [RuntimeError('close'), KeyboardInterrupt('close')])
def test_runtime_disconnects_owned_pool_even_when_client_close_fails(settings, failure):
    """Client cleanup failure cannot skip explicit disconnection of its owned pool."""
    pool, client = Mock(), Mock()
    client.close.side_effect = failure
    with patch.object(testee, 'create_redis_pool', return_value=pool), \
            patch.object(testee.redis, 'StrictRedis', return_value=client):
        runtime = testee.Runtime(settings)
        with pytest.raises(type(failure), match='close'):
            runtime.close()
        runtime.close()
    client.close.assert_called_once_with()
    pool.disconnect.assert_called_once_with()
