import builtins
import json
import subprocess
import sys
import threading
from pathlib import Path
from textwrap import dedent
from types import SimpleNamespace
from unittest import mock

import pytest
from pathlib_extensions import OverwriteMode

import youtube_whisperer.transcriber.azure_transcriber as testee
from youtube_whisperer.adaptors.lang_code_adaptor import LanguageCode
from youtube_whisperer.adaptors.srt_deduplicator import SrtBlock

LANGUAGE = LanguageCode(source="en")


@pytest.fixture(autouse=True)
def synthetic_azure_settings(mocker):
    """Supply inert credentials so Azure tests never inspect ambient settings."""
    settings = SimpleNamespace(azure_speech_api_key='test-subscription', azure_service_region='test-region')
    return mocker.patch.object(testee, 'Settings', return_value=settings)


class MockSpeechRecognitionResult:
    """Store the Azure result fields used by timestamp conversion."""

    def __init__(self, offset: int, duration: int, text: str):
        """Record timestamps in Azure ticks and the recognized text."""
        self.offset = offset
        self.duration = duration
        self.text = text


class CallbackOwner:
    """Own callback threads and account for work attempted after cancellation."""

    def __init__(self) -> None:
        """Allocate cancellation, thread ownership, and synchronized accounting."""
        self.cancelled = threading.Event()
        self._lock = threading.Lock()
        self._threads = []
        self.errors = []
        self.late_emissions = 0

    def start(self, callback, recognizer) -> None:
        """Run a callback under local exception accounting."""
        def run() -> None:
            """Capture callback exceptions without leaking worker failures globally."""
            try:
                callback(recognizer)
            except Exception as error:  # noqa: BLE001 - account for arbitrary SDK callback failures
                with self._lock:
                    self.errors.append(error)

        thread = threading.Thread(target=run)
        self._threads.append(thread)
        thread.start()

    def emit(self, callbacks, event) -> None:
        """Dispatch callbacks atomically against cancellation."""
        with self._lock:
            if self.cancelled.is_set():
                self.late_emissions += 1
                return
            for callback in callbacks:
                callback(event)

    def close(self) -> None:
        """Cancel callbacks and prove that all owned work has stopped."""
        with self._lock:
            self.cancelled.set()
        for thread in self._threads:
            thread.join(timeout=1)
            assert not thread.is_alive(), "Azure fake callback failed to quiesce"

    def assert_clean(self) -> None:
        """Report callback failures and work attempted after cancellation."""
        with self._lock:
            assert not self.errors, f"Azure fake callback errors: {self.errors!r}"
            assert self.late_emissions == 0


@pytest.fixture
def callback_owner():
    """Quiesce each test's callback work even when the test raises."""
    owner = CallbackOwner()
    yield owner
    owner.close()
    owner.assert_clean()


class FakeSignal:
    """Dispatch registered callbacks synchronously through an optional owner."""

    def __init__(self, owner=None) -> None:
        """Keep callbacks local and use owner cancellation when supplied."""
        self.callbacks = []
        self.owner = owner

    def connect(self, callback) -> None:
        """Register one callback in delivery order."""
        self.callbacks.append(callback)

    def emit(self, event) -> None:
        """Deliver the event or account for delivery attempted after cancellation."""
        if self.owner is not None:
            self.owner.emit(self.callbacks, event)
            return
        for callback in self.callbacks:
            callback(event)


class FakeSpeechRecognizerAsync:
    """Run Azure callbacks in one owned, cancellable worker thread."""

    def __init__(self, on_start, owner: CallbackOwner) -> None:
        """Attach signals and asynchronous work to one test-owned lifecycle."""
        self._on_start = on_start
        self.owner = owner
        self.recognized = FakeSignal(owner)
        self.canceled = FakeSignal(owner)
        self.session_stopped = FakeSignal(owner)
        self.stop_calls = 0

    def start_continuous_recognition(self) -> None:
        """Start one owned callback thread without waiting for its completion."""
        self.owner.start(self._on_start, self)

    def stop_continuous_recognition(self) -> None:
        """Record stop and cancel and join all owned callback work."""
        self.stop_calls += 1
        self.owner.close()


