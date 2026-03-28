from pathlib import Path

from pathlib_extensions import OverwriteMode

from youtube_whisperer.fastapi.models import Task
from youtube_whisperer.transcriber.azure_transcriber import transcribe_audio_file
from youtube_whisperer.transcriber.waveform_loader import save_as_wav_file
from youtube_whisperer.utils import TranscriberType
from youtube_whisperer.workers.common import process_active_slot_queue


def dispatch_task(task: Task, source: Path) -> None:
    """Run Azure Speech transcription for a resolved filesystem source.

    Azure transcription expects WAV input, so the worker reuses an existing
    sidecar WAV file when present or converts the source before submitting the
    resulting audio file to the Azure transcriber using the task's requested
    language.

    Args:
        task: The transcription task that provides language settings for the
            Azure Speech request.
        source: The concrete filesystem path to the media file that should be
            transcribed.

    Returns:
        None. Subtitle output is written by the Azure transcriber as a side
        effect.
    """
    if source.suffix.lower() != '.wav':
        wav_source = source.with_suffix('.wav')
        if not wav_source.is_file():
            converted_source = save_as_wav_file(source, output_file_path=wav_source, overwrite=OverwriteMode.NEVER)
            if converted_source is None:
                raise RuntimeError(f"Failed to create WAV file for {source}")
            wav_source = converted_source
        source = wav_source
    transcribe_audio_file(source, task.language, overwrite=OverwriteMode.NEVER)


def process_queue(slot: str, poll_interval_seconds: int = 5) -> None:
    """Process Azure transcription tasks for a specific active worker slot.

    The worker listens to its slot-specific active queue, resolves task sources
    to local paths, and hands each source to the Azure dispatcher after any
    required audio conversion.

    Args:
        slot: Active-slot identifier used to select the Redis queue this worker
            should consume.
        poll_interval_seconds: Number of seconds to wait between Redis polling
            attempts while the active queue is empty.

    Returns:
        None. The function runs until the worker process is stopped.
    """
    process_active_slot_queue(TranscriberType.AZURE, slot, dispatch_task, poll_interval_seconds)
