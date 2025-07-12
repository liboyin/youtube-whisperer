import pytest
from pydantic import ValidationError

import youtube_whisperer.fastapi.models as testee
from youtube_whisperer.utils import WhisperMode


def test_task_source_validator():
    task = testee.Task(source="  http://example.com/video  ")
    assert task.source == "http://example.com/video"
    with pytest.raises(ValidationError):
        testee.Task(source="  ")


def test_task_language_validator():
    task = testee.Task(language="")
    assert task.language == ""
    task = testee.Task(language="en")
    assert task.language == "en"
    with pytest.raises(ValidationError):
        testee.Task(language="unsupported")


def test_task_mode_validator():
    task = testee.Task(mode="transcribe")
    assert task.mode == WhisperMode.TRANSCRIBE
    task = testee.Task(mode=WhisperMode.TRANSLATE)
    assert task.mode == WhisperMode.TRANSLATE
    with pytest.raises(ValidationError):
        testee.Task(mode="invalid_mode")
