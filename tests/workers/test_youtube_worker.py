from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest
from pathlib_extensions import OverwriteMode

import youtube_whisperer.workers.common as common_testee
import youtube_whisperer.workers.youtube_worker as testee
from youtube_whisperer.models import Task
from youtube_whisperer.utils import TranscriberType

PLAYLIST_URL = 'https://example.com/playlist'
VIDEO_1 = 'https://example.com/video-1'
VIDEO_2 = 'https://example.com/video-2'
VIDEO_3 = 'https://example.com/video-3'


@pytest.fixture
def client():
    """Provide a test-owned Redis double so no test reaches the shared pooled client."""
    return mock.Mock(name='redis-client')


@pytest.fixture
def playlist_task():
    """Provide a playlist task requesting Azure transcription follow-ups."""
    return Task(
        source=PLAYLIST_URL,
        language='en',
        transcriber=TranscriberType.AZURE,
    )


def concrete_task(playlist_task, source):
    """Build the per-video task the worker derives from a playlist task."""
    return playlist_task.model_copy(update={'source': source})


def _raise(url):
    """Raise the download failure the per-video isolation tests inject."""
    raise RuntimeError(f'download failed for {url}')


@pytest.mark.parametrize('claim_min_idle_seconds', [91, 92])
def test_youtube_worker_stream_bindings(mocker, client, claim_min_idle_seconds):
    """Test that YouTube bindings natively map consumer names properly."""
    mocker.patch.object(common_testee, 'Settings', return_value=SimpleNamespace(worker_claim_min_idle_seconds=claim_min_idle_seconds))
    worker = testee.YouTubeWorker('test-slot', client=client)
    assert worker.get_consumer_name() == 'test-slot'
    assert worker.get_stream_name() == testee.YOUTUBE_STREAM

    from youtube_whisperer.queueing import WORKERS_GROUP
    mock_yield = mocker.patch('youtube_whisperer.workers.common.yield_task')
    worker.yield_tasks(10)
    mock_yield.assert_called_once_with(
        client=client,
        stream_name=testee.YOUTUBE_STREAM,
        group_name=WORKERS_GROUP,
        consumer_name='test-slot',
        poll_interval_seconds=10,
        claim_min_idle_seconds=claim_min_idle_seconds,
    )


def test_process_video_queues_follow_up_when_transcript_is_missing(mocker, client, playlist_task):
    """Test that a video without a downloadable transcript enqueues follow-up work for its media file."""
    task = concrete_task(playlist_task, VIDEO_1)
    mock_download = mocker.patch.object(
        testee,
        'download_video_and_transcript_with_default_title',
        return_value=(Path('/owned/video-1.mp4'), False),
    )
    mock_queue = mocker.patch.object(testee, 'queue_transcription_tasks')

    testee.YouTubeWorker('youtube-0', client=client).process_video(task)

    mock_download.assert_called_once_with(VIDEO_1, task.language, overwrite=OverwriteMode.NEVER)
    mock_queue.assert_called_once_with(client, [concrete_task(playlist_task, '/owned/video-1.mp4')])


def test_process_video_skips_follow_up_when_transcript_was_downloaded(mocker, client, playlist_task):
    """Test that an available transcript satisfies the request so no transcription is enqueued."""
    mocker.patch.object(
        testee,
        'download_video_and_transcript_with_default_title',
        return_value=(Path('/owned/video-1.mp4'), True),
    )
    mock_queue = mocker.patch.object(testee, 'queue_transcription_tasks')

    testee.YouTubeWorker('youtube-0', client=client).process_video(concrete_task(playlist_task, VIDEO_1))

    mock_queue.assert_not_called()


def test_process_video_with_none_transcriber_downloads_without_queueing_follow_up(mocker, client):
    """Test that a `none` transcriber downloads the media but never enqueues transcription, even without an SRT."""
    task = Task(source=VIDEO_1, language='en', transcriber=TranscriberType.NONE)
    mock_download = mocker.patch.object(
        testee,
        'download_video_and_transcript_with_default_title',
        return_value=(Path('/owned/video-1.mp4'), False),  # transcript missing: would otherwise queue a follow-up
    )
    mock_queue = mocker.patch.object(testee, 'queue_transcription_tasks')

    testee.YouTubeWorker('youtube-0', client=client).process_video(task)

    mock_download.assert_called_once_with(VIDEO_1, task.language, overwrite=OverwriteMode.NEVER)
    mock_queue.assert_not_called()


def test_process_task_queues_follow_ups_only_for_videos_missing_a_transcript(mocker, client, playlist_task):
    """Test that an expanded playlist enqueues follow-up work for exactly the videos still missing an SRT."""
    mocker.patch.object(testee, 'yield_flattened_video_urls', return_value=iter([VIDEO_1, VIDEO_2]))
    mock_download = mocker.patch.object(
        testee,
        'download_video_and_transcript_with_default_title',
        side_effect=[(Path('/owned/video-1.mp4'), True), (Path('/owned/video-2.mp4'), False)],
    )
    mock_queue = mocker.patch.object(testee, 'queue_transcription_tasks')
    mock_dead_letter = mocker.patch.object(testee, 'queue_dead_letter')

    testee.YouTubeWorker('youtube-0', client=client).process_task(playlist_task)

    assert mock_download.call_count == 2
    mock_download.assert_any_call(VIDEO_1, playlist_task.language, overwrite=OverwriteMode.NEVER)
    mock_download.assert_any_call(VIDEO_2, playlist_task.language, overwrite=OverwriteMode.NEVER)
    mock_queue.assert_called_once_with(client, [concrete_task(playlist_task, '/owned/video-2.mp4')])
    mock_dead_letter.assert_not_called()