class FakeSpeechSDK:
    """Build synchronous or owned asynchronous Azure recognizer doubles."""

    class CancellationReason:
        """Expose a distinct error reason for cancellation callbacks."""

        Error = object()

    class audio:
        """Mirror the SDK namespace containing audio configuration."""

        class AudioConfig:
            """Record the filename supplied to the SDK without opening it."""

            def __init__(self, filename: str) -> None:
                """Keep the filename available for wiring assertions."""
                self.filename = filename

    def __init__(self, on_start, callback_owner: CallbackOwner | None = None) -> None:
        """Select direct callbacks or callbacks owned by the supplied lifecycle."""
        self._on_start = on_start
        self.callback_owner = callback_owner
        self.created_recognizer = None

    class SpeechConfig:
        """Record credentials and recognition language without contacting Azure."""

        def __init__(self, subscription: str | None, region: str | None) -> None:
            """Keep synthetic credentials available for wiring assertions."""
            self.subscription = subscription
            self.region = region
            self.speech_recognition_language = None

    def SpeechRecognizer(self, speech_config, audio_config):
        """Create a recognizer and retain its configuration for assertions."""
        if self.callback_owner is None:
            self.created_recognizer = FakeSpeechRecognizerSync(self._on_start)
        else:
            self.created_recognizer = FakeSpeechRecognizerAsync(self._on_start, self.callback_owner)
        self.created_speech_config = speech_config
        self.created_audio_config = audio_config
        return self.created_recognizer


class FakeSpeechRecognizerSync:
    """Synchronous variant: on_start is called directly in start_continuous_recognition."""

    def __init__(self, on_start) -> None:
        """Allocate synchronous signals and retain the startup callback."""
        self._on_start = on_start
        self.recognized = FakeSignal()
        self.canceled = FakeSignal()
        self.session_stopped = FakeSignal()
        self.stop_calls = 0

    def start_continuous_recognition(self) -> None:
        """Deliver startup callbacks directly in the calling thread."""
        self._on_start(self)

    def stop_continuous_recognition(self) -> None:
        """Record that synchronous recognition was stopped."""
        self.stop_calls += 1


def test_get_audio_duration_seconds_reads_soundfile_info(mocker, tmp_path):
    """Test that audio duration is read from soundfile metadata."""
    mocker.patch.object(testee.sf, "info", return_value=SimpleNamespace(duration=12.5))

    assert testee.get_audio_duration_seconds(tmp_path / "audio.wav") == 12.5


def test_recognition_result_to_srt_block():
    """Converts an Azure recognition result's offset/duration ticks into an SrtBlock."""
    segment = MockSpeechRecognitionResult(offset=10_000_000, duration=20_000_000, text="Hello world")
    result = testee.recognition_result_to_srt_block(segment)
    assert result == SrtBlock(start_time="00:00:01,000", end_time="00:00:03,000", content=["Hello world"])


@pytest.mark.parametrize('offset, duration, text, expected_start, expected_end, expected_content', [
    (5_000, 10_000, ' \nFirst\n  Second \t', '00:00:00,000', '00:00:00,002', ['First', '  Second']),
    (10_001, 5_000, '', '00:00:00,001', '00:00:00,002', ['']),
    (599_994_999, 1, 'text', '00:00:59,999', '00:01:00,000', ['text']),
    (35_999_995_000, 3_564_000_020_000, ' \n\t ', '01:00:00,000', '100:00:00,002', ['']),
    (20_000_000, -10_000_000, 'text', '00:00:02,000', '00:00:01,000', ['text']),
])
def test_recognition_result_to_srt_block_preserves_tick_precision_and_text(
    offset, duration, text, expected_start, expected_end, expected_content,
):
    """The public Azure wrapper adds ticks before conversion and retains exact SRT formatting."""
    segment = MockSpeechRecognitionResult(offset=offset, duration=duration, text=text)
    assert testee.recognition_result_to_srt_block(segment) == SrtBlock(expected_start, expected_end, expected_content)


@pytest.mark.parametrize('offset, duration', [(-1, 10_000_000), (0, -1)])
def test_recognition_result_to_srt_block_rejects_either_negative_timestamp(offset, duration):
    """Negative offsets and negative computed ends retain the public Azure converter assertion."""
    with pytest.raises(AssertionError, match='non-negative timestamp expected'):
        testee.recognition_result_to_srt_block(MockSpeechRecognitionResult(offset, duration, 'text'))


