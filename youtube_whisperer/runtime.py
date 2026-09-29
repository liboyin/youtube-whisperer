"""Concrete ownership of a runtime's settings, paths and Redis resources."""

from types import TracebackType

import redis
from typing_extensions import Self

from youtube_whisperer.config import Settings
from youtube_whisperer.utils import create_redis_pool


class Runtime:
    """Bind one settings snapshot to resources with explicit cleanup ownership."""

    def __init__(
        self,
        settings: Settings | None = None,
        client: redis.StrictRedis | None = None,
        *,
        pool: redis.ConnectionPool | None = None,
        owns_pool: bool = False,
    ) -> None:
        """Resolve configuration once and create only missing Redis resources.

        Args:
            settings: Supplied snapshot, or environment settings resolved now.
            client: Borrowed client; it is never closed by this owner.
            pool: Borrowed pool, unless ownership is explicitly transferred.
            owns_pool: Whether a supplied pool must be disconnected on exit.

        Raises:
            BaseException: Construction failure, after disconnecting an owned pool.
        """
        self.settings = settings if settings is not None else Settings()
        self.assets_dir = self.settings.whisper_assets_dir
        self.models_dir = self.settings.whisper_models_dir
        self.pool = pool
        self._owns_client = client is None
        self._owns_pool = owns_pool if pool is not None else client is None
        self._closed = False
        if client is None:
            if self.pool is None:
                self.pool = create_redis_pool(self.settings)
            try:
                client = redis.StrictRedis(connection_pool=self.pool)
            except BaseException:
                if self._owns_pool:
                    self.pool.disconnect()
                raise
        self.client = client

    def close(self) -> None:
        """Close created clients and disconnect owned pools, once, even if close fails."""
        if self._closed:
            return
        self._closed = True
        try:
            if self._owns_client:
                self.client.close()
        finally:
            if self._owns_pool and self.pool is not None:
                self.pool.disconnect()

    def __enter__(self) -> Self:
        """Return this owner for a bounded runtime execution scope."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Release owned resources on normal completion or any interruption.

        Args:
            exc_type: Active exception type, if execution failed.
            exc_value: Active exception, propagated rather than suppressed.
            traceback: Execution traceback, left unchanged by this owner.
        """
        self.close()
