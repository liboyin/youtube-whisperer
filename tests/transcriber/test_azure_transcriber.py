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
        self.created_speech_config = speech_config
        self.created_audio_config = audio_config
        return self.created_recognizer


class FakeSpeechRecognizerSync:
    """Synchronous variant: on_start is called directly in start_continuous_recognition."""

    def __init__(self, on_start) -> None:
        self._on_start = on_start
        self.recognized = FakeSignal()
        self.canceled = FakeSignal()
        self.session_stopped = FakeSignal()
        self.stop_calls = 0

    def start_continuous_recognition(self) -> None:
        self._on_start(self)

    def stop_continuous_recognition(self) -> None:
        self.stop_calls += 1


class FakeSpeechSDKSync:
    """Variant of FakeSpeechSDK that uses FakeSpeechRecognizerSync."""

    class CancellationReason:
        Error = object()

    class audio:
        class AudioConfig:
            def __init__(self, filename: str) -> None:
                self.filename = filename

    class SpeechConfig:
        def __init__(self, subscription: str | None, region: str | None) -> None:
            self.subscription = subscription
            self.region = region
            self.speech_recognition_language = None

    def __init__(self, on_start) -> None:
        self._on_start = on_start
        self.created_recognizer = None

    def SpeechRecognizer(self, speech_config, audio_config):
        self.created_recognizer = FakeSpeechRecognizerSync(self._on_start)
        self.created_speech_config = speech_config
        self.created_audio_config = audio_config
        return self.created_recognizer


def test_get_audio_duration_seconds_reads_soundfile_info(mocker):
    mocker.patch.object(testee.sf, "info", return_value=SimpleNamespace(duration=12.5))

    assert testee.get_audio_duration_seconds(Path("audio.wav")) == 12.5


def test_transcribe_audio_file_returns_existing_output_when_overwrite_denied(mocker, tmp_path):
    input_path = tmp_path / "audio.wav"
    output_path = tmp_path / "audio.srt"
    output_path.write_text("existing")
    mock_overwrite = mocker.patch.object(testee, "overwrite_existing_path", return_value=False)
    mock_speech = mocker.patch.object(testee.speechsdk, "SpeechConfig")

    result = testee.transcribe_audio_file(
        input_path,
        LANGUAGE,
        output_file_path=output_path,
        overwrite=OverwriteMode.NEVER,
    )

    assert result == output_path
    mock_overwrite.assert_called_once_with(output_path, OverwriteMode.NEVER)
    mock_speech.assert_not_called()


def test_transcribe_audio_file_successfully_saves_srt(mocker):
    def on_start(recognizer: FakeSpeechRecognizerSync) -> None:
        recognizer.recognized.emit(SimpleNamespace(result=SimpleNamespace(text="hello")))
        recognizer.recognized.emit(SimpleNamespace(result=SimpleNamespace(text="")))
        recognizer.session_stopped.emit(SimpleNamespace())

    fake_speechsdk = FakeSpeechSDKSync(on_start)
    language = mock.Mock(get_source_as_BCP=mock.Mock(return_value="en-US"))
    adaptor = mock.Mock()

    with mock.patch.object(testee, "speechsdk", fake_speechsdk), \
         mock.patch.object(testee, "get_audio_duration_seconds", return_value=0.01), \
         mock.patch.object(testee, "AzureRecognitionResultAdaptor", return_value=adaptor):
        result = testee.transcribe_audio_file(Path("audio.wav"), language)

    assert result == Path("audio.srt")
    assert fake_speechsdk.created_speech_config.speech_recognition_language == "en-US"
    assert fake_speechsdk.created_audio_config.filename == "audio.wav"
    adaptor.append.assert_called_once()
    adaptor.save_as_srt_file.assert_called_once_with(Path("audio.srt"), deduplicate=True)
    assert fake_speechsdk.created_recognizer.stop_calls == 1


def test_transcribe_audio_file_times_out_and_stops_recognition():
    fake_speechsdk = FakeSpeechSDKSync(lambda recognizer: None)
    language = mock.Mock(get_source_as_BCP=mock.Mock(return_value="en-US"))

    with mock.patch.object(testee, "speechsdk", fake_speechsdk), \
         mock.patch.object(testee, "get_audio_duration_seconds", return_value=0):
        with pytest.raises(TimeoutError, match="Transcription timed out"):
            testee.transcribe_audio_file(Path("audio.wav"), language)

    assert fake_speechsdk.created_recognizer.stop_calls == 1


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

    with mock.patch.object(testee, "speechsdk", fake_speechsdk), \
         mock.patch.object(testee, "get_audio_duration_seconds", return_value=0.01), \
         mock.patch.object(testee, "AzureRecognitionResultAdaptor", return_value=adaptor):
        with pytest.raises(RuntimeError, match=error_details):
            testee.transcribe_audio_file(Path("audio.wav"), language)

    assert fake_speechsdk.created_recognizer is not None
    assert fake_speechsdk.created_recognizer.stop_calls == 1
    adaptor.save_as_srt_file.assert_not_called()
