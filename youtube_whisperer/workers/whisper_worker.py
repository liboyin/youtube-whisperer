import subprocess
import sys
from pathlib import Path

from pathlib_extensions import OverwriteMode

from youtube_whisperer.__main__ import transcribe_to_srt_files
from youtube_whisperer.fastapi.models import Task
from youtube_whisperer.transcriber.model_parameters import get_default_cuda_flag as use_cuda
from youtube_whisperer.utils import TranscriberType
from youtube_whisperer.workers.common import process_active_slot_queue


def is_gpu_healthy() -> bool:
    """Check whether the CUDA device is available for Whisper work.

    The Whisper worker treats a successful `nvidia-smi` invocation as a simple
    health probe for the host GPU before attempting CUDA-backed transcription.

    Returns:
        True when `nvidia-smi` exits successfully, indicating the GPU is likely
        available. False when the command fails or cannot be executed.
    """
    try:
        result = subprocess.run(["nvidia-smi"], check=False)
        return result.returncode == 0
    except Exception:
        return False


def validate_gpu_health_or_exit() -> None:
    """Abort the worker when CUDA is enabled but the GPU health check fails.

    This guard is called immediately before Whisper transcription so the worker
    can restart cleanly instead of repeatedly failing jobs against an unhealthy
    CUDA environment.

    Returns:
        None. The function exits the process with the worker restart status code
        when CUDA is enabled and the GPU health probe fails.
    """
    if use_cuda() and not is_gpu_healthy():
        print("GPU health check failed. Restarting...")
        sys.exit(2)


def dispatch_task(task: Task, source: Path) -> None:
    """Run Whisper transcription for a resolved filesystem source.

    The worker validates GPU availability when CUDA is enabled and then invokes
    the standard transcription entrypoint to write subtitle files for the media
    source represented by the queued task.

    Args:
        task: The transcription task that provides language and mode settings
            for the Whisper run.
        source: The concrete filesystem path to the media file that should be
            transcribed.

    Returns:
        None. Subtitle files are written to disk as a side effect.
    """
    validate_gpu_health_or_exit()
    transcribe_to_srt_files([source], task.language, mode=task.mode, overwrite=OverwriteMode.NEVER)


def process_queue(slot: str, poll_interval_seconds: int = 5) -> None:
    """Process Whisper tasks assigned to a specific active worker slot.

    The worker listens to its slot-specific active queue, resolves task sources
    to local paths, and passes each item to the Whisper dispatcher for
    transcription.

    Args:
        slot: Active-slot identifier used to select the Redis queue this worker
            should consume.
        poll_interval_seconds: Number of seconds to wait between Redis polling
            attempts while the active queue is empty.

    Returns:
        None. The function runs until the worker process is stopped.
    """
    process_active_slot_queue(TranscriberType.WHISPER, slot, dispatch_task, poll_interval_seconds)
