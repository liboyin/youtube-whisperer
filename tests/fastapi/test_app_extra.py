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


def test_add_tasks_raises_http_500_when_redis_fails(mocker):
    from youtube_whisperer.fastapi.models import Task
    redis_client = mocker.MagicMock()
    redis_client.rpush.side_effect = RuntimeError("redis down")
    task = Task(source="http://example.com/video", language="en")
    mocker.patch("youtube_whisperer.fastapi.app.resolve_tasks", return_value=[task])

    with pytest.raises(HTTPException, match="redis down"):
        asyncio.run(testee.add_tasks([task], redis_client=redis_client))


def test_clear_tasks_raises_http_500_when_redis_fails(mocker):
    redis_client = mocker.MagicMock()
    redis_client.lrange.side_effect = RuntimeError("redis down")

    with pytest.raises(HTTPException, match="redis down"):
        asyncio.run(testee.clear_tasks(redis_client=redis_client))


def test_add_assets_catches_individual_file_write_failure(mocker, tmp_path):
    mock_upload = mocker.MagicMock()
    mock_upload.filename = "test.txt"
    bad_path = mocker.MagicMock()
    bad_path.open.side_effect = OSError("disk full")
    mocker.patch("youtube_whisperer.fastapi.app.prepare_output_file", return_value=bad_path)

    result = asyncio.run(testee.add_assets([mock_upload], dir_path=tmp_path))

    assert result.failed == ["test.txt"]
    assert result.successful == []


def test_add_assets_raises_http_500_when_filename_is_missing(mocker, tmp_path):
    mock_upload = mocker.MagicMock()
    mock_upload.filename = None

    with pytest.raises(HTTPException):
        asyncio.run(testee.add_assets([mock_upload], dir_path=tmp_path))


def test_clean_assets_raises_http_500_when_directory_listing_fails():
    bad_dir = Path("/definitely/missing")

    with pytest.raises(HTTPException, match="No such file or directory"):
        asyncio.run(testee.clean_assets(dir_path=bad_dir))
