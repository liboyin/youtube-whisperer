import builtins
import inspect
import logging
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest
from faster_whisper.transcribe import Segment
from pathlib_extensions import OverwriteMode

import youtube_whisperer.transcriber.whisper_transcriber as testee
from youtube_whisperer.adaptors.lang_code_adaptor import LanguageCode
from youtube_whisperer.adaptors.srt_deduplicator import SrtBlock
from youtube_whisperer.transcriber.rejection_policy import (
    REJECTED_SUBSTRINGS,
    RejectedTranscriptionError,
)

LANGUAGE = LanguageCode("zh")


def make_segment(text: str) -> SimpleNamespace:
    return SimpleNamespace(text=text)


def test_segment_to_srt_block():
    """Converts a faster-whisper Segment's start/end/text into an SrtBlock."""
    segment = Segment(id=1, seek=2704, start=0.0, end=1.24, text='Segment', tokens=[50365, 4511], temperature=0.0, avg_logprob=-0.31, compression_ratio=1.28, no_speech_prob=0.72, words=None)
    srt_block = testee.segment_to_srt_block(segment)
    assert isinstance(srt_block, SrtBlock)
    assert srt_block.start_time == '00:00:00,000'
    assert srt_block.end_time == '00:00:01,240'
    assert srt_block.content == ['Segment']


def make_logging_model() -> SimpleNamespace:
    """Return a stand-in Whisper model that echoes the resolved language and task into its info dict."""
    return SimpleNamespace(
        transcribe=lambda waveform, lang_code, task: (
            iter(["segment"]),
            {"lang": lang_code, "task": task},
        )
    )


@pytest.mark.parametrize("source, expected_iso", [
    ("en", "en"), ("en-us", "en"), ("zh", "zh"), ("zh-cn", "zh"),
])
def test_transcribe_waveform_requests_source_language_transcription(caplog, source, expected_iso):
    """Test that every registered source runs transcription and logs model information."""
    with caplog.at_level(logging.INFO):
        result = list(testee.transcribe_waveform(make_logging_model(), np.array([1.0]), LanguageCode(source)))

    assert result == ["segment"]
    assert str({'lang': expected_iso, 'task': 'transcribe'}) in caplog.text


def test_whisper_helpers_expose_source_language_signatures():
    """Test that Python entry points retire operation arguments while retaining other parameters."""
    assert tuple(inspect.signature(testee.transcribe_waveform).parameters) == ('model', 'waveform', 'language')
    assert tuple(inspect.signature(testee.transcribe_waveform_with_default_model).parameters) == ('waveform', 'language')
    assert tuple(inspect.signature(testee.transcribe_file_with_default_model).parameters) == (
        'input_file_path', 'language', 'output_file_path', 'overwrite',
    )


@contextmanager
def owned_default_whisper_model_cache():
    """Isolate a fake default model in the process-wide cache.

    The cache is cleared on entry and every exit, including assertion failures.

    Yields:
        None: A scope for constructing and checking a fake model.
    """
    testee.get_default_whisper_model.cache_clear()
    try:
        yield
    finally:
        testee.get_default_whisper_model.cache_clear()


def test_get_default_whisper_model_builds_once_and_caches(mocker):
    """Test that the default model is built from resolved parameters once and served from cache thereafter."""
    model = mocker.MagicMock()
    mocker.patch.object(testee, "get_default_whisper_model_parameters", return_value={"device": "cpu"})
    mock_model_cls = mocker.patch.object(testee, "WhisperModel", return_value=model)

    with owned_default_whisper_model_cache():
        first = testee.get_default_whisper_model()
        second = testee.get_default_whisper_model()

        assert first is model and second is model
        mock_model_cls.assert_called_once_with(device="cpu")  # built once, kept resident across calls


def test_get_default_whisper_model_clears_fake_after_assertion_failure(mocker):
    """Test that a failed assertion releases the fake so the next cache use builds anew."""
    first_model = mocker.MagicMock()
    next_model = mocker.MagicMock()
    mock_model_cls = mocker.patch.object(testee, "WhisperModel", side_effect=[first_model, next_model])
    mocker.patch.object(testee, "get_default_whisper_model_parameters", return_value={"device": "cpu"})

    with pytest.raises(AssertionError, match="injected failure"), owned_default_whisper_model_cache():
        assert testee.get_default_whisper_model() is first_model
        raise AssertionError("injected failure")

    assert testee.get_default_whisper_model.cache_info().currsize == 0
    with owned_default_whisper_model_cache():
        assert testee.get_default_whisper_model() is next_model
        assert testee.get_default_whisper_model() is next_model
    assert mock_model_cls.call_count == 2


