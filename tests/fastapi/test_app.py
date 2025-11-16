import pytest
from fastapi.testclient import TestClient
from redis import StrictRedis
from unittest.mock import MagicMock, patch

from youtube_whisperer.fastapi.app import app, get_redis, get_assets_dir, resolve_tasks
from youtube_whisperer.fastapi.models import Task, TranscriberMode


@pytest.fixture
def mock_dependencies(mocker):
    mock_is_url = mocker.patch('youtube_whisperer.fastapi.app.is_url')
    mock_yield_urls = mocker.patch('youtube_whisperer.fastapi.app.yield_flattened_video_urls')
    mock_glob = mocker.patch('youtube_whisperer.fastapi.app.glob.glob')
    return mock_is_url, mock_yield_urls, mock_glob


def test_resolve_tasks_with_url(mock_dependencies):
    mock_is_url, mock_yield_urls, _ = mock_dependencies
    mock_is_url.return_value = True
    mock_yield_urls.return_value = ['http://example.com/video1', 'http://example.com/video2']
    pattern = Task(source='http://example.com/playlist', language='en')
    result = resolve_tasks(pattern)
    assert len(result) == 2
    assert result[0].source == 'http://example.com/video1'
    assert result[1].source == 'http://example.com/video2'
    mock_is_url.assert_called_once_with('http://example.com/playlist')
    mock_yield_urls.assert_called_once_with(['http://example.com/playlist'])


def test_resolve_tasks_with_local_path(mock_dependencies):
    mock_is_url, _, mock_glob = mock_dependencies
    mock_is_url.return_value = False
    mock_glob.return_value = ['/path/to/file1.mkv', '/path/to/file2.mkv']
    pattern = Task(source='/path/to/*.mkv', language='en')
    result = resolve_tasks(pattern)
    assert len(result) == 2
    assert result[0].source == '/path/to/file1.mkv'
    assert result[1].source == '/path/to/file2.mkv'
    mock_is_url.assert_called_once_with('/path/to/*.mkv')
    mock_glob.assert_called_once_with('/path/to/*.mkv')


def test_resolve_tasks_no_match(mock_dependencies):
    mock_is_url, mock_yield_urls, mock_glob = mock_dependencies
    mock_is_url.return_value = False
    mock_yield_urls.return_value = []
    mock_glob.return_value = []
    pattern = Task(source='nonexistent_pattern', language='en')
    result = resolve_tasks(pattern)
    assert len(result) == 0
    mock_is_url.assert_called_once_with('nonexistent_pattern')
    mock_glob.assert_called_once_with('nonexistent_pattern')


@pytest.fixture
def mock_redis_client():
    mock_client = MagicMock(spec=StrictRedis)
    mock_client.lrange.return_value = []
    mock_client.rpush.return_value = 1
    mock_client.delete.return_value = 1
    return mock_client


@pytest.fixture
def mock_assets_dir(tmp_path):
    return tmp_path


@pytest.fixture(autouse=True)
def override_dependencies(mock_redis_client, mock_assets_dir):
    app.dependency_overrides[get_redis] = lambda: mock_redis_client
    app.dependency_overrides[get_assets_dir] = lambda: mock_assets_dir
    yield
    app.dependency_overrides = {}


@pytest.fixture
def client():
    return TestClient(app)


def test_get_tasks_empty(client, mock_redis_client):
    response = client.get("/tasks")
    assert response.status_code == 200
    assert response.json() == []
    mock_redis_client.lrange.assert_called_once_with('tasks', 0, -1)


def test_get_tasks_with_data(client, mock_redis_client):
    tasks_data = [
        Task(source="http://example.com/video1", language="zh", mode=TranscriberMode.TRANSCRIBE),
        Task(source="http://example.com/video2", language="en", mode=TranscriberMode.TRANSLATE),
    ]
    mock_redis_client.lrange.return_value = [task.model_dump_json().encode('utf-8') for task in tasks_data]
    response = client.get("/tasks")
    assert response.status_code == 200
    response_json = response.json()
    assert len(response_json) == 2
    assert response_json[0]["source"] == "http://example.com/video1"
    assert response_json[1]["source"] == "http://example.com/video2"
    mock_redis_client.lrange.assert_called_once_with('tasks', 0, -1)


def test_add_tasks(client, mock_redis_client):
    tasks_to_add = [
        {"source": "http://example.com/video1", "language": "en", "mode": "transcribe"}
    ]
    with patch('youtube_whisperer.fastapi.app.resolve_tasks') as mock_resolve_tasks:
        resolved_task = Task(source="http://example.com/video1", language="en", mode=TranscriberMode.TRANSCRIBE)
        mock_resolve_tasks.return_value = [resolved_task]
        response = client.post("/tasks", json=tasks_to_add)
    assert response.status_code == 201
    response_json = response.json()
    assert len(response_json["successful"]) == 1
    assert response_json["successful"][0]["source"] == "http://example.com/video1"
    assert len(response_json["failed"]) == 0
    mock_redis_client.rpush.assert_called_once_with('tasks', resolved_task.model_dump_json())


def test_add_tasks_failed_resolution(client, mock_redis_client):
    tasks_to_add = [
        {"source": "nonexistent", "language": "en", "mode": "transcribe"}
    ]
    with patch('youtube_whisperer.fastapi.app.resolve_tasks') as mock_resolve_tasks:
        mock_resolve_tasks.return_value = []
        response = client.post("/tasks", json=tasks_to_add)
    assert response.status_code == 201
    response_json = response.json()
    assert len(response_json["successful"]) == 0
    assert len(response_json["failed"]) == 1
    assert response_json["failed"][0]["source"] == "nonexistent"
    mock_redis_client.rpush.assert_not_called()


def test_clear_tasks(client, mock_redis_client):
    tasks_data = [
        Task(source="http://example.com/video1", language="en", mode=TranscriberMode.TRANSCRIBE),
    ]
    mock_redis_client.lrange.return_value = [task.model_dump_json().encode('utf-8') for task in tasks_data]
    response = client.delete("/tasks")
    assert response.status_code == 200
    response_json = response.json()
    assert len(response_json) == 1
    assert response_json[0]["source"] == "http://example.com/video1"
    mock_redis_client.lrange.assert_called_once_with('tasks', 0, -1)
    mock_redis_client.delete.assert_called_once_with('tasks')


def test_list_assets_empty(client):
    response = client.get("/assets")
    assert response.status_code == 200
    assert response.json() == []


def test_list_assets_with_files(client, mock_assets_dir):
    (mock_assets_dir / "file1.txt").touch()
    (mock_assets_dir / "file2.txt").touch()
    response = client.get("/assets")
    assert response.status_code == 200
    assert sorted(response.json()) == [str(mock_assets_dir / "file1.txt"), str(mock_assets_dir / "file2.txt")]


def test_add_assets(client, mock_assets_dir):
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


def test_clean_assets(client, mock_assets_dir):
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
