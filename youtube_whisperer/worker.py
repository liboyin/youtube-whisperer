import json
from pathlib import Path
import time

from youtube_whisperer.__main__ import transcribe_to_srt_files
from youtube_whisperer.downloaders import download_video_and_transcript_with_default_title
from youtube_whisperer.utils import redis_connection, is_url


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
                    video_file_path, transcript_flag = download_video_and_transcript_with_default_title(source, language)
                else:
                    video_file_path = Path(source)
                    transcript_flag = False
                if not transcript_flag:
                    transcribe_to_srt_files([video_file_path], language)
                client.lpop('tasks')
            else:
                print("Queue is empty. Sleeping for 60 seconds...")
                time.sleep(60)


if __name__ == "__main__":
    process_queue()