def test_recognition_result_to_srt_block_uses_neutral_conversion():
    """Azure forwards tick-derived seconds and unchanged text to the shared formatting owner."""
    segment = MockSpeechRecognitionResult(10_001, 5_000, ' \ntext \t')
    block = SrtBlock('shared start', 'shared end', ['shared content'])
    with mock.patch.object(testee, 'timestamps_to_srt_block', return_value=block) as convert:
        assert testee.recognition_result_to_srt_block(segment) is block
    convert.assert_called_once_with(0.0010001, 0.0015001, segment.text)


def test_recognition_result_to_srt_block_imports_no_whisper_or_ctranslate2(tmp_path):
    """A fresh Azure converter import and call attempt no Whisper/CTranslate2 imports or resources."""
    script = dedent('''
        import builtins
        import importlib.abc
        import json
        import os
        import socket
        import sys
        from pathlib import Path
        from types import ModuleType, SimpleNamespace
        from unittest.mock import patch

        import pydantic_settings
        import redis

        forbidden = ('faster_whisper', 'whisper', 'ctranslate2')
        attempts = []

        def check_import(name):
            """Record and reject every attempt to import an unselected engine."""
            if name.split('.')[0] in forbidden:
                attempts.append(name)
                raise AssertionError('unselected engine import: ' + name)

        native_import = builtins.__import__

        def guarded_import(name, *args, **kwargs):
            """Trap ordinary import attempts even if a module were already cached."""
            check_import(name)
            return native_import(name, *args, **kwargs)

        class ImportTrap(importlib.abc.MetaPathFinder):
            """Trap importlib requests that bypass the ordinary import hook."""

            def find_spec(self, fullname, path=None, target=None):
                """Reject forbidden module loading before its package executes."""
                check_import(fullname)
                return None

        for name in ('azure', 'azure.cognitiveservices', 'azure.cognitiveservices.speech', 'soundfile'):
            module = ModuleType(name)
            module.__path__ = []
            sys.modules[name] = module
        sys.modules['azure.cognitiveservices.speech'].SpeechRecognitionResult = SimpleNamespace
        assert not any(name.split('.')[0] in forbidden for name in sys.modules)
        sys.meta_path.insert(0, ImportTrap())

        with (
            patch.object(builtins, '__import__', guarded_import),
            patch.object(pydantic_settings.BaseSettings, '__init__', side_effect=AssertionError('Settings construction')),
            patch.object(redis.ConnectionPool, '__init__', side_effect=AssertionError('Redis pool construction')),
            patch.object(redis.Redis, '__init__', side_effect=AssertionError('Redis client construction')),
            patch.object(socket, 'socket', side_effect=AssertionError('network access')),
            patch.object(Path, 'is_file', side_effect=AssertionError('filesystem data probe')),
            patch.object(Path, 'is_dir', side_effect=AssertionError('filesystem data probe')),
            patch.object(Path, 'exists', side_effect=AssertionError('filesystem data probe')),
            patch.object(Path, 'open', side_effect=AssertionError('filesystem data access')),
        ):
            import youtube_whisperer.transcriber.azure_transcriber as testee
            assert Path(testee.__file__).is_relative_to(Path(os.environ['PYTHONPATH']))
            result = testee.recognition_result_to_srt_block(SimpleNamespace(
                offset=5_000, duration=10_000, text=' \\nFirst\\n  Second \\t',
            ))
            assert result == testee.SrtBlock('00:00:00,000', '00:00:00,002', ['First', '  Second'])
        assert attempts == []
        assert not any(name.split('.')[0] in forbidden for name in sys.modules)
        print(json.dumps({'attempts': attempts, 'start': result.start_time, 'end': result.end_time}))
    ''')
    environment = {
        'HOME': str(tmp_path),
        'TMPDIR': str(tmp_path),
        'PYTHONPATH': str(Path(testee.__file__).parents[2]),
        'PYTHONDONTWRITEBYTECODE': '1',
        'WHISPER_ASSETS_DIR': str(tmp_path / 'assets'),
        'WHISPER_MODELS_DIR': str(tmp_path / 'models'),
        'WHISPER_USE_CUDA': 'false',
        'WHISPER_MODEL': 'test-model',
        'REDIS_HOST': 'format.test.invalid',
        'REDIS_PORT': '6392',
    }
    result = subprocess.run(
        [sys.executable, '-c', script], cwd=tmp_path, env=environment,
        capture_output=True, text=True, check=False, timeout=10,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout) == {'attempts': [], 'start': '00:00:00,000', 'end': '00:00:00,002'}


