import pytest
from pydantic import ValidationError

from youtube_whisperer.adaptors.lang_code_adaptor import LanguageCode
import youtube_whisperer.models as testee
from youtube_whisperer.utils import TranscriberMode, TranscriberType


def test_task_requires_explicit_source():
    """Test that source has no default, so a task cannot be created without one."""
    with pytest.raises(ValidationError):
        testee.Task()


def test_task_source_validator():
    """Test that task sources are stripped and blank sources are rejected."""
    task = testee.Task(source="  http://example.com/video  ")
    assert task.source == "http://example.com/video"
    with pytest.raises(ValidationError):
        testee.Task(source="  ")


def test_task_transcriber_validator():
    """Test that task transcribers accept supported values, including download-only `none`, and reject invalid ones."""
    task = testee.Task(source="/tmp/audio.wav", transcriber="whisper")
    assert task.transcriber == TranscriberType.WHISPER
    task = testee.Task(source="/tmp/audio.wav", transcriber=TranscriberType.AZURE)
    assert task.transcriber == TranscriberType.AZURE
    task = testee.Task(source="https://example.com/video", transcriber="none")
    assert task.transcriber == TranscriberType.NONE
    with pytest.raises(ValidationError):
        testee.Task(source="/tmp/audio.wav", transcriber="unknown")
    with pytest.raises(ValidationError):
        testee.Task(source="/tmp/audio.wav", transcriber="local")


def test_task_language_validator():
    """Test that task languages accept valid codes and reject invalid ones."""
    english = LanguageCode("en")
    task = testee.Task(source="/tmp/audio.wav", language="en")
    assert task.language == english
    task = testee.Task(source="/tmp/audio.wav", language=english)
    assert task.language == english
    with pytest.raises(ValidationError):
        testee.Task(source="/tmp/audio.wav", language="")
    with pytest.raises(ValidationError):
        testee.Task(source="/tmp/audio.wav", language="invalid")


def test_task_mode_validator():
    """Test that task modes accept supported values and reject unknown ones."""
    task = testee.Task(source="/tmp/audio.wav", mode="transcribe")
    assert task.mode == TranscriberMode.TRANSCRIBE
    task = testee.Task(source="/tmp/audio.wav", mode=TranscriberMode.TRANSLATE)
    assert task.mode == TranscriberMode.TRANSLATE
    with pytest.raises(ValidationError):
        testee.Task(source="/tmp/audio.wav", mode="unknown")


def test_task_language_rejects_non_string_value():
    """Test that non-string language values raise a direct TypeError."""
    # Pydantic v2 does not wrap TypeError from plain validators, so it propagates directly
    with pytest.raises(TypeError, match="Unexpected language"):
        testee.Task(source="/tmp/audio.wav", language=123)


def test_task_model_json_schema_exposes_language_as_documented_string():
    """Test that the language field is published as a string with example codes for the docs UI."""
    language_schema = testee.Task.model_json_schema()["properties"]["language"]
    assert language_schema["type"] == "string"
    assert language_schema["examples"] == ["en", "en-us", "en-us->zh-cn"]


def test_task_queues_model_accepts_grouped_tasks():
    """Test that grouped queue snapshots accept task lists for each queue."""
    task = testee.Task(source="/tmp/audio.wav", language="en")

    result = testee.TaskQueues(
        youtube=[],
        whisper_pending=[task],
        whisper_active=[],
        azure_pending=[],
        azure_active=[],
    )

    assert result.whisper_pending == [task]


def test_dead_letter_model_wraps_task_error_context():
    """Test that dead-letter models retain the failed task, queue, and error."""
    task = testee.Task(source="/tmp/audio.wav", language="en")

    result = testee.DeadLetter(task=task, queue="stream:whisper", error="boom")

    assert result.task == task
    assert result.queue == "stream:whisper"
    assert result.error == "boom"
