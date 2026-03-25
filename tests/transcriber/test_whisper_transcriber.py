from pathlib import Path
from types import SimpleNamespace

import numpy as np
from pathlib_extensions import OverwriteMode

from youtube_whisperer.adaptors.lang_code_adaptor import LanguageCode
import youtube_whisperer.transcriber.whisper_transcriber as testee
from youtube_whisperer.utils import TranscriberMode


LANGUAGE = LanguageCode("zh")


def make_segment(text: str) -> SimpleNamespace:
    return SimpleNamespace(text=text)


def test_transcribe_waveform_switches_translate_to_transcribe_for_english(capsys):
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


def test_transcribe_waveform_with_default_model_builds_model_from_default_parameters(mocker):
    waveform = np.array([1.0], dtype=np.float32)
    model = mocker.MagicMock()
    mocker.patch.object(testee, "get_default_whisper_model_parameters", return_value={"device": "cpu"})
    mock_model_cls = mocker.patch.object(testee, "WhisperModel", return_value=model)
    mock_transcribe = mocker.patch.object(testee, "transcribe_waveform", return_value=["segment"])

    result = testee.transcribe_waveform_with_default_model(waveform, TranscriberMode.TRANSCRIBE, LANGUAGE)

    assert result == ["segment"]
    mock_model_cls.assert_called_once_with(device="cpu")
    mock_transcribe.assert_called_once_with(model, waveform, TranscriberMode.TRANSCRIBE, LANGUAGE)


def test_early_stopper_stops_at_known_bad_segment():
    segments = [
        make_segment("hello"),
        make_segment("请不吝点赞 订阅 转发 打赏支持明镜与点点栏目"),
        make_segment("world"),
    ]

    result = list(testee.early_stopper(segments))

    assert [segment.text for segment in result] == ["hello"]


def test_transcribe_file_with_default_model_returns_existing_output_when_overwrite_denied(mocker, tmp_path):
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
    input_path = tmp_path / "audio.wav"
    mocker.patch.object(testee, "load_whisper_waveform_from_file", return_value=np.array([]))

    result = testee.transcribe_file_with_default_model(input_path, LANGUAGE)

    assert result is None
    assert f"Skipping {input_path} because empty waveform is loaded" in capsys.readouterr().out


def test_transcribe_file_with_default_model_saves_segments(mocker, tmp_path):
    input_path = tmp_path / "audio.wav"
    output_path = tmp_path / "audio.srt"
    segments = [make_segment("hello")]
    adaptor = mocker.MagicMock()
    adaptor_cls = mocker.patch.object(testee, "WhisperSegmentAdaptor", return_value=adaptor)
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
    adaptor_cls.assert_called_once()
    adaptor.save_as_srt_file.assert_called_once_with(output_path, overwrite=OverwriteMode.ALWAYS)


def test_transcribe_file_with_default_model_returns_none_on_error(mocker, tmp_path, capsys):
    input_path = tmp_path / "audio.wav"
    mocker.patch.object(testee, "load_whisper_waveform_from_file", return_value=np.array([1.0], dtype=np.float32))
    mocker.patch.object(testee, "transcribe_waveform_with_default_model", side_effect=RuntimeError("boom"))

    result = testee.transcribe_file_with_default_model(input_path, LANGUAGE)

    assert result is None
    assert f"An error occurred while transcribing {input_path}: boom" in capsys.readouterr().out


def test_whisper_main_parses_arguments_and_transcribes_each_path(mocker):
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
