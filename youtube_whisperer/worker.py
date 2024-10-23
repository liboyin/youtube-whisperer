from contextlib import contextmanager
import json
from pathlib import Path
import time

from pathlib_extensions import OverwriteMode

from youtube_whisperer.__main__ import transcribe_to_srt_files
from youtube_whisperer.downloaders import download_video_and_transcript_with_default_title
from youtube_whisperer.utils import get_redis_client, is_url


@contextmanager
def redis_connection():
    """
    Context manager for a Redis connection.

    Yields:
        redis.StrictRedis: A Redis client instance.
    """
    client = get_redis_client()
    try:
        yield client
    finally:
        if client:
            client.close()


def process_queue():
    """
    Continuously monitors and processes download and transcription tasks from a Redis queue.
    """
    with redis_connection() as client:
        print("Worker started")
        while True:
            task = client.lindex('tasks', 0)
            if task:
                print(f"Picked up task: {task}")
                task = json.loads(task)
                source = task['source']
                language = task['language']
                # assume playlists and glob patterns have been resolved at insertion time
                if is_url(source):
                    video_file_path, transcript_flag = download_video_and_transcript_with_default_title(source, language, overwrite=OverwriteMode.NEVER)
                else:
                    video_file_path = Path(source)
                    transcript_flag = False
                if not transcript_flag:
                    transcribe_to_srt_files([video_file_path], language, overwrite=OverwriteMode.NEVER)
                client.lpop('tasks')
            else:
                print("Queue is empty. Sleeping for 60 seconds...")
                time.sleep(60)


if __name__ == "__main__":
    process_queue()
