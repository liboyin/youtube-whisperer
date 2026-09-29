from collections.abc import Mapping

from pydantic import BaseModel, field_validator, model_validator

from youtube_whisperer.adaptors.lang_code_adaptor import LanguageCode
from youtube_whisperer.domain import TranscriberType


class Task(BaseModel):
    """Describe media download or source-language transcription work.

    A supplied obsolete ``mode`` field is rejected; other unknown fields retain
    the existing ignored-field behavior.

    Attributes:
        source: Required YouTube video/playlist URL or filesystem glob at input;
            after resolution, a concrete video URL or filesystem file path.
            Surrounding whitespace is stripped and blank sources are rejected.
        transcriber: ``whisper`` (the default), ``azure``, or ``none`` for a
            download-only URL task. Filesystem sources with ``none`` are not
            actionable and are reported as failed.
        language: Registered source language, defaulting to ``en-us``. BCP-47
            codes work with both engines; ISO 639-1 codes work with Whisper only.
    """
    source: str
    transcriber: TranscriberType = TranscriberType.WHISPER
    language: LanguageCode = LanguageCode('en-us')  # validation is handled by LanguageCode.__get_pydantic_core_schema__

    @model_validator(mode='before')
    @classmethod
    def reject_removed_mode(cls, data: object) -> object:
        """Reject obsolete operation selection before validating task fields.

        Other unknown fields retain Pydantic's existing ignored-field behavior.

        Args:
            data: The incoming task mapping or an already constructed task.

        Returns:
            The unchanged input when it does not contain the removed field.

        Raises:
            ValueError: If the input supplies any value for ``mode``.
        """
        if isinstance(data, Mapping) and 'mode' in data:
            raise ValueError('mode is no longer supported; omit it to transcribe the source language')
        return data

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