def test_transcribe_waveform_with_default_model_uses_cached_model(mocker):
    """Test that waveform transcription reuses the cached default model instead of rebuilding it."""
    waveform = np.array([1.0], dtype=np.float32)
    model = mocker.MagicMock()
    mocker.patch.object(testee, "get_default_whisper_model", return_value=model)
    mock_transcribe = mocker.patch.object(testee, "transcribe_waveform", return_value=["segment"])

    result = testee.transcribe_waveform_with_default_model(waveform, LANGUAGE)

    assert result == ["segment"]
    mock_transcribe.assert_called_once_with(model, waveform, LANGUAGE)


def test_transcribe_file_with_default_model_returns_existing_output_when_overwrite_denied(mocker, tmp_path):
    """Test that an existing SRT is returned without reloading audio when overwrite is denied."""
    input_path = tmp_path / "audio.wav"
    output_path = tmp_path / "audio.srt"
    output_path.write_text("existing")
    mock_overwrite = mocker.patch.object(testee, "overwrite_existing_path", return_value=False)
    mock_load = mocker.patch.object(testee, "load_whisper_waveform_from_file")

    result = testee.transcribe_file_with_default_model(
        input_path,
        LANGUAGE,
        output_file_path=output_path,
        overwrite=OverwriteMode.NEVER,
    )

    assert result == output_path
    mock_overwrite.assert_called_once_with(output_path, OverwriteMode.NEVER)
    mock_load.assert_not_called()


def test_transcribe_file_with_default_model_skips_empty_waveform(mocker, tmp_path, caplog):
    """Test that an empty waveform is skipped instead of transcribed."""
    input_path = tmp_path / "audio.wav"
    mocker.patch.object(testee, "load_whisper_waveform_from_file", return_value=np.array([]))

    with caplog.at_level(logging.WARNING):
        result = testee.transcribe_file_with_default_model(input_path, LANGUAGE)

    assert result is None
    assert f"Skipping {input_path} because empty waveform is loaded" in caplog.text


def test_transcribe_file_with_default_model_raises_on_rejected_transcription(mocker, tmp_path):
    """Test that a rejected transcription writes no SRT and propagates so the caller can dead-letter it."""
    input_path = tmp_path / "audio.wav"
    output_path = tmp_path / "audio.srt"
    mocker.patch.object(testee, "load_whisper_waveform_from_file", return_value=np.array([1.0], dtype=np.float32))
    mocker.patch.object(
        testee,
        "transcribe_waveform_with_default_model",
        return_value=[make_segment(f"prefix {REJECTED_SUBSTRINGS[0]} suffix")],
    )

    with pytest.raises(RejectedTranscriptionError):
        testee.transcribe_file_with_default_model(input_path, LANGUAGE, output_file_path=output_path)

    assert not output_path.exists()


def test_transcribe_file_with_default_model_saves_segments(mocker, tmp_path):
    """Test that successful segments are saved as SRT with the requested overwrite mode."""
    input_path = tmp_path / "audio.wav"
    output_path = tmp_path / "audio.srt"
    segments = [make_segment("hello")]
    save_mock = mocker.patch.object(testee, "save_segments_as_srt")
    mocker.patch.object(testee, "load_whisper_waveform_from_file", return_value=np.array([1.0], dtype=np.float32))
    mock_transcribe = mocker.patch.object(testee, "transcribe_waveform_with_default_model", return_value=segments)

    result = testee.transcribe_file_with_default_model(
        input_path,
        LANGUAGE,
        output_file_path=output_path,
        overwrite=OverwriteMode.ALWAYS,
    )

    assert result == output_path
    mock_transcribe.assert_called_once()
    assert mock_transcribe.call_args.args[1:] == (LANGUAGE,)
    save_mock.assert_called_once()
    assert save_mock.call_args.args[1] == output_path
    assert save_mock.call_args.kwargs == {"overwrite": OverwriteMode.ALWAYS}


