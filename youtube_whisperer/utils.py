import redis

from youtube_whisperer import domain
from youtube_whisperer.config import Settings

TranscriberType = domain.TranscriberType
is_url = domain.is_url


def create_redis_pool(settings: Settings) -> redis.ConnectionPool:
    """Build the shared Redis connection pool from settings.

    socket_timeout must stay None: workers issue blocking XREADGROUP ... BLOCK reads that
    legitimately keep the socket idle for the whole poll window. redis-py 8.0 changed the
    default from None to 5s, which would race the BLOCK timeout and raise spurious
    TimeoutError. health_check_interval still detects dead connections.

    Args:
        settings (Settings): Application settings providing the Redis host and port.

    Returns:
        redis.ConnectionPool: A connection pool targeting the configured Redis endpoint.
    """
    return redis.ConnectionPool(
        host=settings.redis_host,
        port=settings.redis_port,
        socket_timeout=None,
        socket_connect_timeout=5,
        health_check_interval=60,
    )


_settings = Settings()
WHISPER_ASSETS_DIR = _settings.whisper_assets_dir
WHISPER_MODELS_DIR = _settings.whisper_models_dir
REDIS_POOL = create_redis_pool(_settings)
REDIS_CLIENT = redis.StrictRedis(connection_pool=REDIS_POOL)
