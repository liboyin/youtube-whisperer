from pathlib import Path

from pathlib_extensions import OverwriteMode

from youtube_whisperer.models import Task
from youtube_whisperer.utils import TranscriberMode, TranscriberType
import youtube_whisperer.workers.youtube_worker as testee


def test_youtube_worker_stream_bindings(mocker):
    """Test that YouTube bindings natively map consumer names properly."""
    worker = testee.YouTubeWorker('test-slot')
    assert worker.get_consumer_name() == 'test-slot'
    assert worker.get_stream_name() == testee.YOUTUBE_STREAM

    from youtube_whisperer.queueing import WORKERS_GROUP
    mock_yield = mocker.patch('youtube_whisperer.workers.common.yield_task')
    worker.yield_tasks(10)
    mock_yield.assert_called_once_with(
        client=testee.REDIS_CLIENT,
        stream_name=testee.YOUTUBE_STREAM,
        group_name=WORKERS_GROUP,
        consumer_name='test-slot',
        poll_interval_seconds=10
    )


def test_dispatch_task_queues_follow_up_transcription_tasks(mocker):
    """Test that the YouTube worker only queues follow-up work for files still missing an SRT."""
    task = Task(
        source='https://example.com/playlist',
        language='en',
        transcriber=TranscriberType.AZURE,
        mode=TranscriberMode.TRANSLATE,
    )
    mocker.patch.object(testee, 'yield_flattened_video_urls', return_value=iter(['https://example.com/video-1', 'https://example.com/video-2']))
    mock_download = mocker.patch.object(
        testee,
        'download_video_and_transcript_with_default_title',
        side_effect=[
            (Path('/tmp/video-1.mp4'), True),
            (Path('/tmp/video-2.mp4'), False),
        ],
    )
    mock_queue_transcription_tasks = mocker.patch.object(testee, 'queue_transcription_tasks')

    testee.YouTubeWorker('youtube-0').process_task(task)

    assert mock_download.call_count == 2
    mock_download.assert_any_call('https://example.com/video-1', task.language, overwrite=OverwriteMode.NEVER)
    mock_download.assert_any_call('https://example.com/video-2', task.language, overwrite=OverwriteMode.NEVER)

    mock_queue_transcription_tasks.assert_called_once_with(
        testee.REDIS_CLIENT,
        [
            Task(
                source='/tmp/video-2.mp4',
                language='en',
                transcriber=TranscriberType.AZURE,
                mode=TranscriberMode.TRANSLATE,
            )
        ],
    )