def test_transcribe_audio_file_returns_existing_output_when_overwrite_denied(mocker, tmp_path, owned_path_probes, synthetic_azure_settings):
    """Test that an existing SRT is returned without contacting Azure when overwrite is denied."""
    input_path = tmp_path / "audio.wav"
    output_path = tmp_path / "audio.srt"
    output_path.write_text("existing")
    mock_overwrite = mocker.patch.object(testee, "overwrite_existing_path", return_value=False)
    mock_speech = mocker.patch.object(testee.speechsdk, "SpeechConfig")

    with owned_path_probes():
        result = testee.transcribe_audio_file(
            input_path,
            LANGUAGE,
            overwrite=OverwriteMode.NEVER,
        )

    assert result == output_path
    mock_overwrite.assert_called_once_with(output_path, OverwriteMode.NEVER)
    mock_speech.assert_not_called()
    synthetic_azure_settings.assert_not_called()


@pytest.mark.parametrize('subscription, region', [
    ('test-subscription', 'test-region'),
    ('alternate-subscription', 'alternate-region'),
])
def test_transcribe_audio_file_successfully_saves_srt(mocker, tmp_path, owned_path_probes, synthetic_azure_settings, subscription, region):
    """Test that recognized non-empty results are saved as a deduplicated SRT."""
    synthetic_azure_settings.return_value = SimpleNamespace(
        azure_speech_api_key=subscription,
        azure_service_region=region,
    )
    def on_start(recognizer: FakeSpeechRecognizerSync) -> None:
        """Emit non-empty and empty recognition results before completing."""
        recognizer.recognized.emit(SimpleNamespace(result=SimpleNamespace(text="hello")))
        recognizer.recognized.emit(SimpleNamespace(result=SimpleNamespace(text="")))
        recognizer.session_stopped.emit(SimpleNamespace())

    fake_speechsdk = FakeSpeechSDK(on_start)
    language = mock.Mock(get_source_as_BCP=mock.Mock(return_value="en-US"))
    input_path = tmp_path / "audio.wav"
    output_path = tmp_path / "audio.srt"

    with mock.patch.object(testee, "speechsdk", fake_speechsdk), \
         mock.patch.object(testee, "get_audio_duration_seconds", return_value=0.01), \
         mock.patch.object(testee, "recognition_result_to_srt_block", side_effect=lambda r: r), \
         mock.patch.object(testee, "save_segments_as_srt") as save_mock, \
         owned_path_probes():
        result = testee.transcribe_audio_file(input_path, language)

    assert result == output_path
    synthetic_azure_settings.assert_called_once_with()
    assert fake_speechsdk.created_speech_config.subscription == subscription
    assert fake_speechsdk.created_speech_config.region == region
    assert fake_speechsdk.created_speech_config.speech_recognition_language == "en-US"
    assert fake_speechsdk.created_audio_config.filename == str(input_path)
    save_mock.assert_called_once()
    blocks_iter, saved_output_path = save_mock.call_args.args
    assert saved_output_path == output_path
    assert save_mock.call_args.kwargs == {"deduplicate": True, "overwrite": OverwriteMode.PROMPT}
    saved = list(blocks_iter)
    assert len(saved) == 1 and saved[0].text == "hello"
    assert fake_speechsdk.created_recognizer.stop_calls == 1


