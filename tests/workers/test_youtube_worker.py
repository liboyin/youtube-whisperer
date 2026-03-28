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

    testee.YouTubeWorker().process_task(task)

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



