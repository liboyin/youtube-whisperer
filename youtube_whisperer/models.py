from pydantic import BaseModel, field_validator

from youtube_whisperer.adaptors.lang_code_adaptor import LanguageCode
from youtube_whisperer.utils import TranscriberMode, TranscriberType


class Task(BaseModel):
    """
    source: str (required)
        At input time, source can be a URL of a YouTube video or a playlist, or a glob pattern for filesystem files.
        After resolution, it will be a concrete URL of a YouTube video or a filesystem file path.
        It is required: there is no default, so `POST /tasks` must specify an explicit source per task.

    transcriber: TranscriberType
        `whisper` for faster-whisper, `azure` for Azure Speech Recognition API, or `none` to download
        a YouTube source without transcribing it. Defaults to `whisper`. `none` only applies to URL
        sources; a filesystem source with `none` is not actionable and is reported as failed.

    language: LanguageCode
        The output language of transcription/translation. Must follow BCP-47 (works for Azure and Whisper) or ISO 639-1 (works for Whisper only).

    mode: TranscriberMode
        Whether to run Whisper in transcribe mode or translate mode.
    """
    source: str
    transcriber: TranscriberType = TranscriberType.WHISPER
    language: LanguageCode = LanguageCode('en-us')  # validation is handled by LanguageCode.__get_pydantic_core_schema__
    mode: TranscriberMode = TranscriberMode.TRANSCRIBE

    @field_validator('source')
    def validate_source(cls, x: str) -> str:
        """Strip surrounding whitespace from a task source and reject empty values.

        Args:
            x (str): The raw `source` value supplied for the task.

        Returns:
            str: The stripped source value.

        Raises:
            ValueError: If the source is empty after stripping.
        """
        x = x.strip()
        if not x:
            raise ValueError('Source cannot be empty')
        return x


class AddTasksResponse(BaseModel):
    successful: list[Task]
    failed: list[Task]


class TaskQueues(BaseModel):
    youtube: list[Task]
    whisper_pending: list[Task]
    whisper_active: list[Task]
    azure_pending: list[Task]
    azure_active: list[Task]


class DeadLetter(BaseModel):
    task: Task
    queue: str
    error: str
