from pathlib import Path
import subprocess
import sys
import time
from typing import Generator

from pathlib_extensions import OverwriteMode
from redis import StrictRedis

from youtube_whisperer.__main__ import transcribe_to_srt_files
from youtube_whisperer.downloaders import download_video_and_transcript_with_default_title
from youtube_whisperer.fastapi.models import Task
from youtube_whisperer.transcriber.azure_transcriber import transcribe_audio_file_fire_and_forget
from youtube_whisperer.transcriber.model_parameters import get_default_cuda_flag as use_cuda
from youtube_whisperer.transcriber.waveform_loader import save_as_wav_file
from youtube_whisperer.utils import TranscriberType, REDIS_CLIENT, is_url


def yield_task(client: StrictRedis, poll_interval_seconds: int = 5) -> Generator[Task, None, None]:
    """
    Continuously peeks at the head of the Redis 'tasks' queue.

    If a task is available, it yields the task. If the queue is empty, it waits for a specified interval before checking again.
    """
    while True:
        head = client.lrange('tasks', 0, 0)
        if not head:
            time.sleep(poll_interval_seconds)
            continue
        task = head[0]
        print(f"Picked up task: {task}")
        yield Task.model_validate_json(task)


def is_gpu_healthy() -> bool:
    """
    Checks if the GPU is healthy and available by running `nvidia-smi`.
    
    Returns:
        bool: True if nvidia-smi finished with exit code 0, False otherwise.
    """
    try:
        result = subprocess.run(["nvidia-smi"], check=False)
        return result.returncode == 0
    except Exception:
        return False


def validate_gpu_health_or_exit() -> None:
    """
    Validates the GPU health. If unhealthy, exit with ENOENT to restart the worker container.
    """
    if use_cuda() and not is_gpu_healthy():
        print("GPU health check failed. Restarting...")
        sys.exit(2)


def resolve_waveform_file_path(task: Task) -> tuple[Path, bool]:
    """
    Resolves the task's source into a local media file path and checks for existing transcripts.

    If the task's source is a URL, it downloads the video/audio. If it's a local path, it uses that path directly.

    Returns:
        tuple[Path, bool]:
            - Path: The path to the local media file.
            - bool: True if a transcript was found, False otherwise.
    """
    source = task.source
    # assume playlists and glob patterns have been resolved at insertion time
    if is_url(source):
        return download_video_and_transcript_with_default_title(source, task.language, overwrite=OverwriteMode.NEVER)
    return Path(source), False


def dispatch_transcription_task(task: Task, source: Path) -> None:
    """
    Dispatches the transcription task to the appropriate transcriber (local Whisper or Azure).

    Handles necessary pre-processing steps like converting audio to WAV format for Azure.
    """
    match task.transcriber:
        case TranscriberType.LOCAL:
            validate_gpu_health_or_exit()
            transcribe_to_srt_files([source], task.language, mode=task.mode, overwrite=OverwriteMode.NEVER)
        case TranscriberType.AZURE:
            if source.suffix.lower() != '.wav':
                source = save_as_wav_file(source, overwrite=OverwriteMode.NEVER)
                if not source:
                    print(f"Skipping transcription for {source} as WAV conversion failed")
                    return
            transcribe_audio_file_fire_and_forget(source, task.language, overwrite=OverwriteMode.NEVER)
        case _:
            raise ValueError(f'Unsupported transcriber type: {task.transcriber}')


def process_queue(poll_interval_seconds: int = 5) -> None:
    """
    Continuously monitors the Redis 'tasks' queue and processes incoming transcription tasks.
    """
    print("Worker started")
    for task in yield_task(REDIS_CLIENT, poll_interval_seconds):
        delete_task = False
        try:
            waveform_file_path, transcript_found = resolve_waveform_file_path(task)
            if not transcript_found:
                dispatch_transcription_task(task, waveform_file_path)
            delete_task = True
        # validate_gpu_health_or_exit() may raise SystemExit, which is a subclass of BaseException instead of Exception
        except Exception as e:
            print(f"An error occurred while processing task {task}: {e}")
            delete_task = True  # Remove the task from the queue to prevent infinite retries.
        finally:
            # delete_task is only False if GPU health check failed
            if delete_task:
                # Assuming a single worker, we can safely LPOP the head.
                REDIS_CLIENT.lpop('tasks')
                print(f"Removed task: {task}")


if __name__ == "__main__":
    process_queue()