@pytest.mark.parametrize('overwrite, existing_before_start', [
    (OverwriteMode.ALWAYS, True),
    (OverwriteMode.NEVER, True),
    (OverwriteMode.NEVER, False),
    (OverwriteMode.RENAME, True),
    (OverwriteMode.RENAME, False),
])
def test_transcribe_audio_file_honors_noninteractive_overwrite_policy(mocker, tmp_path, owned_path_probes, synthetic_azure_settings, overwrite, existing_before_start):
    """Keep or replace actual output according to policy without reading stdin."""
    input_path = tmp_path / 'audio.wav'
    output_path = tmp_path / 'audio.srt'
    prior_text = 'previous complete output'
    if existing_before_start:
        output_path.write_text(prior_text)

    def on_start(recognizer: FakeSpeechRecognizerSync) -> None:
        """Deliver real segment fields and a competing output before completion."""
        recognizer.recognized.emit(SimpleNamespace(result=MockSpeechRecognitionResult(0, 10_000_000, 'hello')))
        if not existing_before_start:
            output_path.write_text(prior_text)
        recognizer.session_stopped.emit(SimpleNamespace())

    fake_speechsdk = FakeSpeechSDK(on_start)
    mocker.patch.object(testee, 'speechsdk', fake_speechsdk)
    duration = mocker.patch.object(testee, 'get_audio_duration_seconds', return_value=0)
    stdin = mocker.patch.object(builtins, 'input', side_effect=AssertionError('Unexpected stdin read'))

    with owned_path_probes():
        result = testee.transcribe_audio_file(input_path, LanguageCode(source="en-us"), overwrite=overwrite)

    assert result == output_path
    stdin.assert_not_called()
    if overwrite == OverwriteMode.ALWAYS:
        assert output_path.read_text() == '1\n00:00:00,000 --> 00:00:01,000\nhello\n'
    else:
        assert output_path.read_text() == prior_text
    if overwrite in (OverwriteMode.NEVER, OverwriteMode.RENAME) and existing_before_start:
        assert fake_speechsdk.created_recognizer is None
        synthetic_azure_settings.assert_not_called()
        duration.assert_not_called()
    else:
        assert fake_speechsdk.created_recognizer.stop_calls == 1


@pytest.mark.parametrize('answer', ['y', 'n'])
def test_transcribe_audio_file_default_prompt_honors_competing_output_consent(mocker, tmp_path, owned_path_probes, answer):
    """Default PROMPT saves a competing output only after explicit consent."""
    output_path = tmp_path / 'audio.srt'
    prior_text = 'competing complete output'

    def on_start(recognizer: FakeSpeechRecognizerSync) -> None:
        """Publish a competing file during controlled synchronous recognition."""
        recognizer.recognized.emit(SimpleNamespace(result=MockSpeechRecognitionResult(0, 10_000_000, 'hello')))
        output_path.write_text(prior_text)
        recognizer.session_stopped.emit(SimpleNamespace())

    fake_speechsdk = FakeSpeechSDK(on_start)
    mocker.patch.object(testee, 'speechsdk', fake_speechsdk)
    mocker.patch.object(testee, 'get_audio_duration_seconds', return_value=0)
    stdin = mocker.patch.object(builtins, 'input', return_value=answer)

    with owned_path_probes():
        result = testee.transcribe_audio_file(tmp_path / 'audio.wav', LanguageCode(source='en-us'))

    assert result == output_path
    stdin.assert_called_once_with(f"Path '{output_path}' already exists. Overwrite? (y/N): ")
    expected = '1\n00:00:00,000 --> 00:00:01,000\nhello\n' if answer == 'y' else prior_text
    assert output_path.read_text() == expected
    assert fake_speechsdk.created_recognizer.stop_calls == 1


@pytest.mark.parametrize('answer', ['y', 'n'])
def test_transcribe_audio_file_existing_prompt_is_decided_once(mocker, tmp_path, owned_path_probes, answer):
    """Existing-output consent occurs once before recognition and is reused for atomic saving."""
    output = tmp_path / 'audio.srt'
    output.write_text('original')

    def on_start(recognizer: FakeSpeechRecognizerSync) -> None:
        """Complete a synchronous test-owned recognition without background callbacks."""
        recognizer.recognized.emit(SimpleNamespace(result=MockSpeechRecognitionResult(0, 10_000_000, 'hello')))
        recognizer.session_stopped.emit(SimpleNamespace())

    fake_speechsdk = FakeSpeechSDK(on_start)
    mocker.patch.object(testee, 'speechsdk', fake_speechsdk)
    duration = mocker.patch.object(testee, 'get_audio_duration_seconds', return_value=0)
    stdin = mocker.patch.object(builtins, 'input', return_value=answer)
    with owned_path_probes():
        assert testee.transcribe_audio_file(tmp_path / 'audio.wav', LanguageCode(source='en-us')) == output
    stdin.assert_called_once_with(f"Path '{output}' already exists. Overwrite? (y/N): ")
    expected = '1\n00:00:00,000 --> 00:00:01,000\nhello\n' if answer == 'y' else 'original'
    assert output.read_text() == expected
    if answer == 'y':
        assert fake_speechsdk.created_recognizer.stop_calls == 1
        duration.assert_called_once()
    else:
        assert fake_speechsdk.created_recognizer is None
        duration.assert_not_called()


