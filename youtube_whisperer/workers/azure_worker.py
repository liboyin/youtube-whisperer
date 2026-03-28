from pathlib import Path

from pathlib_extensions import OverwriteMode

from youtube_whisperer.fastapi.models import Task
from youtube_whisperer.transcriber.azure_transcriber import transcribe_audio_file
from youtube_whisperer.transcriber.waveform_loader import save_as_wav_file
from youtube_whisperer.utils import TranscriberType
from youtube_whisperer.workers.common import TranscriptionWorker


class AzureWorker(TranscriptionWorker):

    def __init__(self, slot: str) -> None:
        """Initialize the Azure transcription worker.

        Args:
            slot: The worker slot identifier determining which active queue to run under.
        """
        super().__init__(TranscriberType.AZURE, slot)

    def dispatch_task(self, task: Task, source: Path) -> None:
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
