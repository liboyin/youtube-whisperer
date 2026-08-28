import threading
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest
from pathlib_extensions import OverwriteMode

from youtube_whisperer.adaptors.lang_code_adaptor import LanguageCode
from youtube_whisperer.adaptors.srt_deduplicator import SrtBlock
from youtube_whisperer.transcriber import azure_transcriber as testee

LANGUAGE = LanguageCode(source="en")


class MockSpeechRecognitionResult:
    def __init__(self, offset: int, duration: int, text: str):
        self.offset = offset
        self.duration = duration
        self.text = text


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
    """Test that audio duration is read from soundfile metadata."""
    mocker.patch.object(testee.sf, "info", return_value=SimpleNamespace(duration=12.5))

    assert testee.get_audio_duration_seconds(Path("audio.wav")) == 12.5


def test_recognition_result_to_srt_block():
    """Converts an Azure recognition result's offset/duration ticks into an SrtBlock."""
    segment = MockSpeechRecognitionResult(offset=10_000_000, duration=20_000_000, text="Hello world")
    result = testee.recognition_result_to_srt_block(segment)
    assert result == SrtBlock(start_time="00:00:01,000", end_time="00:00:03,000", content=["Hello world"])


def test_transcribe_audio_file_returns_existing_output_when_overwrite_denied(mocker, tmp_path):
    """Test that an existing SRT is returned without contacting Azure when overwrite is denied."""
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
    """Test that recognized non-empty results are saved as a deduplicated SRT."""
    def on_start(recognizer: FakeSpeechRecognizerSync) -> None:
        recognizer.recognized.emit(SimpleNamespace(result=SimpleNamespace(text="hello")))
        recognizer.recognized.emit(SimpleNamespace(result=SimpleNamespace(text="")))
        recognizer.session_stopped.emit(SimpleNamespace())

    fake_speechsdk = FakeSpeechSDKSync(on_start)
    language = mock.Mock(get_source_as_BCP=mock.Mock(return_value="en-US"))

    with mock.patch.object(testee, "speechsdk", fake_speechsdk), \
         mock.patch.object(testee, "get_audio_duration_seconds", return_value=0.01), \
         mock.patch.object(testee, "recognition_result_to_srt_block", side_effect=lambda r: r), \
         mock.patch.object(testee, "save_segments_as_srt") as save_mock:
        result = testee.transcribe_audio_file(Path("audio.wav"), language)

    assert result == Path("audio.srt")
    assert fake_speechsdk.created_speech_config.speech_recognition_language == "en-US"
    assert fake_speechsdk.created_audio_config.filename == "audio.wav"
    save_mock.assert_called_once()
    blocks_iter, output_path = save_mock.call_args.args
    assert output_path == Path("audio.srt")
    assert save_mock.call_args.kwargs == {"deduplicate": True}
    saved = list(blocks_iter)
    assert len(saved) == 1 and saved[0].text == "hello"
    assert fake_speechsdk.created_recognizer.stop_calls == 1


def test_transcribe_audio_file_times_out_and_stops_recognition(mocker):
    """Test that recognition stops and raises when it exceeds the timeout."""
    fake_speechsdk = FakeSpeechSDKSync(lambda recognizer: None)
    language = mock.Mock(get_source_as_BCP=mock.Mock(return_value="en-US"))
    # Shrink the floor so the timeout path fires immediately instead of blocking for the real floor.
    mocker.patch.object(testee, "MIN_AZURE_TIMEOUT_SECONDS", 0.01)

    with (
        mock.patch.object(testee, "speechsdk", fake_speechsdk),
        mock.patch.object(testee, "get_audio_duration_seconds", return_value=0),
        pytest.raises(TimeoutError, match="Transcription timed out"),
    ):
        testee.transcribe_audio_file(Path("audio.wav"), language)

    assert fake_speechsdk.created_recognizer.stop_calls == 1


@pytest.mark.parametrize("duration, expected_timeout", [(0, 60.0), (10, 60.0), (1000, 1500.0)])
def test_transcribe_audio_file_applies_timeout_floor(mocker, duration, expected_timeout):
    """Test that the timeout is floored so short/zero-duration clips still allow Azure session startup."""
    recorded = {}

    class FakeEvent:
        def wait(self, timeout):
            recorded["timeout"] = timeout
            return True  # pretend Azure completed so the call returns without blocking

        def set(self):
            pass

    fake_speechsdk = FakeSpeechSDKSync(lambda recognizer: None)
    language = mock.Mock(get_source_as_BCP=mock.Mock(return_value="en-US"))
    mocker.patch.object(testee.threading, "Event", return_value=FakeEvent())
    mocker.patch.object(testee, "get_audio_duration_seconds", return_value=duration)
    mocker.patch.object(testee, "save_segments_as_srt")

    with mock.patch.object(testee, "speechsdk", fake_speechsdk):
        testee.transcribe_audio_file(Path("audio.wav"), language)

    assert recorded["timeout"] == expected_timeout


def test_transcribe_audio_file_surfaces_azure_cancellation_error_without_timing_out():
    """Test that an Azure cancellation error is surfaced instead of timing out."""
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

    with (
        mock.patch.object(testee, "speechsdk", fake_speechsdk),
        mock.patch.object(testee, "get_audio_duration_seconds", return_value=0.01),
        mock.patch.object(testee, "save_segments_as_srt") as save_mock,
        pytest.raises(RuntimeError, match=error_details),
    ):
        testee.transcribe_audio_file(Path("audio.wav"), language)

    assert fake_speechsdk.created_recognizer is not None
    assert fake_speechsdk.created_recognizer.stop_calls == 1
    save_mock.assert_not_called()
