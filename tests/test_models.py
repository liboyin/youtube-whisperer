import json

import pytest
from pydantic import ValidationError

import youtube_whisperer.models as testee
from youtube_whisperer.adaptors.lang_code_adaptor import LanguageCode
from youtube_whisperer.utils import TranscriberType


def test_task_requires_explicit_source():
    """Test that source has no default, so a task cannot be created without one."""
    with pytest.raises(ValidationError):
        testee.Task()


@pytest.mark.parametrize('mode', ['transcribe', 'translate', 'unknown', None, 0, [], {}])
def test_task_rejects_any_removed_mode_value(mode):
    """Test that supplying the removed field fails even for former transcription values."""
    with pytest.raises(ValidationError, match='mode is no longer supported'):
        testee.Task(source='https://example.com/video', mode=mode)


def test_task_still_ignores_unrelated_unknown_fields():
    """Test that the narrow mode rejection preserves the existing unknown-field policy."""
    task = testee.Task(source='https://example.com/video', unrelated='ignored')
    assert task.model_dump(mode='json') == {
        'source': 'https://example.com/video', 'transcriber': 'whisper', 'language': 'en-us',
    }


def test_task_revalidation_accepts_existing_instance():
    """Test that the removed-key guard permits already constructed tasks."""
    task = testee.Task(source='https://example.com/video')
    assert testee.Task.model_validate(task) is task


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


@pytest.mark.parametrize('language', ['en->en', 'zh->en', 'en-us->zh-cn', 'en -> zh'])
def test_task_language_rejects_translation_arrows(language):
    """Test that translation-looking languages fail task validation rather than losing intent."""
    with pytest.raises(ValidationError, match='Unexpected input'):
        testee.Task(source='/tmp/audio.wav', language=language)


def test_task_language_rejects_non_string_value():
    """Test that non-string language values raise a direct TypeError."""
    # Pydantic v2 does not wrap TypeError from plain validators, so it propagates directly
    with pytest.raises(TypeError, match="Unexpected language"):
        testee.Task(source="/tmp/audio.wav", language=123)


def test_task_model_json_schema_exposes_language_as_documented_string():
    """Test that the language field is published as a string with example codes for the docs UI."""
    schema = testee.Task.model_json_schema()
    assert set(schema['properties']) == {'source', 'transcriber', 'language'}
    language_schema = schema["properties"]["language"]
    assert language_schema["type"] == "string"
    assert language_schema["examples"] == ["en", "en-us"]


def test_task_json_round_trip_has_only_transcription_fields():
    """Test that task JSON retains defaults and a source language without an operation field."""
    task = testee.Task(source='/tmp/audio.wav', language='zh-cn')
    payload = task.model_dump_json()
    assert json.loads(payload) == {'source': '/tmp/audio.wav', 'transcriber': 'whisper', 'language': 'zh-cn'}
    assert testee.Task.model_validate_json(payload) == task


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
    assert json.loads(result.model_dump_json())['whisper_pending'] == [
        {'source': '/tmp/audio.wav', 'transcriber': 'whisper', 'language': 'en'},
    ]
    assert testee.TaskQueues.model_validate_json(result.model_dump_json()) == result


def test_dead_letter_model_wraps_task_error_context():
    """Test that dead-letter models retain the failed task, queue, and error."""
    task = testee.Task(source="/tmp/audio.wav", language="en")

    result = testee.DeadLetter(task=task, queue="stream:whisper", error="boom")

    assert result.task == task
    assert result.queue == "stream:whisper"
    assert result.error == "boom"
    assert json.loads(result.model_dump_json()) == {
        'task': {'source': '/tmp/audio.wav', 'transcriber': 'whisper', 'language': 'en'},
        'queue': 'stream:whisper', 'error': 'boom',
    }
    assert testee.DeadLetter.model_validate_json(result.model_dump_json()) == result
