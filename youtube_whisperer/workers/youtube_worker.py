
import logging

from pathlib_extensions import OverwriteMode
from redis import StrictRedis

from youtube_whisperer.domain import TranscriberType
from youtube_whisperer.downloaders import (
    download_video_and_transcript_with_default_title,
)
from youtube_whisperer.downloaders.playlist_downloader import yield_flattened_video_urls
from youtube_whisperer.models import Task
from youtube_whisperer.queueing import (
    YOUTUBE_STREAM,
    queue_dead_letter,
    queue_transcription_tasks,
)
from youtube_whisperer.utils import REDIS_CLIENT
from youtube_whisperer.workers.common import BaseWorker

logger = logging.getLogger(__name__)


class YouTubeWorker(BaseWorker):
    """The YouTube worker expands playlists or channels and dispatches transcription tasks."""
    def __init__(self, slot: str, client: StrictRedis = REDIS_CLIENT) -> None:
        """Initialize the YouTube worker binding the slot to the consumer identity.

        Args:
            slot: The consumer identity this worker uses to claim and recover tasks.
            client: Redis client used for queueing follow-up tasks. Defaults to the shared pooled client.
        """
        super().__init__(client)
        self.slot = slot

    def get_stream_name(self) -> str:
        """Return the constant stream name for YouTube extraction tasks."""
        return YOUTUBE_STREAM

    def get_consumer_name(self) -> str:
        """Return the constant consumer name ensuring task recovery inside the topology."""
        return self.slot

    def process_video(self, task: Task) -> None:
        """Download one concrete video and enqueue its follow-up transcription work.

        The follow-up is enqueued for this video alone instead of being buffered until the
        playlist finishes, so a later video's failure cannot discard work this video already
        earned. A `none` transcriber requests download only, so no follow-up is enqueued
        regardless of transcript presence.

        Args:
            task: A task whose source is a single concrete video URL.

        Returns:
            None. The media file is written to disk and any follow-up task is enqueued in
            Redis as side effects.

        Raises:
            Exception: Any download, caption-lookup, or enqueue failure, so the caller can
                dead-letter this one video rather than abandoning the rest of the playlist.
        """
        waveform_file_path, transcript_found = download_video_and_transcript_with_default_title(
            task.source,
            task.language,
            overwrite=OverwriteMode.NEVER,
        )
        if task.transcriber != TranscriberType.NONE and not transcript_found:
            queue_transcription_tasks(self.client, [task.model_copy(update={
                'source': str(waveform_file_path),
            })])

    def process_task(self, task: Task) -> None:
        """Resolve a YouTube task into concrete transcription work items.

        The YouTube worker expands playlist or channel inputs into individual video URLs and
        processes each one independently. A video that fails to download, look up captions, or
        enqueue its follow-up is dead-lettered under its own concrete video URL, and the
        remaining videos are still attempted, so one private or unavailable video no longer
        strands an entire playlist. The parent task therefore completes once every expanded
        video has been attempted; a failure during expansion itself still propagates and
        dead-letters the parent, with already-completed videos' follow-ups already durable.

        Args:
            task: The queued YouTube task whose source should be expanded and
                converted into downstream transcription tasks.

        Returns:
            None. Follow-up tasks and per-video dead letters are written to Redis as side
            effects.
        """
        for source in yield_flattened_video_urls([task.source]):
            concrete_task = task.model_copy(update={'source': source})
            try:
                self.process_video(concrete_task)
            # Per-video isolation: only Exception is contained, so a BaseException such as
            # KeyboardInterrupt still aborts the parent and leaves its message pending.
            except Exception as e:
                logger.exception("Failed to process video %s expanded from %s", source, task.source)
                queue_dead_letter(self.client, concrete_task, self.get_stream_name(), str(e))