def test_transcribe_audio_file_waits_for_delayed_callback(mocker, tmp_path, owned_path_probes, callback_owner):
    """Test that completion follows an owned callback released after waiting begins."""
    class ControlledCompletion:
        """Release a callback only after the transcription wait has started."""

        def __init__(self) -> None:
            """Allocate explicit wait-entry and completion signals."""
            self.completed = threading.Event()
            self.wait_entered = threading.Event()
            self.timeout = None

        def wait(self, timeout):
            """Record the requested timeout and wait for controlled completion."""
            self.timeout = timeout
            self.wait_entered.set()
            return self.completed.wait(timeout=1)

        def set(self):
            """Signal completion after callback delivery."""
            self.completed.set()

    completion = ControlledCompletion()

    def on_start(recognizer: FakeSpeechRecognizerAsync) -> None:
        """Emit results after wait entry instead of relying on elapsed time."""
        assert completion.wait_entered.wait(timeout=1)
        recognizer.recognized.emit(SimpleNamespace(result=SimpleNamespace(text="delayed")))
        recognizer.session_stopped.emit(SimpleNamespace())

    fake_speechsdk = FakeSpeechSDK(on_start, callback_owner)
    language = mock.Mock(get_source_as_BCP=mock.Mock(return_value="en-US"))
    mocker.patch.object(testee, "threading", SimpleNamespace(Event=lambda: completion))

    with (
        mock.patch.object(testee, "speechsdk", fake_speechsdk),
        mock.patch.object(testee, "get_audio_duration_seconds", return_value=0),
        mock.patch.object(testee, "recognition_result_to_srt_block", side_effect=lambda result: result),
        mock.patch.object(testee, "save_segments_as_srt") as save_mock,
        owned_path_probes(),
    ):
        result = testee.transcribe_audio_file(tmp_path / "audio.wav", language)

    assert result == tmp_path / "audio.srt"
    assert completion.timeout == 60.0
    assert fake_speechsdk.created_recognizer.stop_calls == 1
    assert next(iter(save_mock.call_args.args[0])).text == "delayed"


def test_transcribe_audio_file_times_out_and_stops_recognition(mocker, tmp_path, owned_path_probes, callback_owner):
    """Test that controlled timeout cancels and joins a pending callback."""
    fake_speechsdk = FakeSpeechSDK(lambda recognizer: recognizer.owner.cancelled.wait(), callback_owner)
    language = mock.Mock(get_source_as_BCP=mock.Mock(return_value="en-US"))
    completion = mock.Mock()
    completion.wait.return_value = False
    mocker.patch.object(testee, "threading", SimpleNamespace(Event=lambda: completion))

    with (
        mock.patch.object(testee, "speechsdk", fake_speechsdk),
        mock.patch.object(testee, "get_audio_duration_seconds", return_value=0),
        owned_path_probes(),
        pytest.raises(TimeoutError, match="Transcription timed out"),
    ):
        testee.transcribe_audio_file(tmp_path / "audio.wav", language)

    assert fake_speechsdk.created_recognizer.stop_calls == 1
    completion.wait.assert_called_once_with(60.0)
    assert callback_owner.cancelled.is_set()


@pytest.mark.parametrize("duration, expected_timeout", [(0, 60.0), (10, 60.0), (1000, 1500.0)])
def test_transcribe_audio_file_applies_timeout_floor(mocker, tmp_path, owned_path_probes, duration, expected_timeout):
    """Test that the timeout is floored so short/zero-duration clips still allow Azure session startup."""
    recorded = {}

    class FakeEvent:
        """Record the timeout while completing immediately."""

        def wait(self, timeout):
            """Capture the timeout and report successful completion."""
            recorded["timeout"] = timeout
            return True  # pretend Azure completed so the call returns without blocking

        def set(self):
            """Accept completion signals without creating asynchronous state."""

    fake_speechsdk = FakeSpeechSDK(lambda recognizer: None)
    language = mock.Mock(get_source_as_BCP=mock.Mock(return_value="en-US"))
    mocker.patch.object(testee, "threading", SimpleNamespace(Event=lambda: FakeEvent()))
    mocker.patch.object(testee, "get_audio_duration_seconds", return_value=duration)
    mocker.patch.object(testee, "save_segments_as_srt")

    with mock.patch.object(testee, "speechsdk", fake_speechsdk), owned_path_probes():
        testee.transcribe_audio_file(tmp_path / "audio.wav", language)

    assert recorded["timeout"] == expected_timeout


