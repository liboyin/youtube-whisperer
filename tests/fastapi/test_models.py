import pytest
from pydantic import ValidationError

from youtube_whisperer.adaptors.lang_code_adaptor import LanguageCode
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


def test_task_language_validator():
    english = LanguageCode("en")
    task = testee.Task(language="en")
    assert task.language == english
    task = testee.Task(language=english)
    assert task.language == english
    with pytest.raises(ValidationError):
        testee.Task(language="")
    with pytest.raises(ValidationError):
        testee.Task(language="invalid")


def test_task_mode_validator():
    task = testee.Task(mode="transcribe")
    assert task.mode == TranscriberMode.TRANSCRIBE
    task = testee.Task(mode=TranscriberMode.TRANSLATE)
    assert task.mode == TranscriberMode.TRANSLATE
    with pytest.raises(ValidationError):
        testee.Task(mode="unknown")


def test_task_language_accepts_repr_string():
    task = testee.Task(language="LanguageCode(source='en-us', target=None)")
    assert task.language == LanguageCode("en-us")


def test_task_language_rejects_non_string_value():
    # Pydantic v2 does not wrap TypeError from plain validators, so it propagates directly
    with pytest.raises(TypeError, match="Unexpected language"):
        testee.Task(language=123)


def test_task_model_json_schema_includes_language_field():
    schema = testee.Task.model_json_schema()
    assert "language" in schema.get("properties", {})
