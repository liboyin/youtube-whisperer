import atexit
import os
import sys
from contextlib import ExitStack, contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest

# Explicit compatibility-resource access or helper calls can resolve configuration during
# collection. Establish owned values first, then restore the inherited process environment.
if any(name in sys.modules for name in ('youtube_whisperer.config', 'youtube_whisperer.utils')):
    raise pytest.UsageError('Run tests in a fresh Python process; application settings were imported before test isolation.')
_bootstrap_cleanup = ExitStack()
atexit.register(_bootstrap_cleanup.close)
try:
    _bootstrap_root = Path(_bootstrap_cleanup.enter_context(TemporaryDirectory(prefix='youtube-whisperer-tests-')))
    _bootstrap_env = _bootstrap_cleanup.enter_context(pytest.MonkeyPatch.context())
    _synthetic_values = {
        'HOME': str(_bootstrap_root),
        'WHISPER_ASSETS_DIR': str(_bootstrap_root / 'assets'),
        'WHISPER_MODELS_DIR': str(_bootstrap_root / 'models'),
        'WHISPER_USE_CUDA': 'false',
        'WHISPER_MODEL': 'test-model',
        'REDIS_HOST': 'queue.test.invalid',
        'REDIS_PORT': '6389',
        'WORKER_SLOT_ID': 'test-slot',
        'WORKER_ROLE': 'whisper',
        'WORKER_CLAIM_MIN_IDLE_SECONDS': '17',
    }
    _removed_names = ('AZURE_SPEECH_API_KEY', 'AZURE_SERVICE_REGION', 'ASSETS_DIR', 'FIREFOX_PROFILE_DIR', 'WHISPER_MODELS_VOLUME')
    _controlled_names = {name.lower() for name in (*_synthetic_values, *_removed_names)}
    # Pydantic normalizes case. Reverse deletion preserves alias precedence during undo.
    for name in reversed(tuple(os.environ)):
        if name.lower() in _controlled_names:
            _bootstrap_env.delenv(name)
    for name, value in _synthetic_values.items():
        _bootstrap_env.setenv(name, value)
except BaseException:
    _bootstrap_cleanup.close()
    atexit.unregister(_bootstrap_cleanup.close)
    raise


def pytest_unconfigure(config):
    """Restore inherited environment and remove the collection-owned directory."""
    _bootstrap_cleanup.close()
    atexit.unregister(_bootstrap_cleanup.close)


@pytest.fixture
def owned_path_probes(tmp_path):
    """Scope filesystem probe guards to the operation under test."""

    @contextmanager
    def guard():
        """Reject file and directory probes outside the test's temporary tree."""
        with ExitStack() as stack:
            for method_name in ("is_file", "is_dir", "exists"):
                original = getattr(Path, method_name)

                def guarded(path, *args, _original=original, **kwargs):
                    """Delegate only probes whose target belongs to the requesting test."""
                    assert path.is_relative_to(tmp_path), f"Unowned filesystem probe: {path}"
                    return _original(path, *args, **kwargs)

                stack.enter_context(patch.object(Path, method_name, guarded))
            yield

    return guard


@pytest.fixture
def caption_http(monkeypatch):
    """Own caption sessions and a scripted adapter while forbidding real HTTP transport."""
    import json

    import requests
    from requests.adapters import HTTPAdapter

    import youtube_whisperer.downloaders.transcript_downloader as testee

    class CaptionAdapter(HTTPAdapter):
        """Serve synthetic watch, innertube and caption responses without sockets."""

        def __init__(self):
            """Initialize per-test request accounting and controlled failures."""
            super().__init__()
            self.calls = []
            self.closed = False
            self.failure_at = None
            self.failure = None
            self.disabled = False
            self.language = 'en'

        def send(self, request, **kwargs):
            """Return controlled payloads or a finite-timeout simulated stall failure."""
            assert not self.closed, 'Caption session closed before fetch completed'
            phase = 'innertube' if request.method == 'POST' else 'caption' if request.url.startswith('https://captions.test.invalid/') else 'watch'
            timeout = kwargs.get('timeout')
            self.calls.append((phase, timeout))
            # A missing timeout completes synthetically instead of hanging the test.
            if (self.failure_at == phase and self.failure is not None
                    and (not isinstance(self.failure, requests.Timeout) or timeout is not None)):
                raise self.failure
            response = requests.Response()
            response.status_code = 200
            response.url = request.url
            response.request = request
            if phase == 'watch':
                text = '{"INNERTUBE_API_KEY": "owned-key"}'
            elif phase == 'innertube':
                data = {'playabilityStatus': {'status': 'OK'}}
                if not self.disabled:
                    data['captions'] = {'playerCaptionsTracklistRenderer': {'captionTracks': [{
                        'baseUrl': 'https://captions.test.invalid/transcript',
                        'name': {'runs': [{'text': 'Owned language'}]},
                        'languageCode': self.language,
                    }]}}
                text = json.dumps(data)
            else:
                text = '<transcript><text start="0" dur="1">Owned captions</text></transcript>'
            response._content = text.encode()
            response.encoding = 'utf-8'
            return response

        def close(self):
            """Record transport closure while releasing adapter resources."""
            self.closed = True
            super().close()

    adapter = CaptionAdapter()
    sessions = []
    original_init = testee.CaptionSession.__init__

    def owned_init(session):
        """Mount the test-owned adapter on every caption session before requests."""
        original_init(session)
        session.trust_env = False
        session.mount('https://', adapter)
        session.mount('http://', adapter)
        sessions.append(session)

    def forbid_real_transport(*args, **kwargs):
        """Fail before any HTTP transport can open a real socket."""
        raise AssertionError('Real HTTP transport is forbidden by caption_http')

    monkeypatch.setattr(testee.CaptionSession, '__init__', owned_init)
    monkeypatch.setattr(HTTPAdapter, 'send', forbid_real_transport)
    try:
        yield adapter
    finally:
        for session in sessions:
            session.close()
        adapter.close()
