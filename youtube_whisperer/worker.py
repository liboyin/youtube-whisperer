from contextlib import contextmanager
from pathlib import Path
import subprocess
import sys

from pathlib_extensions import OverwriteMode

from youtube_whisperer.__main__ import transcribe_to_srt_files
from youtube_whisperer.downloaders import download_video_and_transcript_with_default_title
from youtube_whisperer.fastapi.models import Task
from youtube_whisperer.transcriber.model_parameters import get_default_cuda_flag as use_cuda
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


def is_gpu_healthy() -> bool:
    """
    Checks if the GPU is healthy and available by running nvidia-smi.
    
    Returns:
        bool: True if nvidia-smi finished with exit code 0, False otherwise.
    """
    try:
        result = subprocess.run(["nvidia-smi"], check=False)
        return result.returncode == 0
    except Exception:
        return False


def process_queue():
    """
    Continuously monitors and processes download and transcription tasks from a Redis queue.
    """
    with redis_connection() as client:
        print("Worker started")
        while True:
            task = client.blpop('tasks', 0)[1]  # block indefinitely until a task is available
            # client.blpop returns a tuple (queue_name, task), e.g. (b'tasks', b'{"source": "...", "language": "..."}')
            if use_cuda() and not is_gpu_healthy():
                print("GPU health check failed. Restarting...")
                sys.exit(2)  # ENOENT
            print(f"Picked up task: {task}")
            task = Task.model_validate_json(task)
            source = task.source
            language = task.language
            if language == '':
                language = None  # use default lang codes for transcript downloader and auto-detect language for Whisper
            # assume playlists and glob patterns have been resolved at insertion time
            if is_url(source):
                video_file_path, transcript_flag = download_video_and_transcript_with_default_title(source, language, overwrite=OverwriteMode.NEVER)
            else:
                video_file_path = Path(source)
                transcript_flag = False
            if not transcript_flag:
                transcribe_to_srt_files([video_file_path], language, mode=task.mode, overwrite=OverwriteMode.NEVER)


if __name__ == "__main__":
    process_queue()
