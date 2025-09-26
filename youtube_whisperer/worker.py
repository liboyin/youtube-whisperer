from pathlib import Path
import subprocess
import sys
import time

from pathlib_extensions import OverwriteMode

from youtube_whisperer.__main__ import transcribe_to_srt_files
from youtube_whisperer.downloaders import download_video_and_transcript_with_default_title
from youtube_whisperer.fastapi.models import Task
from youtube_whisperer.transcriber.azure_transcriber import transcribe_audio_file
from youtube_whisperer.transcriber.model_parameters import get_default_cuda_flag as use_cuda
from youtube_whisperer.transcriber.waveform_loader import save_as_wav_file
from youtube_whisperer.utils import TranscriberType, redis_connection, is_url


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


def process_queue(check_interval_seconds: int = 5) -> None:
    """
    Continuously monitors and processes download and transcription tasks from a Redis queue.
    """
    with redis_connection() as client:
        print("Worker started")
        while True:
            # Peek at the head of the queue without removing the task.
            head = client.lrange('tasks', 0, 0)
            if not head:
                time.sleep(check_interval_seconds)
                continue
            task_json = head[0]
            # Perform the health check before processing.
            if use_cuda() and not is_gpu_healthy():
                print("GPU health check failed. Restarting...")
                sys.exit(2)  # Return ENOENT while the task remains on the queue.
            try:
                print(f"Picked up task: {task_json}")
                task = Task.model_validate_json(task_json)
                source = task.source
                language = task.language
                # assume playlists and glob patterns have been resolved at insertion time
                if is_url(source):
                    waveform_file_path, transcript_flag = download_video_and_transcript_with_default_title(source, language, overwrite=OverwriteMode.NEVER)
                else:
                    waveform_file_path = Path(source)
                    transcript_flag = False
                if transcript_flag:
                    continue
                match task.transcriber:
                    case TranscriberType.AZURE:
                        if waveform_file_path.suffix.lower() != '.wav':
                            waveform_file_path = save_as_wav_file(waveform_file_path, overwrite=OverwriteMode.NEVER)
                            if not waveform_file_path:
                                print(f"Skipping transcription for {waveform_file_path} as WAV conversion failed")
                                continue
                        transcribe_audio_file(waveform_file_path, language, overwrite=OverwriteMode.NEVER)
                    case TranscriberType.LOCAL:
                        transcribe_to_srt_files([waveform_file_path], language, mode=task.mode, overwrite=OverwriteMode.NEVER)
                    case _:
                        raise ValueError(f'Unsupported transcriber type: {task.transcriber}')
            except Exception as e:
                print(f"An error occurred while processing task {task_json}: {e}")
            finally:
                # Remove the task from the queue after it has been processed or an error occurred.
                # Assuming a single worker, we can safely LPOP the head.
                popped_task = client.lpop('tasks')
                print(f"Removed task: {popped_task}")


if __name__ == "__main__":
    process_queue()
