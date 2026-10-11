import subprocess
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path
from textwrap import dedent

import pytest

import youtube_whisperer.task_preparation as testee
from youtube_whisperer.models import Task


def test_preparation_import_loads_no_http_or_redis_layers_and_creates_no_resources(tmp_path):
    """A fresh import loads neither FastAPI, Redis nor settings, and constructs no resources."""
    script = dedent('''
        import socket
        import sys
        from unittest.mock import patch

        import pydantic_settings

        with (
            patch.object(pydantic_settings.BaseSettings, '__init__', side_effect=AssertionError('Settings construction')),
            patch.object(socket, 'socket', side_effect=AssertionError('network access')),
        ):
            import youtube_whisperer.task_preparation as testee

            loaded = sorted(name for name in sys.modules if name.split('.')[0] in {'fastapi', 'starlette', 'redis'}
                            or name in {'youtube_whisperer.config', 'youtube_whisperer.utils', 'youtube_whisperer.queueing'})
            assert loaded == [], loaded
            prepared = testee.prepare_tasks([testee.Task(source='https://example.com/video')])
            assert prepared.youtube == prepared.successful
        print('resource-free task preparation passed')
    ''')
    environment = {
        'HOME': str(tmp_path),
        'PYTHONPATH': str(Path(__file__).resolve().parents[1]),
        'PYTHONDONTWRITEBYTECODE': '1',
        'TMPDIR': str(tmp_path),
        'REDIS_HOST': 'preparation.test.invalid',
        'REDIS_PORT': '6392',
        'WHISPER_ASSETS_DIR': str(tmp_path / 'assets'),
        'WHISPER_MODELS_DIR': str(tmp_path / 'models'),
        'WHISPER_USE_CUDA': 'false',
        'WHISPER_MODEL': 'test-model',
    }
    result = subprocess.run(
        [sys.executable, '-c', script],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == 'resource-free task preparation passed'


def test_prepared_tasks_is_immutable():
    """Preparation results cannot be reassigned after construction."""
    prepared = testee.PreparedTasks(successful=(), failed=(), youtube=(), transcription=())

    with pytest.raises(FrozenInstanceError):
        prepared.successful = (Task(source='https://example.com/video'),)


def test_resolve_filesystem_tasks_expands_globs(mocker, monkeypatch, tmp_path, owned_path_probes):
    """Filesystem expansion preserves home expansion, supplied glob order, and task metadata."""
    monkeypatch.setenv('HOME', str(tmp_path))
    first = tmp_path / 'one.wav'
    second = tmp_path / 'two.wav'
    first.touch()
    second.touch()
    pattern = Task(source='~/*.wav', language='zh-cn', transcriber='azure')
    mock_glob = mocker.patch.object(testee.glob, 'glob', return_value=[str(second), str(first)])

    with owned_path_probes():
        result = testee.resolve_filesystem_tasks(pattern)

    assert result == [pattern.model_copy(update={'source': str(path)}) for path in (second, first)]
    mock_glob.assert_called_once_with(str(tmp_path / '*.wav'))


def test_resolve_filesystem_tasks_retains_files_and_file_symlinks(tmp_path, owned_path_probes):
    """Mixed glob matches retain arbitrary file extensions and file symlinks while rejecting directories."""
    regular = tmp_path / 'ordinary.wav'
    arbitrary = tmp_path / 'notes.custom'
    regular.touch()
    arbitrary.touch()
    alias = tmp_path / 'alias.custom'
    alias.symlink_to(regular)
    directory = tmp_path / 'directory.wav'
    directory.mkdir()
    directory_alias = tmp_path / 'directory-alias'
    directory_alias.symlink_to(directory, target_is_directory=True)
    broken_alias = tmp_path / 'broken-alias'
    broken_alias.symlink_to(tmp_path / 'missing')
    pattern = Task(source=str(tmp_path / '*'), language='en', transcriber='azure')

    with owned_path_probes():
        result = testee.resolve_filesystem_tasks(pattern)

    assert {task.source for task in result} == {str(regular), str(arbitrary), str(alias)}
    assert all(task.language == pattern.language and task.transcriber == pattern.transcriber for task in result)


@pytest.mark.parametrize('absolute_pattern', [False, True])
def test_resolve_filesystem_tasks_anchors_paths_preserving_aliases_and_order(tmp_path, monkeypatch, mocker, absolute_pattern):
    """Relative and absolute matches preserve spaces, symlink spelling, metadata, and glob order."""
    monkeypatch.chdir(tmp_path)
    media = tmp_path / 'original file.custom'
    media.write_text('original')
    alias = tmp_path / 'alias file.custom'
    alias.symlink_to(media)
    paths = [alias, media]
    matches = [str(path) if absolute_pattern else path.name for path in paths]
    pattern = Task(source=str(tmp_path / '*.custom') if absolute_pattern else '*.custom', language='zh-cn', transcriber='azure')
    glob = mocker.patch.object(testee.glob, 'glob', return_value=matches)

    result = testee.resolve_filesystem_tasks(pattern)

    assert result == [pattern.model_copy(update={'source': str(path)}) for path in paths]
    glob.assert_called_once_with(pattern.source)


@pytest.mark.parametrize('matches_directory', [True, False])
def test_resolve_filesystem_tasks_returns_empty_without_file_matches(tmp_path, owned_path_probes, matches_directory):
    """Directory-only and unmatched patterns produce no filesystem tasks."""
    if matches_directory:
        (tmp_path / 'directory').mkdir()
    pattern = Task(source=str(tmp_path / '*'))

    with owned_path_probes():
        assert testee.resolve_filesystem_tasks(pattern) == []


def test_prepare_tasks_routes_and_orders_mixed_submissions(mocker, tmp_path, owned_path_probes):
    """Mixed submissions keep input/expansion order, route by source and retain request metadata."""
    real_glob = testee.glob.glob
    # Reverse-sorted matches make preserved expansion order distinguishable from sorting.
    mocker.patch.object(testee.glob, 'glob', side_effect=lambda pattern: sorted(real_glob(pattern), reverse=True))
    first, second = tmp_path / 'first.wav', tmp_path / 'second.wav'
    first.touch()
    second.touch()
    (tmp_path / 'directory').mkdir()
    pattern = Task(source=str(tmp_path / '*.wav'), language='zh-cn', transcriber='azure')
    url_task = Task(source='https://example.com/video', language='en')
    download = Task(source='https://example.com/download', transcriber='none')
    unmatched = Task(source=str(tmp_path / '*.missing'))
    directory_only = Task(source=str(tmp_path / 'directory'))
    local_none = Task(source=str(first), transcriber='none')
    later = Task(source=str(second), language='en')

    with owned_path_probes():
        prepared = testee.prepare_tasks([url_task, unmatched, pattern, local_none, download, directory_only, later])

    resolved = tuple(pattern.model_copy(update={'source': str(path)}) for path in (second, first))
    assert prepared == testee.PreparedTasks(
        successful=(url_task, *resolved, download, later),
        failed=(unmatched, local_none, directory_only),
        youtube=(url_task, download),
        transcription=(*resolved, later),
    )


def test_prepare_tasks_never_resolves_filesystem_sources_with_none_transcriber(mocker):
    """A local `none` source fails without glob resolution because there is nothing to download."""
    none_task = Task(source='/never/resolved.wav', language='en', transcriber='none')
    resolve = mocker.patch.object(testee, 'resolve_filesystem_tasks')

    prepared = testee.prepare_tasks([none_task])

    assert prepared == testee.PreparedTasks(successful=(), failed=(none_task,), youtube=(), transcription=())
    resolve.assert_not_called()
