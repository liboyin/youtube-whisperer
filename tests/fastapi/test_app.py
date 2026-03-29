import asyncio
from pathlib import Path
from unittest.mock import ANY, MagicMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from redis import StrictRedis

import youtube_whisperer.fastapi.app as testee
from youtube_whisperer.fastapi.models import DeadLetter, Task, TaskQueues
from youtube_whisperer.utils import TranscriberMode


@pytest.fixture
def mock_redis_client():
    mock_client = MagicMock(spec=StrictRedis)
    mock_client.lrange.return_value = []
    mock_client.rpush.return_value = 1
    mock_client.delete.return_value = 1
    mock_client.scan_iter.return_value = iter([])
    return mock_client


@pytest.fixture
def mock_assets_dir(tmp_path):
    return tmp_path


@pytest.fixture(autouse=True)
def override_dependencies(mock_redis_client, mock_assets_dir):
    testee.app.dependency_overrides[testee.get_redis_client] = lambda: mock_redis_client
    testee.app.dependency_overrides[testee.get_assets_dir] = lambda: mock_assets_dir
    yield
    testee.app.dependency_overrides = {}


@pytest.fixture
def client():
    return TestClient(testee.app)


def test_get_assets_dir_returns_configured_directory():
    """Test that the assets dependency returns the configured assets directory."""
    assert testee.get_assets_dir() == testee.WHISPER_ASSETS_DIR


def test_get_redis_client_yields_configured_client():
    """Test that the Redis dependency yields the configured Redis client."""
    assert next(testee.get_redis_client()) is testee.REDIS_CLIENT


def test_get_tasks_returns_queue_snapshot(client, mocker):
    """Test that the tasks endpoint returns the grouped queue snapshot."""
    queue_snapshot = TaskQueues(youtube=[], whisper_pending=[], whisper_active=[], azure_pending=[], azure_active=[])
    mock_list = mocker.patch.object(testee, 'list_task_queues', return_value=queue_snapshot)

    response = client.get("/tasks")

    assert response.status_code == 200
    assert response.json() == queue_snapshot.model_dump(mode='json')
    mock_list.assert_called_once()


def test_get_tasks_raises_http_500_when_queue_lookup_fails(mocker):
    """Test that task lookup failures are surfaced as HTTP 500 errors."""
    redis_client = mocker.MagicMock()
    mocker.patch.object(testee, 'list_task_queues', side_effect=RuntimeError("redis down"))

    with pytest.raises(HTTPException, match="redis down"):
        asyncio.run(testee.get_tasks(redis_client=redis_client))


def test_resolve_filesystem_tasks_expands_globs(mocker):
    """Test that filesystem task expansion expands glob patterns and preserves metadata."""
    pattern = Task(source='/tmp/*.wav', language='en')
    mock_glob = mocker.patch.object(testee.glob, 'glob', return_value=['/tmp/one.wav', '/tmp/two.wav'])

    result = testee.resolve_filesystem_tasks(pattern)

    assert [task.source for task in result] == ['/tmp/one.wav', '/tmp/two.wav']
    assert all(task.language == pattern.language for task in result)
    mock_glob.assert_called_once_with('/tmp/*.wav')


def test_model_copy_preserves_non_source_fields():
    """Test that copying a task with a new source preserves its other fields."""
    pattern = Task(source='https://example.com/playlist', language='en', mode=TranscriberMode.TRANSLATE)

    result = pattern.model_copy(update={'source': 'https://example.com/video1'})

    assert result.source == 'https://example.com/video1'
    assert result.language == pattern.language
    assert result.transcriber == pattern.transcriber
    assert result.mode == pattern.mode


def test_add_tasks_routes_youtube_and_whisper_work(client, mocker):
    """Test that the add-tasks endpoint splits YouTube and filesystem work correctly."""
    url_task = Task(source='https://example.com/video', language='en')
    resolved_whisper_task = Task(source='/tmp/audio.wav', language='en')
    mocker.patch.object(testee, 'is_url', side_effect=lambda source: source.startswith('http'))
    mock_resolve_filesystem = mocker.patch.object(testee, 'resolve_filesystem_tasks', return_value=[resolved_whisper_task])
    mock_queue_youtube_task = mocker.patch.object(testee, 'queue_youtube_task')
    mock_queue_transcription_tasks = mocker.patch.object(testee, 'queue_transcription_tasks')

    response = client.post(
        "/tasks",
        json=[
            url_task.model_dump(mode='json'),
            Task(source='/tmp/*.wav', language='en').model_dump(mode='json'),
        ],
    )

    assert response.status_code == 201
    assert response.json() == {
        'successful': [url_task.model_dump(mode='json'), resolved_whisper_task.model_dump(mode='json')],
        'failed': [],
    }
    mock_resolve_filesystem.assert_called_once()
    mock_queue_youtube_task.assert_called_once_with(ANY, url_task)
    mock_queue_transcription_tasks.assert_called_once_with(ANY, [resolved_whisper_task])