def test_transcribe_audio_file_surfaces_azure_cancellation_error_without_timing_out(tmp_path, owned_path_probes, callback_owner):
    """Test that an Azure cancellation error is surfaced instead of timing out."""
    error_details = "bad credentials"

    def on_start(recognizer: FakeSpeechRecognizerAsync) -> None:
        """Emit the synthetic Azure error through the owned callback thread."""
        event = SimpleNamespace(
            cancellation_details=SimpleNamespace(
                reason=FakeSpeechSDK.CancellationReason.Error,
                error_details=error_details,
            )
        )
        recognizer.canceled.emit(event)

    fake_speechsdk = FakeSpeechSDK(on_start, callback_owner)
    language = mock.Mock(get_source_as_BCP=mock.Mock(return_value="en-us"))

    with (
        mock.patch.object(testee, "speechsdk", fake_speechsdk),
        mock.patch.object(testee, "get_audio_duration_seconds", return_value=0.01),
        mock.patch.object(testee, "save_segments_as_srt") as save_mock,
        owned_path_probes(),
        pytest.raises(RuntimeError, match=error_details),
    ):
        testee.transcribe_audio_file(tmp_path / "audio.wav", language)

    assert fake_speechsdk.created_recognizer is not None
    assert fake_speechsdk.created_recognizer.stop_calls == 1
    save_mock.assert_not_called()


def test_async_fake_accounts_for_callback_failure():
    """Test that a callback exception is captured locally and its thread exits."""
    owner = CallbackOwner()

    def fail(_recognizer) -> None:
        """Raise a controlled callback error for local accounting."""
        raise ValueError("callback failed")

    owner.start(fail, object())
    owner.close()

    assert len(owner.errors) == 1
    assert isinstance(owner.errors[0], ValueError)
    assert str(owner.errors[0]) == "callback failed"


def test_transcribe_audio_file_uses_supplied_credentials_after_environment_mutation(mocker, monkeypatch, tmp_path, synthetic_azure_settings):
    """Two supplied Azure snapshots bypass ambient credentials and Settings construction."""
    from youtube_whisperer.config import Settings

    snapshots = [Settings(azure_speech_api_key=name + '-key', azure_service_region=name + '-region')
                 for name in ['first', 'second']]
    monkeypatch.setenv('AZURE_SPEECH_API_KEY', 'changed-key')
    monkeypatch.setenv('AZURE_SERVICE_REGION', 'changed-region')
    synthetic_azure_settings.side_effect = AssertionError('ambient settings')
    sdk = FakeSpeechSDK(lambda recognizer: recognizer.session_stopped.emit(SimpleNamespace()))
    mocker.patch.object(testee, 'speechsdk', sdk)
    mocker.patch.object(testee, 'get_audio_duration_seconds', return_value=0)
    mocker.patch.object(testee, 'save_segments_as_srt')
    for index, snapshot in enumerate(snapshots):
        testee.transcribe_audio_file(tmp_path / f'{index}.wav', LanguageCode('en-us'), settings=snapshot)
        assert sdk.created_speech_config.subscription == snapshot.azure_speech_api_key
        assert sdk.created_speech_config.region == snapshot.azure_service_region
    synthetic_azure_settings.assert_not_called()


def test_standalone_azure_defaults_observe_current_owned_environment(mocker, monkeypatch, tmp_path, synthetic_azure_settings):
    """Successive uncached Azure invocations resolve newly supplied environment credentials."""
    from youtube_whisperer.config import Settings

    synthetic_azure_settings.side_effect = Settings
    sdk = FakeSpeechSDK(lambda recognizer: recognizer.session_stopped.emit(SimpleNamespace()))
    mocker.patch.object(testee, 'speechsdk', sdk)
    mocker.patch.object(testee, 'get_audio_duration_seconds', return_value=0)
    mocker.patch.object(testee, 'save_segments_as_srt')
    for name in ['first', 'second']:
        monkeypatch.setenv('AZURE_SPEECH_API_KEY', name + '-key')
        monkeypatch.setenv('AZURE_SERVICE_REGION', name + '-region')
        testee.transcribe_audio_file(tmp_path / f'{name}.wav', LanguageCode('en-us'))
        assert sdk.created_speech_config.subscription == name + '-key'
        assert sdk.created_speech_config.region == name + '-region'
    assert synthetic_azure_settings.call_count == 2


