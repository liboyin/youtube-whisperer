from pathlib import Path
from unittest import mock

import pytest

from pathlib_extensions import OverwriteMode

from youtube_whisperer.adaptors.lang_code_adaptor import LanguageCode
from youtube_whisperer.transcriber.azure_transcriber import transcribe_audio_file_fire_and_forget

LANGUAGE = LanguageCode(source="en")


@mock.patch("youtube_whisperer.transcriber.azure_transcriber.transcribe_audio_file", return_value=Path("audio.srt"))
def test_fire_and_forget_returns_future(mock_transcribe):
    future = transcribe_audio_file_fire_and_forget(Path("audio.wav"), LANGUAGE)
    assert future.result() == Path("audio.srt")
    mock_transcribe.assert_called_once_with(Path("audio.wav"), LANGUAGE, None, mock.ANY)


@mock.patch("youtube_whisperer.transcriber.azure_transcriber.transcribe_audio_file", side_effect=RuntimeError("bad credentials"))
def test_fire_and_forget_surfaces_exception_via_future(mock_transcribe):
    future = transcribe_audio_file_fire_and_forget(Path("audio.wav"), LANGUAGE)
    with pytest.raises(RuntimeError, match="bad credentials"):
        future.result()


@mock.patch("youtube_whisperer.transcriber.azure_transcriber.transcribe_audio_file", return_value=Path("out.srt"))
def test_fire_and_forget_passes_output_path_and_overwrite(mock_transcribe):
    output = Path("custom.srt")
    future = transcribe_audio_file_fire_and_forget(Path("audio.wav"), LANGUAGE, output_file_path=output, overwrite=OverwriteMode.NEVER)
    future.result()
    mock_transcribe.assert_called_once_with(Path("audio.wav"), LANGUAGE, output, OverwriteMode.NEVER)