def test_add_tasks_failed_resolution(client, mocker):
    """Test that unresolved filesystem tasks are returned in the failed list."""
    task = Task(source='/tmp/*.wav', language='en')
    mocker.patch.object(testee, 'is_url', return_value=False)
    mocker.patch.object(testee, 'resolve_filesystem_tasks', return_value=[])
    mock_queue_youtube_task = mocker.patch.object(testee, 'queue_youtube_task')
    mock_queue_transcription_tasks = mocker.patch.object(testee, 'queue_transcription_tasks')

    response = client.post("/tasks", json=[task.model_dump(mode='json')])

    assert response.status_code == 201
    assert response.json() == {'successful': [], 'failed': [task.model_dump(mode='json')]}
    mock_queue_youtube_task.assert_not_called()
    mock_queue_transcription_tasks.assert_not_called()


def test_add_tasks_raises_http_500_when_queueing_fails(mocker):
    """Test that queueing failures in add_tasks are surfaced as HTTP 500 errors."""
    redis_client = mocker.MagicMock()
    task = Task(source="/tmp/audio.wav", language="en")
    mocker.patch.object(testee, 'is_url', return_value=False)
    mocker.patch.object(testee, 'resolve_filesystem_tasks', return_value=[task])
    mocker.patch.object(testee, 'queue_transcription_tasks', side_effect=RuntimeError("redis down"))

    with pytest.raises(HTTPException, match="redis down"):
        asyncio.run(testee.add_tasks([task], redis_client=redis_client))


def test_clear_tasks_returns_deleted_queue_snapshot(client, mocker):
    """Test that deleting tasks returns the snapshot of removed queue contents."""
    queue_snapshot = TaskQueues(youtube=[], whisper_pending=[], whisper_active=[], azure_pending=[], azure_active=[])
    mock_clear = mocker.patch.object(testee, 'clear_task_queues', return_value=queue_snapshot)

    response = client.delete("/tasks")

    assert response.status_code == 200
    assert response.json() == queue_snapshot.model_dump(mode='json')
    mock_clear.assert_called_once()


def test_clear_tasks_raises_http_500_when_queue_clearing_fails(mocker):
    """Test that task-clearing failures are surfaced as HTTP 500 errors."""
    redis_client = mocker.MagicMock()
    mocker.patch.object(testee, 'clear_task_queues', side_effect=RuntimeError("redis down"))

    with pytest.raises(HTTPException, match="redis down"):
        asyncio.run(testee.clear_tasks(redis_client=redis_client))


def test_get_dead_letters_returns_queue_contents(client, mocker):
    """Test that the dead-letter endpoint returns the queued dead-letter entries."""
    dead_letter = DeadLetter(task=Task(source='/tmp/audio.wav', language='en'), queue='stream:whisper', error='boom')
    mock_list = mocker.patch.object(testee, 'list_dead_letters', return_value=[dead_letter])

    response = client.get("/dead-letters")

    assert response.status_code == 200
    assert response.json() == [dead_letter.model_dump(mode='json')]
    mock_list.assert_called_once()


def test_get_dead_letters_raises_http_500_when_lookup_fails(mocker):
    """Test that dead-letter lookup failures are surfaced as HTTP 500 errors."""
    redis_client = mocker.MagicMock()
    mocker.patch.object(testee, 'list_dead_letters', side_effect=RuntimeError("redis down"))

    with pytest.raises(HTTPException, match="redis down"):
        asyncio.run(testee.get_dead_letters(redis_client=redis_client))


def test_clear_dead_letters_returns_deleted_items(client, mocker, mock_redis_client):
    """Test that clearing dead letters returns the deleted entries and removes the queue key."""
    dead_letter = DeadLetter(task=Task(source='/tmp/audio.wav', language='en'), queue='stream:whisper', error='boom')
    mock_list = mocker.patch.object(testee, 'list_dead_letters', return_value=[dead_letter])

    response = client.delete("/dead-letters")

    assert response.status_code == 200
    assert response.json() == [dead_letter.model_dump(mode='json')]
    mock_list.assert_called_once()
    mock_redis_client.delete.assert_called_once_with(testee.DEAD_LETTER_QUEUE)


