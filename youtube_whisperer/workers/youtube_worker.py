from youtube_whisperer.downloaders.playlist_downloader import yield_flattened_video_urls
from youtube_whisperer.fastapi.models import Task
from youtube_whisperer.queueing import YOUTUBE_QUEUE, queue_dead_letter, queue_tasks
from youtube_whisperer.utils import REDIS_CLIENT
from youtube_whisperer.workers.common import copy_task_with_source, create_transcription_task, resolve_waveform_file_path, yield_task


def dispatch_task(task: Task) -> None:
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


def process_queue(poll_interval_seconds: int = 5) -> None:
    """Continuously process tasks from the YouTube queue.

    The loop blocks on the shared YouTube queue, dispatches each task into
    concrete transcription work, and removes the task from the queue when
    processing succeeds or after the failure has been recorded as a dead letter.

    Args:
        poll_interval_seconds: Number of seconds to wait between Redis polling
            attempts while the queue is empty.

    Returns:
        None. The function runs until the worker process is stopped.
    """
    print("YouTube worker started")
    for task in yield_task(REDIS_CLIENT, YOUTUBE_QUEUE, poll_interval_seconds):
        delete_task = False
        try:
            dispatch_task(task)
            delete_task = True
        except Exception as e:
            print(f"An error occurred while processing task {task}: {e}")
            queue_dead_letter(REDIS_CLIENT, task, YOUTUBE_QUEUE, str(e))
            delete_task = True
        finally:
            if delete_task:
                REDIS_CLIENT.lpop(YOUTUBE_QUEUE)
                print(f"Removed task from {YOUTUBE_QUEUE}: {task}")
