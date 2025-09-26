import json
from pathlib import Path

import pytest
from pathlib_extensions import OverwriteMode

from youtube_whisperer.adaptors.lang_code_adaptor import LanguageCode
import youtube_whisperer.worker as testee
from youtube_whisperer.utils import TranscriberMode, TranscriberType


@pytest.fixture
def mock_redis(mocker):
    mock_redis_client = mocker.MagicMock()
    mock_redis_connection = mocker.patch('youtube_whisperer.worker.redis_connection')
    mock_redis_connection.return_value.__enter__.return_value = mock_redis_client
    return mock_redis_client


def test_process_queue_url_with_no_transcript(mocker, mock_redis):
    mocker.patch('youtube_whisperer.worker.use_cuda', return_value=False)
    mock_sleep = mocker.patch('time.sleep')
    mock_is_url = mocker.patch('youtube_whisperer.worker.is_url', return_value=True)
    mock_download = mocker.patch(
        'youtube_whisperer.worker.download_video_and_transcript_with_default_title',
        return_value=(Path('/path/to/video.mp4'), False)  # no transcript
    )
    mock_transcribe = mocker.patch('youtube_whisperer.worker.transcribe_to_srt_files')
    task = {'source': 'http://example.com/video.mp4', 'language': 'en', 'transcriber': TranscriberType.LOCAL.value, 'mode': TranscriberMode.TRANSCRIBE.value}
    task_json = json.dumps(task)
    mock_redis.lrange.side_effect = [
        [task_json.encode('utf-8')],
        [],
        StopIteration,
    ]
    mock_redis.lpop.return_value = task_json.encode('utf-8')
    with pytest.raises(StopIteration):
        testee.process_queue(check_interval_seconds=1)
    assert mock_redis.lrange.call_count == 3
    mock_redis.lrange.assert_any_call('tasks', 0, 0)
    mock_redis.lpop.assert_called_once_with('tasks')
    mock_sleep.assert_called_once_with(1)

    mock_is_url.assert_called_once_with(task['source'])
    mock_download.assert_called_once_with(task['source'], LanguageCode(task['language']), overwrite=OverwriteMode.NEVER)
    mock_transcribe.assert_called_once_with([Path('/path/to/video.mp4')], LanguageCode(task['language']), mode=TranscriberMode(task['mode']), overwrite=OverwriteMode.NEVER)


def test_process_queue_url_with_transcript(mocker, mock_redis):
    mocker.patch('youtube_whisperer.worker.use_cuda', return_value=False)
    mock_sleep = mocker.patch('time.sleep')
    mocker.patch('youtube_whisperer.worker.is_url', return_value=True)
    mock_download = mocker.patch(
        'youtube_whisperer.worker.download_video_and_transcript_with_default_title',
        return_value=(Path('/path/to/video.mp4'), True)  # transcript found
    )
    mock_transcribe = mocker.patch('youtube_whisperer.worker.transcribe_to_srt_files')
    task = {'source': 'http://example.com/video.mp4', 'language': 'en', 'transcriber': TranscriberType.LOCAL.value, 'mode': TranscriberMode.TRANSCRIBE.value}
    task_json = json.dumps(task)
    mock_redis.lrange.side_effect = [
        [task_json.encode('utf-8')],
        [],
        StopIteration,
    ]
    mock_redis.lpop.return_value = task_json.encode('utf-8')
    with pytest.raises(StopIteration):
        testee.process_queue(check_interval_seconds=1)
    assert mock_redis.lrange.call_count == 3
    mock_redis.lrange.assert_any_call('tasks', 0, 0)
    mock_redis.lpop.assert_called_once_with('tasks')
    mock_sleep.assert_called_once_with(1)
    mock_download.assert_called_once()
    mock_transcribe.assert_not_called()


def test_process_queue_local_file(mocker, mock_redis):
    mocker.patch('youtube_whisperer.worker.use_cuda', return_value=False)
    mock_sleep = mocker.patch('time.sleep')
    mock_is_url = mocker.patch('youtube_whisperer.worker.is_url', return_value=False)
    mock_download = mocker.patch('youtube_whisperer.worker.download_video_and_transcript_with_default_title')
    mock_transcribe = mocker.patch('youtube_whisperer.worker.transcribe_to_srt_files')
    task = {'source': '/path/to/local/video.mp4', 'language': 'en', 'transcriber': TranscriberType.LOCAL.value, 'mode': TranscriberMode.TRANSCRIBE.value}
    task_json = json.dumps(task)
    mock_redis.lrange.side_effect = [
        [task_json.encode('utf-8')],
        [],
        StopIteration,
    ]
    mock_redis.lpop.return_value = task_json.encode('utf-8')
    with pytest.raises(StopIteration):
        testee.process_queue(check_interval_seconds=1)
    assert mock_redis.lrange.call_count == 3
    mock_redis.lrange.assert_any_call('tasks', 0, 0)
    mock_redis.lpop.assert_called_once_with('tasks')
    mock_sleep.assert_called_once_with(1)
    mock_is_url.assert_called_once_with(task['source'])
    mock_download.assert_not_called()
    mock_transcribe.assert_called_once_with([Path(task['source'])], LanguageCode(task['language']), mode=TranscriberMode(task['mode']), overwrite=OverwriteMode.NEVER)