def test_clear_dead_letters_raises_http_500_when_delete_fails(mocker):
    """Test that dead-letter clearing failures are surfaced as HTTP 500 errors."""
    redis_client = mocker.MagicMock()
    mocker.patch.object(testee, 'list_dead_letters', side_effect=RuntimeError("redis down"))

    with pytest.raises(HTTPException, match="redis down"):
        asyncio.run(testee.clear_dead_letters(redis_client=redis_client))


def test_list_assets_empty(client):
    """Test that the assets endpoint returns an empty list when no files exist."""
    response = client.get("/assets")

    assert response.status_code == 200
    assert response.json() == []


def test_list_assets_with_files(client, mock_assets_dir):
    """Test that the assets endpoint lists files present in the assets directory."""
    (mock_assets_dir / "file1.txt").touch()
    (mock_assets_dir / "file2.txt").touch()

    response = client.get("/assets")

    assert response.status_code == 200
    assert sorted(response.json()) == [str(mock_assets_dir / "file1.txt"), str(mock_assets_dir / "file2.txt")]


def test_list_assets_raises_http_500_when_directory_listing_fails():
    """Test that asset-listing failures are surfaced as HTTP 500 errors."""
    bad_dir = Path("/definitely/missing")

    with pytest.raises(HTTPException, match="No such file or directory"):
        asyncio.run(testee.list_assets(dir_path=bad_dir))


def test_add_assets(client, mock_assets_dir):
    """Test that uploaded asset files are saved and reported as successful."""
    files = [
        ("file1.txt", b"content1"),
        ("file2.txt", b"content2"),
    ]
    upload_files = [("files", (name, content, "text/plain")) for name, content in files]

    response = client.post("/assets", files=upload_files)

    assert response.status_code == 201
    response_json = response.json()
    assert len(response_json["successful"]) == 2
    assert len(response_json["failed"]) == 0
    assert str(mock_assets_dir / "file1.txt") in response_json["successful"]
    assert str(mock_assets_dir / "file2.txt") in response_json["successful"]
    assert (mock_assets_dir / "file1.txt").read_bytes() == b"content1"
    assert (mock_assets_dir / "file2.txt").read_bytes() == b"content2"


def test_add_assets_catches_individual_file_write_failure(mocker, tmp_path):
    """Test that individual asset write failures are reported without crashing the request."""
    mock_upload = mocker.MagicMock()
    mock_upload.filename = "test.txt"
    bad_path = mocker.MagicMock()
    bad_path.open.side_effect = OSError("disk full")
    mocker.patch("youtube_whisperer.fastapi.app.prepare_output_file", return_value=bad_path)

    result = asyncio.run(testee.add_assets([mock_upload], dir_path=tmp_path))

    assert result.failed == ["test.txt"]
    assert result.successful == []


def test_add_assets_raises_http_500_when_filename_is_missing(mocker, tmp_path):
    """Test that uploads without filenames raise an HTTP 500 error."""
    mock_upload = mocker.MagicMock()
    mock_upload.filename = None

    with pytest.raises(HTTPException):
        asyncio.run(testee.add_assets([mock_upload], dir_path=tmp_path))


def test_clean_assets(client, mock_assets_dir):
    """Test that cleaning assets removes only transient media files."""
    (mock_assets_dir / "video.mp4").touch()
    (mock_assets_dir / "video.srt").touch()
    (mock_assets_dir / "video.mkv").touch()
    (mock_assets_dir / "video.wav").touch()
    (mock_assets_dir / "video.mp3").touch()
    (mock_assets_dir / "another.mp4").touch()

    response = client.delete("/assets")

    assert response.status_code == 200
    removed_files = response.json()
    assert len(removed_files) == 3
    assert str(mock_assets_dir / "video.mkv") in removed_files
    assert str(mock_assets_dir / "video.wav") in removed_files
    assert str(mock_assets_dir / "video.mp3") in removed_files
    assert not (mock_assets_dir / "video.mkv").exists()
    assert not (mock_assets_dir / "video.wav").exists()
    assert not (mock_assets_dir / "video.mp3").exists()
    assert (mock_assets_dir / "video.mp4").exists()
    assert (mock_assets_dir / "video.srt").exists()
    assert (mock_assets_dir / "another.mp4").exists()


def test_clean_assets_raises_http_500_when_directory_listing_fails():
    """Test that asset-cleaning listing failures are surfaced as HTTP 500 errors."""
    bad_dir = Path("/definitely/missing")

    with pytest.raises(HTTPException, match="No such file or directory"):
        asyncio.run(testee.clean_assets(dir_path=bad_dir))
