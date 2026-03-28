from pathlib import Path

from youtube_whisperer.fastapi.models import Task
from youtube_whisperer.utils import TranscriberMode, TranscriberType
import youtube_whisperer.workers.youtube_worker as testee


def test_dispatch_task_queues_follow_up_transcription_tasks(mocker):
    """Test that the YouTube worker only queues follow-up work for files still missing an SRT."""
    task = Task(
        source='https://example.com/playlist',
        language='en',
        transcriber=TranscriberType.AZURE,
        mode=TranscriberMode.TRANSLATE,
    )
    mocker.patch.object(testee, 'yield_flattened_video_urls', return_value=iter(['https://example.com/video-1', 'https://example.com/video-2']))
    mock_resolve = mocker.patch.object(
        testee,
        'resolve_waveform_file_path',
        side_effect=[
            (Path('/tmp/video-1.mp4'), True),
            (Path('/tmp/video-2.mp4'), False),
        ],
    )
    mock_queue_tasks = mocker.patch.object(testee, 'queue_tasks')

    testee.dispatch_task(task)

    assert mock_resolve.call_args_list == [
        mocker.call(testee.copy_task_with_source(task, 'https://example.com/video-1')),
        mocker.call(testee.copy_task_with_source(task, 'https://example.com/video-2')),
    ]
    mock_queue_tasks.assert_called_once_with(
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


def test_process_queue_full_flow(mocker):
    """Test successful end-to-end processing of a YouTube queue task."""
    task = Task(source='https://example.com/playlist', language='en')
    mocker.patch.object(testee, 'yield_task', return_value=iter([task]))
    mock_dispatch = mocker.patch.object(testee, 'dispatch_task')
    mock_dead_letter = mocker.patch.object(testee, 'queue_dead_letter')
    mock_redis = mocker.patch.object(testee, 'REDIS_CLIENT')

    testee.process_queue()

    mock_dispatch.assert_called_once_with(task)
    mock_dead_letter.assert_not_called()
    mock_redis.lpop.assert_called_once_with(testee.YOUTUBE_QUEUE)


def test_process_queue_dead_letters_failures(mocker):
    """Test that YouTube queue failures are moved to the dead-letter queue."""
    task = Task(source='https://example.com/playlist', language='en')
    mocker.patch.object(testee, 'yield_task', return_value=iter([task]))
    mocker.patch.object(testee, 'dispatch_task', side_effect=RuntimeError('boom'))
    mock_dead_letter = mocker.patch.object(testee, 'queue_dead_letter')
    mock_redis = mocker.patch.object(testee, 'REDIS_CLIENT')

    testee.process_queue()

    mock_dead_letter.assert_called_once_with(mock_redis, task, testee.YOUTUBE_QUEUE, 'boom')
    mock_redis.lpop.assert_called_once_with(testee.YOUTUBE_QUEUE)