@pytest.mark.parametrize("existing", [False, True])
def test_transcribe_file_with_default_model_late_rejection_preserves_final_and_retry(mocker, tmp_path, existing):
    """A late rejected Whisper segment preserves prior output and complete retry remains possible."""
    input_path = tmp_path / "audio.wav"
    output = tmp_path / "audio.srt"
    if existing:
        output.write_text("original")
    mocker.patch.object(testee, 'load_whisper_waveform_from_file', return_value=np.array([1.0], dtype=np.float32))
    consumed = []

    def segments():
        """Yield a valid segment followed by a rejected segment without real model access."""
        consumed.append("good")
        yield SimpleNamespace(start=0.0, end=1.0, text="Good")
        consumed.append("bad")
        yield SimpleNamespace(start=2.0, end=3.0, text=REJECTED_SUBSTRINGS[0])

    transcribe = mocker.patch.object(testee, 'transcribe_waveform_with_default_model', return_value=segments())
    with patch.object(testee.Path, "open", side_effect=AssertionError("premature write")) as opened, pytest.raises(RejectedTranscriptionError):
        testee.transcribe_file_with_default_model(input_path, LANGUAGE, output_file_path=output, overwrite=OverwriteMode.ALWAYS)
    opened.assert_not_called()
    assert consumed == ["good", "bad"]
    assert output.read_text() == "original" if existing else not output.exists()
    assert list(tmp_path.iterdir()) == ([output] if existing else [])
    transcribe.return_value = iter([SimpleNamespace(start=0.0, end=1.0, text="Good"), SimpleNamespace(start=2.0, end=3.0, text="Done")])
    assert testee.transcribe_file_with_default_model(input_path, LANGUAGE, output_file_path=output, overwrite=OverwriteMode.ALWAYS) == output
    assert output.read_text() == "1\n00:00:00,000 --> 00:00:01,000\nGood\n\n2\n00:00:02,000 --> 00:00:03,000\nDone\n"
    assert list(tmp_path.iterdir()) == [output]


@pytest.mark.parametrize("existing", [False, True])
def test_transcribe_file_with_default_model_publication_failure_preserves_final_and_retry(mocker, tmp_path, existing):
    """Whisper uses atomic publication and retries after a failed final replacement."""
    input_path = tmp_path / "audio.wav"
    output = tmp_path / "audio.srt"
    if existing:
        output.write_text("original")
    mocker.patch.object(testee, "load_whisper_waveform_from_file", return_value=np.array([1.0], dtype=np.float32))
    mocker.patch.object(testee, "transcribe_waveform_with_default_model", side_effect=lambda *args: iter([SimpleNamespace(start=0.0, end=1.0, text="Good")]))
    with patch.object(testee.Path, "replace", side_effect=OSError("failed publication")), pytest.raises(OSError, match="failed publication"):
        testee.transcribe_file_with_default_model(input_path, LANGUAGE, output_file_path=output, overwrite=OverwriteMode.ALWAYS)
    assert output.read_text() == "original" if existing else not output.exists()
    assert list(tmp_path.iterdir()) == ([output] if existing else [])
    assert testee.transcribe_file_with_default_model(input_path, LANGUAGE, output_file_path=output, overwrite=OverwriteMode.ALWAYS) == output
    assert output.read_text() == "1\n00:00:00,000 --> 00:00:01,000\nGood\n"
    assert list(tmp_path.iterdir()) == [output]


@pytest.mark.parametrize("approved", [False, True])
def test_transcribe_file_with_default_model_existing_prompt_is_decided_once(mocker, tmp_path, approved):
    """Existing-output consent occurs once before audio/model work and is reused for saving."""
    input_path = tmp_path / "audio.wav"
    output = tmp_path / "audio.srt"
    output.write_text("original")
    stdin = mocker.patch.object(builtins, "input", return_value="y" if approved else "n")
    load = mocker.patch.object(testee, "load_whisper_waveform_from_file", return_value=np.array([1.0], dtype=np.float32))
    transcribe = mocker.patch.object(testee, "transcribe_waveform_with_default_model", return_value=iter([SimpleNamespace(start=0.0, end=1.0, text="Good")]))
    assert testee.transcribe_file_with_default_model(input_path, LANGUAGE, output_file_path=output) == output
    stdin.assert_called_once_with(f"Path '{output}' already exists. Overwrite? (y/N): ")
    assert load.call_count == int(approved)
    assert transcribe.call_count == int(approved)
    assert output.read_text() == ("1\n00:00:00,000 --> 00:00:01,000\nGood\n" if approved else "original")


def test_transcribe_file_with_default_model_propagates_error(mocker, tmp_path):
    """Test that transcription errors propagate so the worker loop can dead-letter the task."""
    input_path = tmp_path / "audio.wav"
    mocker.patch.object(testee, "load_whisper_waveform_from_file", return_value=np.array([1.0], dtype=np.float32))
    mocker.patch.object(testee, "transcribe_waveform_with_default_model", side_effect=RuntimeError("boom"))

    with pytest.raises(RuntimeError, match="boom"):
        testee.transcribe_file_with_default_model(input_path, LANGUAGE)
