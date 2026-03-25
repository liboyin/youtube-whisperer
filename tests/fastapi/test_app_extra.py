import asyncio
from pathlib import Path

import pytest
from fastapi import HTTPException

import youtube_whisperer.fastapi.app as testee


def test_get_assets_dir_returns_configured_directory():
    assert testee.get_assets_dir() == testee.WHISPER_ASSETS_DIR


def test_get_redis_client_yields_configured_client():
    assert next(testee.get_redis_client()) is testee.REDIS_CLIENT


def test_get_tasks_raises_http_500_when_redis_fails(mocker):
    redis_client = mocker.MagicMock()
    redis_client.lrange.side_effect = RuntimeError("redis down")

    with pytest.raises(HTTPException, match="redis down"):
        asyncio.run(testee.get_tasks(redis_client=redis_client))


def test_list_assets_raises_http_500_when_directory_listing_fails():
    bad_dir = Path("/definitely/missing")

    with pytest.raises(HTTPException, match="No such file or directory"):
        asyncio.run(testee.list_assets(dir_path=bad_dir))
