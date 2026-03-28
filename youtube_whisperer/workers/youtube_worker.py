from typing import Generator

from youtube_whisperer.downloaders.playlist_downloader import yield_flattened_video_urls
from youtube_whisperer.fastapi.models import Task
from youtube_whisperer.queueing import YOUTUBE_QUEUE, queue_tasks
from youtube_whisperer.utils import REDIS_CLIENT
from youtube_whisperer.workers.common import BaseWorker, copy_task_with_source, create_transcription_task, resolve_waveform_file_path, yield_task


class YouTubeWorker(BaseWorker):
    """The YouTube worker expands playlists or channels and dispatches transcription tasks."""

    def get_queue_name(self) -> str:
        """Return the constant queue name for YouTube extraction tasks.

        Returns:
            The Redis string key assigned to the YouTube worker queue.
        """
        return YOUTUBE_QUEUE

    def yield_tasks(self, poll_interval_seconds: int) -> Generator[Task, None, None]:
        """Poll the basic YouTube Redis queue for new tasks continuously.

        Args:
            poll_interval_seconds: Number of seconds to wait between polling attempts when the queue is empty.

        Yields:
            Validated task models dequeued sequentially.
        """
        print("YouTube worker started")
        return yield_task(REDIS_CLIENT, YOUTUBE_QUEUE, poll_interval_seconds)

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
            concrete_task = copy_task_with_source(task, source)
            waveform_file_path, transcript_found = resolve_waveform_file_path(concrete_task)
            if not transcript_found:
                follow_up_tasks.append(create_transcription_task(concrete_task, waveform_file_path))
        if follow_up_tasks:
            queue_tasks(REDIS_CLIENT, follow_up_tasks)
