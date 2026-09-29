"""Fresh-process checks for selected worker role imports."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

import youtube_whisperer.workers.__main__ as testee

_ISOLATED_PROBE = r'''
import builtins
import sys
from pathlib import Path
from unittest.mock import Mock, patch

families = ('faster_whisper', 'ctranslate2', 'azure.cognitiveservices', 'yt_dlp', 'youtube_transcript_api')
owned = {
    'youtube': ('yt_dlp', 'youtube_transcript_api'),
    'whisper': ('faster_whisper', 'ctranslate2'),
    'azure': ('azure.cognitiveservices',),
}
module_name = {
    'youtube': 'youtube_whisperer.workers.youtube_worker',
    'whisper': 'youtube_whisperer.workers.whisper_worker',
    'azure': 'youtube_whisperer.workers.azure_worker',
}
class_name = {'youtube': 'YouTubeWorker', 'whisper': 'WhisperWorker', 'azure': 'AzureWorker'}
case, role = sys.argv[1:]
allowed = owned[role] if case in ('selected', 'legacy') else ()
attempts = []
original_import = builtins.__import__

def guarded_import(name, *args, **kwargs):
    family = 'azure.cognitiveservices' if name.startswith('azure.cognitiveservices') else name.split('.', 1)[0]
    if family in families:
        attempts.append(family)
        if family not in allowed:
            raise AssertionError(f'forbidden import attempt: {name}')
    return original_import(name, *args, **kwargs)

builtins.__import__ = guarded_import
import youtube_whisperer.workers.__main__ as testee

if case == 'help':
    sys.argv = ['worker', '--help']
    try:
        testee.main()
    except SystemExit as exc:
        assert exc.code == 0
    else:
        raise AssertionError('help did not exit')
elif case == 'invalid_direct':
    try:
        testee.process_queue('remote')
    except ValueError as exc:
        assert str(exc) == 'Unsupported worker role: remote'
    else:
        raise AssertionError('invalid direct role accepted')
elif case == 'invalid_cli':
    sys.argv = ['worker', 'remote']
    try:
        testee.main()
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError('invalid CLI role accepted')
elif case == 'legacy':
    worker_class = getattr(testee, class_name[role])
    assert worker_class.__module__ == module_name[role]
    assert worker_class is getattr(sys.modules[module_name[role]], class_name[role])
elif case == 'selected':
    import youtube_whisperer.runtime as runtime_testee
    from youtube_whisperer.workers.common import BaseWorker
    settings = testee.Settings(worker_slot_id='owned', whisper_assets_dir=Path.home() / 'assets', whisper_models_dir=Path.home() / 'models')
    pool, client = Mock(), Mock()
    calls = []

    def bounded_run(self, poll_interval_seconds=5):
        calls.append((type(self).__name__, type(self).__module__, self.get_consumer_name(), poll_interval_seconds, self.runtime.settings is settings, self.runtime.client is client))

    with patch.object(runtime_testee, 'create_redis_pool', return_value=pool), patch.object(runtime_testee.redis, 'StrictRedis', return_value=client), patch.object(BaseWorker, 'process_queue', bounded_run):
        testee.process_queue(role, poll_interval_seconds=13, settings=settings)
    assert calls == [(class_name[role], module_name[role], role + '-owned', 13, True, True)], calls
    client.close.assert_called_once_with()
    pool.disconnect.assert_called_once_with()

if case in ('selected', 'legacy'):
    assert module_name[role] in sys.modules
    for family in owned[role]:
        assert family in attempts, (family, attempts)
else:
    assert not attempts, attempts
    assert not any(name in sys.modules for name in module_name.values())
'''


@pytest.mark.parametrize('case', ['module', 'help', 'invalid_direct', 'invalid_cli'])
def test_entrypoint_import_help_and_invalid_roles_attempt_no_engine_imports(tmp_path, case):
    """Fresh import traps reject every engine attempt before a valid role is chosen."""
    _run_isolated_probe(tmp_path, case, 'whisper')


@pytest.mark.parametrize('role', ['youtube', 'whisper', 'azure'])
def test_selected_role_loads_only_its_engine_and_runs_with_owned_runtime(tmp_path, role):
    """Each explicit role imports its own module and SDKs, then runs a bounded fake."""
    _run_isolated_probe(tmp_path, 'selected', role)


@pytest.mark.parametrize('role', ['youtube', 'whisper', 'azure'])
def test_legacy_main_class_forwarding_loads_only_requested_role(tmp_path, role):
    """Legacy entrypoint class names resolve to real classes without other engines."""
    _run_isolated_probe(tmp_path, 'legacy', role)


def _run_isolated_probe(tmp_path: Path, case: str, role: str) -> None:
    """Run an import probe with only test-owned configuration and bounded execution.

    Args:
        tmp_path: Test-owned home and configured media/model paths.
        case: Import, CLI, selected execution, or compatibility scenario.
        role: Selected or reference role for the scenario.
    """
    root = Path(testee.__file__).resolve().parents[2]
    env = {
        'HOME': str(tmp_path),
        'WHISPER_ASSETS_DIR': str(tmp_path / 'assets'),
        'WHISPER_MODELS_DIR': str(tmp_path / 'models'),
        'WHISPER_USE_CUDA': 'false',
        'REDIS_HOST': 'queue.test.invalid',
        'WORKER_ROLE': 'whisper',
        'PATH': os.defpath,
    }
    result = subprocess.run(
        [sys.executable, '-c', _ISOLATED_PROBE, case, role],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