def test_process_task_delivers_earlier_follow_ups_when_a_later_video_fails(mocker, client, playlist_task):
    """Test that a failing video neither discards an earlier video's follow-up nor stops later videos."""
    mocker.patch.object(testee, 'yield_flattened_video_urls', return_value=iter([VIDEO_1, VIDEO_2, VIDEO_3]))
    downloads = {
        VIDEO_1: (Path('/owned/video-1.mp4'), False),
        VIDEO_3: (Path('/owned/video-3.mp4'), False),
    }
    mocker.patch.object(
        testee,
        'download_video_and_transcript_with_default_title',
        side_effect=lambda url, _language, overwrite: downloads[url] if url in downloads else _raise(url),
    )
    mock_queue = mocker.patch.object(testee, 'queue_transcription_tasks')
    mock_dead_letter = mocker.patch.object(testee, 'queue_dead_letter')

    testee.YouTubeWorker('youtube-0', client=client).process_task(playlist_task)

    assert mock_queue.call_args_list == [
        mock.call(client, [concrete_task(playlist_task, '/owned/video-1.mp4')]),
        mock.call(client, [concrete_task(playlist_task, '/owned/video-3.mp4')]),
    ]
    # The dead letter names the failed video, not the playlist, so a retry targets only that video.
    mock_dead_letter.assert_called_once_with(
        client,
        concrete_task(playlist_task, VIDEO_2),
        testee.YOUTUBE_STREAM,
        f'download failed for {VIDEO_2}',
    )


def test_process_task_dead_letters_only_the_video_whose_enqueue_failed(mocker, client, playlist_task):
    """Test that a failed follow-up enqueue dead-letters that video alone and still enqueues the rest."""
    mocker.patch.object(testee, 'yield_flattened_video_urls', return_value=iter([VIDEO_1, VIDEO_2]))
    mocker.patch.object(
        testee,
        'download_video_and_transcript_with_default_title',
        side_effect=[(Path('/owned/video-1.mp4'), False), (Path('/owned/video-2.mp4'), False)],
    )
    mock_queue = mocker.patch.object(
        testee,
        'queue_transcription_tasks',
        side_effect=[ConnectionError('redis unavailable'), None],
    )
    mock_dead_letter = mocker.patch.object(testee, 'queue_dead_letter')

    testee.YouTubeWorker('youtube-0', client=client).process_task(playlist_task)

    assert mock_queue.call_args_list[-1] == mock.call(client, [concrete_task(playlist_task, '/owned/video-2.mp4')])
    mock_dead_letter.assert_called_once_with(
        client,
        concrete_task(playlist_task, VIDEO_1),
        testee.YOUTUBE_STREAM,
        'redis unavailable',
    )


def test_process_task_propagates_keyboard_interrupt_instead_of_dead_lettering(mocker, client, playlist_task):
    """Test that an interrupt aborts the parent task so its stream message stays pending for recovery."""
    mocker.patch.object(testee, 'yield_flattened_video_urls', return_value=iter([VIDEO_1, VIDEO_2]))
    mocker.patch.object(
        testee,
        'download_video_and_transcript_with_default_title',
        side_effect=KeyboardInterrupt,
    )
    mock_dead_letter = mocker.patch.object(testee, 'queue_dead_letter')

    worker = testee.YouTubeWorker('youtube-0', client=client)
    with pytest.raises(KeyboardInterrupt):
        worker.process_task(playlist_task)

    # Containing a BaseException would acknowledge the parent and silently drop the remaining videos.
    mock_dead_letter.assert_not_called()


def test_process_task_propagates_expansion_failure_after_delivering_earlier_follow_ups(mocker, client, playlist_task):
    """Test that an expansion failure reaches the worker loop only after earlier follow-ups are durable."""
    def yield_then_fail(_urls):
        yield VIDEO_1
        raise RuntimeError('playlist expansion failed')

    mocker.patch.object(testee, 'yield_flattened_video_urls', side_effect=yield_then_fail)
    mocker.patch.object(
        testee,
        'download_video_and_transcript_with_default_title',
        return_value=(Path('/owned/video-1.mp4'), False),
    )
    mock_queue = mocker.patch.object(testee, 'queue_transcription_tasks')
    mock_dead_letter = mocker.patch.object(testee, 'queue_dead_letter')

    worker = testee.YouTubeWorker('youtube-0', client=client)
    with pytest.raises(RuntimeError, match='playlist expansion failed'):
        worker.process_task(playlist_task)

    mock_queue.assert_called_once_with(client, [concrete_task(playlist_task, '/owned/video-1.mp4')])
    # The base worker loop owns the parent dead letter for an expansion failure.
    mock_dead_letter.assert_not_called()


def test_process_task_restart_requeues_only_the_still_untranscribed_video(mocker, client, playlist_task):
    """Test that reprocessing a recovered playlist skips videos whose SRT now exists and retries the rest."""
    mocker.patch.object(testee, 'yield_flattened_video_urls', return_value=iter([VIDEO_1, VIDEO_2]))
    # After the restart the first video's SRT exists, so the downloader reports the transcript as present.
    mocker.patch.object(
        testee,
        'download_video_and_transcript_with_default_title',
        side_effect=[(Path('/owned/video-1.mp4'), True), (Path('/owned/video-2.mp4'), False)],
    )
    mock_queue = mocker.patch.object(testee, 'queue_transcription_tasks')
    mock_dead_letter = mocker.patch.object(testee, 'queue_dead_letter')

    testee.YouTubeWorker('youtube-0', client=client).process_task(playlist_task)

    mock_queue.assert_called_once_with(client, [concrete_task(playlist_task, '/owned/video-2.mp4')])
    mock_dead_letter.assert_not_called()