def test_callback_owner_fixture_quiesces_after_test_assertion_fails(tmp_path):
    """Test that actual pytest failure teardown cancels and joins callback work."""
    (tmp_path / "conftest.py").write_text(dedent('''
        import importlib.util
        import json
        import os
        import threading
        from pathlib import Path

        import pytest

        spec = importlib.util.spec_from_file_location('azure_helpers', os.environ['AZURE_TEST_HELPERS'])
        helpers = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helpers)
        callback_owner = helpers.callback_owner
        state = {}

        @pytest.fixture
        def pending_callback(callback_owner):
            """Hold owned work until fixture teardown explicitly joins it."""
            started = threading.Event()
            release = threading.Event()
            finished = threading.Event()

            def callback(_recognizer):
                """Remain alive after cancellation until the owned join begins."""
                started.set()
                callback_owner.cancelled.wait()
                release.wait()
                finished.set()

            callback_owner.start(callback, object())
            thread = callback_owner._threads[-1]
            native_join = thread.join

            def releasing_join(timeout=None):
                """Release the callback and delegate to the real thread join."""
                release.set()
                native_join(timeout)

            thread.join = releasing_join
            state.update(owner=callback_owner, thread=thread, release=release,
                         finished=finished, native_join=native_join)
            assert started.wait(timeout=1)

        @pytest.hookimpl(hookwrapper=True)
        def pytest_runtest_teardown(item, nextitem):
            """Audit real fixture teardown before independently cleaning mutants."""
            try:
                yield
            finally:
                if state:
                    thread = state['thread']
                    audit = {
                        'cancelled': state['owner'].cancelled.is_set(),
                        'finished': state['finished'].is_set(),
                        'alive': thread.is_alive(),
                    }
                    try:
                        Path('audit.json').write_text(json.dumps(audit))
                    finally:
                        state['owner'].cancelled.set()
                        state['release'].set()
                        state['native_join'](timeout=1)
                        assert not thread.is_alive(), 'Harness callback did not stop'
    '''))
    (tmp_path / "test_failure.py").write_text(dedent('''
        def test_injected_assertion(pending_callback):
            """Exercise fixture finalization after a controlled test failure."""
            raise AssertionError('injected assertion')
    '''))
    (tmp_path / "pytest.ini").write_text("[pytest]\n")
    environment = {
        'HOME': str(tmp_path),
        'TMPDIR': str(tmp_path),
        'PYTHONPATH': str(Path(__file__).resolve().parents[2]),
        'PYTHONDONTWRITEBYTECODE': '1',
        'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1',
        'AZURE_TEST_HELPERS': str(Path(__file__).resolve()),
        'REDIS_HOST': 'queue.invalid',
        'REDIS_PORT': '6381',
        'WHISPER_ASSETS_DIR': str(tmp_path / 'assets'),
        'WHISPER_MODELS_DIR': str(tmp_path / 'models'),
    }

    result = subprocess.run(
        [sys.executable, '-m', 'pytest', '-p', 'pytest_cov', '--no-cov', '-q', 'test_failure.py'],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )

    assert result.returncode == 1, result.stdout + result.stderr
    assert '1 failed' in result.stdout
    assert 'injected assertion' in result.stdout
    assert 'ERROR' not in result.stdout, result.stdout + result.stderr
    assert json.loads((tmp_path / 'audit.json').read_text()) == {
        'cancelled': True,
        'finished': True,
        'alive': False,
    }


def test_async_fake_accounts_for_late_emission_without_mutation():
    """Test that emissions after cancellation are counted and not dispatched."""
    owner = CallbackOwner()
    received = []
    signal = FakeSignal(owner)
    signal.connect(received.append)

    owner.close()
    signal.emit("late")

    assert received == []
    assert owner.late_emissions == 1
