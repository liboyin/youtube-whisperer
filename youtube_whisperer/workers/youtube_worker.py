
from pathlib_extensions import OverwriteMode

from youtube_whisperer.downloaders import download_video_and_transcript_with_default_title
from youtube_whisperer.downloaders.playlist_downloader import yield_flattened_video_urls
from youtube_whisperer.fastapi.models import Task
from youtube_whisperer.queueing import YOUTUBE_STREAM, queue_transcription_tasks
from youtube_whisperer.utils import REDIS_CLIENT
from youtube_whisperer.workers.common import BaseWorker


class YouTubeWorker(BaseWorker):
    """The YouTube worker expands playlists or channels and dispatches transcription tasks."""
    def __init__(self, slot: str) -> None:
        """Initialize the YouTube worker binding the slot to the consumer identity."""
        self.slot = slot

    def get_stream_name(self) -> str:
        """Return the constant stream name for YouTube extraction tasks."""
        return YOUTUBE_STREAM

    def get_consumer_name(self) -> str:
        """Return the constant consumer name ensuring task recovery inside the topology."""
        return self.slot

    def process_task(self, task: Task) -> None:
        """Resolve a YouTube task into concrete transcription work items.

        The YouTube worker expands playlist or channel inputs into individual video
        URLs, downloads each source to a local waveform-compatible path, and queues
        follow-up Whisper or Azure transcription tasks for any sources that still
        need transcripts.

        Args:
            task: The queued YouTube task whose source should be expanded and
                converted into downstream transcription tasks.

        Returns:
            None. Follow-up tasks are enqueued in Redis as a side effect when
            transcript generation is still required.
        """
        follow_up_tasks: list[Task] = []
        for source in yield_flattened_video_urls([task.source]):
            concrete_task = task.model_copy(update={'source': source})
            waveform_file_path, transcript_found = download_video_and_transcript_with_default_title(
                concrete_task.source,
                concrete_task.language,
                overwrite=OverwriteMode.NEVER,
            )
            if not transcript_found:
                follow_up_tasks.append(concrete_task.model_copy(update={
                    'source': str(waveform_file_path),
                }))
        if follow_up_tasks:
            queue_transcription_tasks(REDIS_CLIENT, follow_up_tasks)
