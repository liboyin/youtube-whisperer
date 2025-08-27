import pytest
from pydantic import ValidationError

import youtube_whisperer.fastapi.models as testee
from youtube_whisperer.utils import TranscriberMode, TranscriberType


def test_task_source_validator():
    task = testee.Task(source="  http://example.com/video  ")
    assert task.source == "http://example.com/video"
    with pytest.raises(ValidationError):
        testee.Task(source="  ")


def test_task_transcriber_validator():
    task = testee.Task(transcriber="local")
    assert task.transcriber == TranscriberType.LOCAL
    task = testee.Task(transcriber=TranscriberType.AZURE)
    assert task.transcriber == TranscriberType.AZURE
    with pytest.raises(ValidationError):
        testee.Task(transcriber="unknown")


def test_task_validate_transcriber():
    assert testee.Task.model_validate({"transcriber": "local"}).transcriber == TranscriberType.LOCAL
    assert testee.Task.model_validate({"transcriber": "azure"}).transcriber == TranscriberType.AZURE
    assert testee.Task.model_validate({"transcriber": TranscriberType.LOCAL}).transcriber == TranscriberType.LOCAL
    assert testee.Task.model_validate({"transcriber": TranscriberType.AZURE}).transcriber == TranscriberType.AZURE
    with pytest.raises(ValidationError):
        testee.Task.model_validate({"transcriber": "unknown"})


def test_task_language_validator():
    task = testee.Task(language="")
    assert task.language == ""
    task = testee.Task(language="en")
    assert task.language == "en"
    with pytest.raises(ValidationError):
        testee.Task(language="unsupported")


def test_task_mode_validator():
    task = testee.Task(mode="transcribe")
    assert task.mode == TranscriberMode.TRANSCRIBE
    task = testee.Task(mode=TranscriberMode.TRANSLATE)
    assert task.mode == TranscriberMode.TRANSLATE
    with pytest.raises(ValidationError):
        testee.Task(mode="invalid_mode")


def test_task_validate_mode():
    assert testee.Task.model_validate({"mode": "transcribe"}).mode == TranscriberMode.TRANSCRIBE
    assert testee.Task.model_validate({"mode": "translate"}).mode == TranscriberMode.TRANSLATE
    assert testee.Task.model_validate({"mode": TranscriberMode.TRANSCRIBE}).mode == TranscriberMode.TRANSCRIBE
    assert testee.Task.model_validate({"mode": TranscriberMode.TRANSLATE}).mode == TranscriberMode.TRANSLATE
    import pydantic
    with pytest.raises(pydantic.ValidationError):
        testee.Task.model_validate({"mode": "foo"})
