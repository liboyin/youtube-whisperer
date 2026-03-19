from pathlib import Path
import threading
from types import SimpleNamespace
from unittest import mock

import pytest

from pathlib_extensions import OverwriteMode

from youtube_whisperer.adaptors.lang_code_adaptor import LanguageCode
from youtube_whisperer.transcriber import azure_transcriber as testee

LANGUAGE = LanguageCode(source="en")


class FakeSignal:
    def __init__(self) -> None:
        self.callbacks = []

    def connect(self, callback) -> None:
        self.callbacks.append(callback)

    def emit(self, event) -> None:
        for callback in self.callbacks:
            callback(event)


class FakeSpeechRecognizer:
    def __init__(self, on_start) -> None:
        self._on_start = on_start
        self.recognized = FakeSignal()
        self.canceled = FakeSignal()
        self.session_stopped = FakeSignal()
        self.stop_calls = 0

    def start_continuous_recognition(self) -> None:
        threading.Thread(target=self._on_start, args=(self,), daemon=True).start()

    def stop_continuous_recognition(self) -> None:
        self.stop_calls += 1


class FakeSpeechSDK:
    class CancellationReason:
        Error = object()

    class audio:
        class AudioConfig:
            def __init__(self, filename: str) -> None:
                self.filename = filename

    def __init__(self, on_start) -> None:
        self._on_start = on_start
        self.created_recognizer = None

    class SpeechConfig:
        def __init__(self, subscription: str | None, region: str | None) -> None:
            self.subscription = subscription
            self.region = region
            self.speech_recognition_language = None

    def SpeechRecognizer(self, speech_config, audio_config):
        self.created_recognizer = FakeSpeechRecognizer(self._on_start)
        return self.created_recognizer


@mock.patch("youtube_whisperer.transcriber.azure_transcriber.transcribe_audio_file", return_value=Path("audio.srt"))
def test_fire_and_forget_returns_future(mock_transcribe):
    future = testee.transcribe_audio_file_fire_and_forget(Path("audio.wav"), LANGUAGE)
    assert future.result() == Path("audio.srt")
    mock_transcribe.assert_called_once_with(Path("audio.wav"), LANGUAGE, None, mock.ANY)


@mock.patch("youtube_whisperer.transcriber.azure_transcriber.transcribe_audio_file", side_effect=RuntimeError("bad credentials"))
def test_fire_and_forget_surfaces_exception_via_future(mock_transcribe):
    future = testee.transcribe_audio_file_fire_and_forget(Path("audio.wav"), LANGUAGE)
    with pytest.raises(RuntimeError, match="bad credentials"):
        future.result()


@mock.patch("youtube_whisperer.transcriber.azure_transcriber.transcribe_audio_file", return_value=Path("out.srt"))
def test_fire_and_forget_passes_output_path_and_overwrite(mock_transcribe):
    output = Path("custom.srt")
    future = testee.transcribe_audio_file_fire_and_forget(Path("audio.wav"), LANGUAGE, output_file_path=output, overwrite=OverwriteMode.NEVER)
    future.result()
    mock_transcribe.assert_called_once_with(Path("audio.wav"), LANGUAGE, output, OverwriteMode.NEVER)


def test_transcribe_audio_file_surfaces_azure_cancellation_error_without_timing_out():
    error_details = "bad credentials"

    def on_start(recognizer: FakeSpeechRecognizer) -> None:
        event = SimpleNamespace(
            cancellation_details=SimpleNamespace(
                reason=FakeSpeechSDK.CancellationReason.Error,
                error_details=error_details,
            )
        )
        recognizer.canceled.emit(event)

    fake_speechsdk = FakeSpeechSDK(on_start)
    language = mock.Mock(get_source_as_BCP=mock.Mock(return_value="en-us"))
    adaptor = mock.Mock()

    with mock.patch.object(testee.azure_transcriber, "speechsdk", fake_speechsdk), \
         mock.patch.object(testee.azure_transcriber, "get_audio_duration_seconds", return_value=0.01), \
         mock.patch.object(testee.azure_transcriber, "AzureRecognitionResultAdaptor", return_value=adaptor):
        with pytest.raises(RuntimeError, match=error_details):
            testee.azure_transcriber.transcribe_audio_file(Path("audio.wav"), language)

    assert fake_speechsdk.created_recognizer is not None
    assert fake_speechsdk.created_recognizer.stop_calls == 1
    adaptor.save_as_srt_file.assert_not_called()
