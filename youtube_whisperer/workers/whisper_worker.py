import logging
import subprocess
import sys
from pathlib import Path

from pathlib_extensions import OverwriteMode
from redis import StrictRedis

from youtube_whisperer.models import Task
from youtube_whisperer.transcriber.model_parameters import get_default_cuda_flag as use_cuda
from youtube_whisperer.transcriber.whisper_transcriber import transcribe_file_with_default_model
from youtube_whisperer.utils import REDIS_CLIENT, TranscriberType
from youtube_whisperer.workers.common import TranscriptionWorker

logger = logging.getLogger(__name__)


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
        logger.error("GPU health check failed. Restarting...")
        sys.exit(2)


class WhisperWorker(TranscriptionWorker):

    def __init__(self, slot: str, client: StrictRedis = REDIS_CLIENT) -> None:
        """Initialize the Whisper transcription worker.

        Args:
            slot: The worker slot identifier determining which active queue to run under.
            client: Redis client used for stream operations. Defaults to the shared pooled client.
        """
        super().__init__(TranscriberType.WHISPER, slot, client)

    def dispatch_task(self, task: Task, source: Path) -> None:
        """Run Whisper transcription for a resolved filesystem source.

        The worker validates GPU availability when CUDA is enabled and then invokes
        the Whisper transcriber directly to write subtitle files for the media source
        represented by the queued task. Any transcription failure propagates so the
        worker loop dead-letters the task instead of silently dropping it.

        Args:
            task: The transcription task that provides language and mode settings
                for the Whisper run.
            source: The concrete filesystem path to the media file that should be
                transcribed.

        Returns:
            None. Subtitle files are written to disk as a side effect.

        Raises:
            Exception: If Whisper transcription fails; the error propagates to the worker
                loop so the task is dead-lettered.
        """
        validate_gpu_health_or_exit()
        transcribe_file_with_default_model(source, task.language, mode=task.mode, overwrite=OverwriteMode.NEVER)
