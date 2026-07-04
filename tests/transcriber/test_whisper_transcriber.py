from pathlib import Path
from types import SimpleNamespace

from faster_whisper.transcribe import Segment
import numpy as np
from pathlib_extensions import OverwriteMode
import pytest

from youtube_whisperer.adaptors.lang_code_adaptor import LanguageCode
from youtube_whisperer.adaptors.srt_deduplicator import SrtBlock
from youtube_whisperer.transcriber.rejection_policy import REJECTED_SUBSTRINGS, RejectedTranscriptionError
import youtube_whisperer.transcriber.whisper_transcriber as testee
from youtube_whisperer.utils import TranscriberMode


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


def test_transcribe_waveform_switches_translate_to_transcribe_for_english(capsys):
    """Test that translate mode is downgraded to transcribe when the source is English."""
    model = SimpleNamespace(
        transcribe=lambda waveform, lang_code, task: (
            iter(["segment"]),
            {"lang": lang_code, "task": task},
        )
    )
    language = LanguageCode("en")

    result = list(testee.transcribe_waveform(model, np.array([1.0]), TranscriberMode.TRANSLATE, language))

    assert result == ["segment"]
    assert "{'lang': 'en', 'task': 'transcribe'}" in capsys.readouterr().out


def test_get_default_whisper_model_builds_once_and_caches(mocker):
    """Test that the default model is built from resolved parameters once and served from cache thereafter."""
    testee.get_default_whisper_model.cache_clear()
    model = mocker.MagicMock()
    mocker.patch.object(testee, "get_default_whisper_model_parameters", return_value={"device": "cpu"})
    mock_model_cls = mocker.patch.object(testee, "WhisperModel", return_value=model)

    first = testee.get_default_whisper_model()
    second = testee.get_default_whisper_model()

    assert first is model and second is model
    mock_model_cls.assert_called_once_with(device="cpu")  # built once, kept resident across calls
    testee.get_default_whisper_model.cache_clear()


def test_transcribe_waveform_with_default_model_uses_cached_model(mocker):
    """Test that waveform transcription reuses the cached default model instead of rebuilding it."""
    waveform = np.array([1.0], dtype=np.float32)
    model = mocker.MagicMock()
    mocker.patch.object(testee, "get_default_whisper_model", return_value=model)
    mock_transcribe = mocker.patch.object(testee, "transcribe_waveform", return_value=["segment"])

    result = testee.transcribe_waveform_with_default_model(waveform, TranscriberMode.TRANSCRIBE, LANGUAGE)

    assert result == ["segment"]
    mock_transcribe.assert_called_once_with(model, waveform, TranscriberMode.TRANSCRIBE, LANGUAGE)


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


def test_transcribe_file_with_default_model_skips_empty_waveform(mocker, tmp_path, capsys):
    """Test that an empty waveform is skipped instead of transcribed."""
    input_path = tmp_path / "audio.wav"
    mocker.patch.object(testee, "load_whisper_waveform_from_file", return_value=np.array([]))

    result = testee.transcribe_file_with_default_model(input_path, LANGUAGE)

    assert result is None
    assert f"Skipping {input_path} because empty waveform is loaded" in capsys.readouterr().out


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
    mocker.patch.object(testee, "transcribe_waveform_with_default_model", return_value=segments)

    result = testee.transcribe_file_with_default_model(
        input_path,
        LANGUAGE,
        output_file_path=output_path,
        overwrite=OverwriteMode.ALWAYS,
        mode=TranscriberMode.TRANSLATE,
    )

    assert result == output_path
    save_mock.assert_called_once()
    assert save_mock.call_args.args[1] == output_path
    assert save_mock.call_args.kwargs == {"overwrite": OverwriteMode.ALWAYS}


def test_transcribe_file_with_default_model_propagates_error(mocker, tmp_path):
    """Test that transcription errors propagate so the worker loop can dead-letter the task."""
    input_path = tmp_path / "audio.wav"
    mocker.patch.object(testee, "load_whisper_waveform_from_file", return_value=np.array([1.0], dtype=np.float32))
    mocker.patch.object(testee, "transcribe_waveform_with_default_model", side_effect=RuntimeError("boom"))

    with pytest.raises(RuntimeError, match="boom"):
        testee.transcribe_file_with_default_model(input_path, LANGUAGE)


def test_whisper_main_parses_arguments_and_transcribes_each_path(mocker):
    """Test that the CLI transcribes each provided path with the parsed options."""
    args = SimpleNamespace(
        paths=[Path("/tmp/a.wav"), Path("/tmp/b.wav")],
        language=LANGUAGE,
        overwrite=OverwriteMode.NEVER,
        mode=TranscriberMode.TRANSLATE,
    )
    mocker.patch("argparse.ArgumentParser.parse_args", return_value=args)
    mock_transcribe = mocker.patch.object(testee, "transcribe_file_with_default_model")

    testee.main()

    assert mock_transcribe.call_args_list == [
        mocker.call(
            Path("/tmp/a.wav"),
            LANGUAGE,
            overwrite=OverwriteMode.NEVER,
            mode=TranscriberMode.TRANSLATE,
        ),
        mocker.call(
            Path("/tmp/b.wav"),
            LANGUAGE,
            overwrite=OverwriteMode.NEVER,
            mode=TranscriberMode.TRANSLATE,
        ),
    ]
