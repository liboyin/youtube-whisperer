import json
import time

from youtube_whisperer.__main__ import transcribe_to_srt_files
from youtube_whisperer.downloaders import download_video_and_transcript_with_default_title
from youtube_whisperer.utils import redis_connection, is_url


def process_queue():
    with redis_connection() as client:
        while True:
            task = client.lindex('tasks', 0)
            if task:
                source, language = json.loads(task)
                print(f"Processing task: {source}, {language}")
                # assume playlists and glob patterns have been resolved at insertion time
                if is_url(source):
                    video_file_path, transcript_flag = download_video_and_transcript_with_default_title(source, language)
                if not transcript_flag:
                    transcribe_to_srt_files([video_file_path], language)
                client.lpop('tasks')
            else:
                print("Queue is empty")
                time.sleep(60)


if __name__ == "__main__":
    process_queue()
