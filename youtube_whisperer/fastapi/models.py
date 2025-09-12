import datetime

from pydantic import BaseModel, field_validator

from youtube_whisperer.adaptors.lang_code_adaptor import LanguageCode
from youtube_whisperer.utils import TranscriberMode, TranscriberType


class Task(BaseModel):
    """
    source: str
        At input time, source can be a URL of a YouTube video or a playlist, or a glob pattern for local files.
        After resolution, it will be a concrete URL of a YouTube video or a local file path.

    transcriber: TranscriberType
        `local` for Whisper or `azure` for Azure Speech Recognition API. Defaults to `local`.

    language: LanguageCode
        The output language of transcription/translation. Must follow BCP-47 (works for Azure and Whisper) or ISO 639-1 (works for Whisper only).

    mode: TranscriberMode
        Whether to run Whisper in transcribe mode or translate mode.
    """
    source: str = f'assets/{datetime.date.today().year}*.mkv'
    transcriber: TranscriberType = TranscriberType.LOCAL
    language: LanguageCode = LanguageCode('en-us')  # validation is handled by LanguageCode.__get_pydantic_core_schema__
    mode: TranscriberMode = TranscriberMode.TRANSCRIBE

    @field_validator('source')
    def validate_source(cls, x: str) -> str:
        x = x.strip()
        if not x:
            raise ValueError('Source cannot be empty')
        return x

    @field_validator('transcriber')
    def validate_transcriber(cls, x: str | TranscriberType) -> TranscriberType:
        try:
            return TranscriberType(x)
        except ValueError:
            raise TypeError(f'Unexpected transcriber {x} of type {type(x)}')

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
