import pytest
from pydantic import ValidationError

import youtube_whisperer.fastapi_app as testee
from youtube_whisperer.utils import WhisperMode


def test_task_source_validator():
    task = testee.Task(source="  http://example.com/video  ")
    assert task.source == "http://example.com/video"
    with pytest.raises(ValidationError):
        testee.Task(source="  ")


def test_task_language_validator():
    task = testee.Task(language="en")
    assert task.language == "en"
    with pytest.raises(ValidationError):
        testee.Task(language="")
    with pytest.raises(ValidationError):
        testee.Task(language="unsupported")


def test_task_mode_validator():
    task = testee.Task(mode="transcribe")
    assert task.mode == WhisperMode.TRANSCRIBE
    task = testee.Task(mode=WhisperMode.TRANSLATE)
    assert task.mode == WhisperMode.TRANSLATE
    with pytest.raises(ValidationError):
        testee.Task(mode="invalid_mode")


@pytest.fixture
def mock_dependencies(mocker):
    mock_is_url = mocker.patch('youtube_whisperer.fastapi_app.is_url')
    mock_yield_urls = mocker.patch('youtube_whisperer.fastapi_app.yield_flattened_video_urls')
    mock_glob = mocker.patch('youtube_whisperer.fastapi_app.glob.glob')
    return mock_is_url, mock_yield_urls, mock_glob


def test_resolve_tasks_with_url(mock_dependencies):
    mock_is_url, mock_yield_urls, _ = mock_dependencies
    mock_is_url.return_value = True
    mock_yield_urls.return_value = ['http://example.com/video1', 'http://example.com/video2']
    pattern = testee.Task(source='http://example.com/playlist', language='en')
    result = testee.resolve_tasks(pattern)
    assert len(result) == 2
    assert result[0].source == 'http://example.com/video1'
    assert result[1].source == 'http://example.com/video2'
    mock_is_url.assert_called_once_with('http://example.com/playlist')
    mock_yield_urls.assert_called_once_with(['http://example.com/playlist'])


def test_resolve_tasks_with_local_path(mock_dependencies):
    mock_is_url, _, mock_glob = mock_dependencies
    mock_is_url.return_value = False
    mock_glob.return_value = ['/path/to/file1.mkv', '/path/to/file2.mkv']
    pattern = testee.Task(source='/path/to/*.mkv', language='fr')
    result = testee.resolve_tasks(pattern)
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
    pattern = testee.Task(source='nonexistent_pattern', language='es')
    result = testee.resolve_tasks(pattern)
    assert len(result) == 0
    mock_is_url.assert_called_once_with('nonexistent_pattern')
    mock_glob.assert_called_once_with('nonexistent_pattern')
