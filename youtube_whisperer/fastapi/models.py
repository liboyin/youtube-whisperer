import datetime

from pydantic import BaseModel, field_validator

from youtube_whisperer.utils import WHISPER_LANG_CODES, TranscriberMode


class Task(BaseModel):
    """
    source: str
        At input time, source can be a URL of a YouTube video or a playlist, or a glob pattern for local files.
        After resolution, it will be a concrete URL of a YouTube video or a local file path.

    language: str
        The language code for the transcription. Must be one of Whisper-supported language codes or an empty string.

    mode: TranscriberMode
        Whether to run Whisper in transcribe mode or translate mode.
    """
    source: str = f'assets/{datetime.date.today().year}*.mkv'
    language: str = 'en'
    mode: TranscriberMode = TranscriberMode.TRANSCRIBE

    @field_validator('source')
    def validate_source(cls, x: str) -> str:
        x = x.strip()
        if not x:
            raise ValueError('Source cannot be empty')
        return x

    @field_validator('language')
    def validate_language(cls, x: str) -> str:
        if x and x not in WHISPER_LANG_CODES:
            raise ValueError(f'Unsupported language: {x}')
        return x

    @field_validator('mode')
    def validate_mode(cls, x: str | TranscriberMode) -> TranscriberMode:
        try:
            return TranscriberMode(x)
        except ValueError:
            raise TypeError(f'Unexpected mode {x} of type {type(x)}')


class AddTasksResponse(BaseModel):
    successful: list[Task]
    failed: list[Task]


class AddAssetsResponse(BaseModel):
    successful: list[str]
    failed: list[str]
