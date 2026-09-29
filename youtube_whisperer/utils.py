import atexit
from pathlib import Path
from typing import TYPE_CHECKING

import redis

from youtube_whisperer import domain
from youtube_whisperer.config import Settings

if TYPE_CHECKING:
    from youtube_whisperer.runtime import Runtime

TranscriberType = domain.TranscriberType
is_url = domain.is_url


def create_redis_pool(settings: Settings | None = None) -> redis.ConnectionPool:
    """Build the shared Redis connection pool from settings.

    socket_timeout must stay None: workers issue blocking XREADGROUP ... BLOCK reads that
    legitimately keep the socket idle for the whole poll window. redis-py 8.0 changed the
    default from None to 5s, which would race the BLOCK timeout and raise spurious
    TimeoutError. health_check_interval still detects dead connections.

    Args:
        settings: Supplied snapshot, or environment settings resolved at invocation.

    Returns:
        redis.ConnectionPool: A connection pool targeting the configured Redis endpoint.
    """
    settings = settings if settings is not None else Settings()
    return redis.ConnectionPool(
        host=settings.redis_host,
        port=settings.redis_port,
        socket_timeout=None,
        socket_connect_timeout=5,
        health_check_interval=60,
    )


_compat_runtime: "Runtime | None" = None


def __getattr__(name: str) -> Path | redis.ConnectionPool | redis.StrictRedis:
    """Resolve legacy exports only on explicit access, never ordinary import.

    Path exports resolve current settings on each access. Redis exports share a
    lazy compatibility runtime until process exit; application runtimes do not use it.

    Args:
        name: Legacy resource or configured-path export.

    Returns:
        The requested configured path, shared client or connection pool.

    Raises:
        AttributeError: If the export is unknown.
    """
    global _compat_runtime
    if name in ('WHISPER_ASSETS_DIR', 'WHISPER_MODELS_DIR'):
        settings = Settings()
        return settings.whisper_assets_dir if name == 'WHISPER_ASSETS_DIR' else settings.whisper_models_dir
    if name in ('REDIS_POOL', 'REDIS_CLIENT'):
        if _compat_runtime is None:
            from youtube_whisperer.runtime import Runtime

            _compat_runtime = Runtime()
            atexit.register(_compat_runtime.close)
        return _compat_runtime.client if name == 'REDIS_CLIENT' else _compat_runtime.client.connection_pool
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
