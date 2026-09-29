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
