import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import ANY, MagicMock

import pytest
from fastapi.testclient import TestClient
from redis import StrictRedis

import youtube_whisperer.api.app as testee
import youtube_whisperer.workers.common as worker_testee
from youtube_whisperer.models import DeadLetter, Task, TaskQueues


@pytest.fixture
def mock_redis_client():
    mock_client = MagicMock(spec=StrictRedis)
    mock_client.lrange.return_value = []
    mock_client.rpush.return_value = 1
    mock_client.delete.return_value = 1
    return mock_client


@pytest.fixture
def mock_assets_dir(tmp_path):
    return tmp_path


@pytest.fixture(autouse=True)
def override_dependencies(mock_redis_client, mock_assets_dir, monkeypatch):
    """Bind API dependencies and direct dependency calls to test-owned resources."""
    monkeypatch.setattr(testee.app.state, 'runtime', SimpleNamespace(client=mock_redis_client, assets_dir=mock_assets_dir), raising=False)
    monkeypatch.setattr(testee.app, 'dependency_overrides', {
        testee.get_redis_client: lambda: mock_redis_client,
        testee.get_assets_dir: lambda: mock_assets_dir,
    })


@pytest.fixture
def client():
    return TestClient(testee.app)


def test_get_assets_dir_returns_configured_directory(mock_assets_dir):
    """Test that the assets dependency returns the configured assets directory."""
    assert testee.get_assets_dir() == mock_assets_dir


def test_get_redis_client_yields_configured_client(mock_redis_client):
    """Test that the Redis dependency yields the configured Redis client."""
    assert next(testee.get_redis_client()) is mock_redis_client


def test_standalone_api_dependencies_resolve_invocation_resources(mocker, monkeypatch, tmp_path):
    """Direct dependency access without lifespan owns and closes its temporary client."""
    # The module's autouse fixture supplies a runtime for older endpoint tests.
    monkeypatch.delattr(testee.app.state, 'runtime')
    monkeypatch.setenv('WHISPER_ASSETS_DIR', str(tmp_path))
    assert testee.get_assets_dir() == tmp_path
    runtime = mocker.patch.object(testee, 'Runtime').return_value.__enter__.return_value
    dependency = testee.get_redis_client()
    assert next(dependency) is runtime.client
    dependency.close()
    testee.Runtime.return_value.__exit__.assert_called_once()


def test_get_tasks_returns_queue_snapshot(client, mocker):
    """Test that the tasks endpoint returns the grouped queue snapshot."""
    queue_snapshot = TaskQueues(youtube=[], whisper_pending=[], whisper_active=[], azure_pending=[], azure_active=[])
    mock_list = mocker.patch.object(testee, 'list_task_queues', return_value=queue_snapshot)

    response = client.get("/tasks")

    assert response.status_code == 200
    assert response.json() == queue_snapshot.model_dump(mode='json')
    mock_list.assert_called_once()


def test_get_tasks_propagates_queue_lookup_failure(mocker):
    """Test that queue lookup failures propagate so the global handler can convert them to 500."""
    redis_client = mocker.MagicMock()
    mocker.patch.object(testee, 'list_task_queues', side_effect=RuntimeError("redis down"))

    with pytest.raises(RuntimeError, match="redis down"):
        asyncio.run(testee.get_tasks(redis_client=redis_client))


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


def test_model_copy_preserves_non_source_fields():
    """Test that copying a task with a new source preserves its other fields."""
    pattern = Task(source='https://example.com/playlist', language='zh-cn', transcriber='azure')

    result = pattern.model_copy(update={'source': 'https://example.com/video1'})

    assert result.source == 'https://example.com/video1'
    assert result.language == pattern.language
    assert result.transcriber == pattern.transcriber


@pytest.mark.parametrize('transcriber', ['whisper', 'azure', 'none'])
@pytest.mark.parametrize('mode', ['transcribe', 'translate', 'unknown', None, 0, [], {}])
def test_add_tasks_rejects_removed_mode_without_enqueueing(client, mocker, transcriber, mode):
    """Test that every supplied operation field produces 422 before either queue submission."""
    youtube_enqueue = mocker.patch.object(testee, 'queue_youtube_task')
    transcription_enqueue = mocker.patch.object(testee, 'queue_transcription_tasks')

    response = client.post('/tasks', json=[{
        'source': 'https://example.com/video', 'transcriber': transcriber, 'mode': mode,
    }])

    assert response.status_code == 422
    assert 'mode is no longer supported' in response.json()['detail'][0]['msg']
    youtube_enqueue.assert_not_called()
    transcription_enqueue.assert_not_called()


@pytest.mark.parametrize('language', ['en->en', 'zh->en', 'en-us->zh-cn', 'en -> zh'])
def test_add_tasks_rejects_arrow_languages_without_enqueueing(client, mocker, language):
    """Test that HTTP translation-language forms are rejected before queue submission."""
    youtube_enqueue = mocker.patch.object(testee, 'queue_youtube_task')
    transcription_enqueue = mocker.patch.object(testee, 'queue_transcription_tasks')

    response = client.post('/tasks', json=[{'source': 'https://example.com/video', 'language': language}])

    assert response.status_code == 422
    youtube_enqueue.assert_not_called()
    transcription_enqueue.assert_not_called()


@pytest.mark.parametrize('language', [123, 1.5, None, [], ['en'], {}, {'source': 'en'}, True])
def test_add_tasks_rejects_non_string_languages_without_enqueueing(mocker, language):
    """Test that malformed language JSON types produce 422 rather than 500, before queue submission."""
    youtube_enqueue = mocker.patch.object(testee, 'queue_youtube_task')
    transcription_enqueue = mocker.patch.object(testee, 'queue_transcription_tasks')
    swallowing_client = TestClient(testee.app, raise_server_exceptions=False)

    response = swallowing_client.post('/tasks', json=[{'source': 'https://example.com/video', 'language': language}])

    assert response.status_code == 422
    assert [item['loc'][-1] for item in response.json()['detail']] == ['language']
    assert 'Unexpected language' in response.json()['detail'][0]['msg']
    youtube_enqueue.assert_not_called()
    transcription_enqueue.assert_not_called()


def test_openapi_documents_source_language_without_mode_or_targets(client):
    """Test that the HTTP task schema cannot advertise the removed operation or arrow examples."""
    schemas = client.get('/openapi.json').json()['components']['schemas']
    task_schemas = [schema for name, schema in schemas.items() if name in {'Task', 'Task-Input', 'Task-Output'}]
    assert task_schemas
    for schema in task_schemas:
        assert set(schema['properties']) == {'source', 'transcriber', 'language'}
        assert schema['properties']['language']['examples'] == ['en', 'en-us']


def test_add_tasks_routes_youtube_and_whisper_work(client, mocker):
    """Test that the add-tasks endpoint splits YouTube and filesystem work correctly."""
    url_task = Task(source='https://example.com/video', language='en')
    resolved_whisper_task = Task(source='/tmp/audio.wav', language='en')
    mocker.patch.object(testee, 'is_url', side_effect=lambda source: source.startswith('http'))
    mock_resolve_filesystem = mocker.patch.object(testee, 'resolve_filesystem_tasks', return_value=[resolved_whisper_task])
    mock_queue_youtube_task = mocker.patch.object(testee, 'queue_youtube_task')
    mock_queue_transcription_tasks = mocker.patch.object(testee, 'queue_transcription_tasks')

    response = client.post(
        "/tasks",
        json=[
            url_task.model_dump(mode='json'),
            Task(source='/tmp/*.wav', language='en').model_dump(mode='json'),
        ],
    )

    assert response.status_code == 201
    assert response.json() == {
        'successful': [url_task.model_dump(mode='json'), resolved_whisper_task.model_dump(mode='json')],
        'failed': [],
    }
    mock_resolve_filesystem.assert_called_once()
    mock_queue_youtube_task.assert_called_once_with(ANY, url_task)
    mock_queue_transcription_tasks.assert_called_once_with(ANY, [resolved_whisper_task])


def test_add_tasks_rejects_filesystem_source_with_none_transcriber(client, mocker):
    """Test that a filesystem source with the `none` transcriber is failed without resolving globs or queueing."""
    none_task = Task(source='/tmp/audio.wav', language='en', transcriber='none')
    mocker.patch.object(testee, 'is_url', return_value=False)
    mock_resolve_filesystem = mocker.patch.object(testee, 'resolve_filesystem_tasks')
    mock_queue_youtube_task = mocker.patch.object(testee, 'queue_youtube_task')
    mock_queue_transcription_tasks = mocker.patch.object(testee, 'queue_transcription_tasks')

    response = client.post("/tasks", json=[none_task.model_dump(mode='json')])

    assert response.status_code == 201
    assert response.json() == {'successful': [], 'failed': [none_task.model_dump(mode='json')]}
    mock_resolve_filesystem.assert_not_called()  # not actionable: never resolved
    mock_queue_youtube_task.assert_not_called()
    mock_queue_transcription_tasks.assert_not_called()


@pytest.mark.parametrize('matches_directory', [True, False])
def test_add_tasks_failed_resolution(client, mocker, tmp_path, owned_path_probes, matches_directory):
    """Directory-only and unmatched filesystem submissions fail without queueing."""
    if matches_directory:
        (tmp_path / 'directory.wav').mkdir()
    task = Task(source=str(tmp_path / '*'), language='en')
    mock_queue_youtube_task = mocker.patch.object(testee, 'queue_youtube_task')
    mock_queue_transcription_tasks = mocker.patch.object(testee, 'queue_transcription_tasks')

    with owned_path_probes():
        response = client.post('/tasks', json=[task.model_dump(mode='json')])

    assert response.status_code == 201
    assert response.json() == {'successful': [], 'failed': [task.model_dump(mode='json')]}
    mock_queue_youtube_task.assert_not_called()
    mock_queue_transcription_tasks.assert_not_called()


def test_add_tasks_mixed_matches_queue_only_files(client, mocker, tmp_path, owned_path_probes):
    """Mixed filesystem submissions report and enqueue only files with request metadata intact."""
    file = tmp_path / 'notes.custom'
    file.touch()
    (tmp_path / 'directory.wav').mkdir()
    pattern = Task(source=str(tmp_path / '*'), language='zh-cn', transcriber='azure')
    resolved = pattern.model_copy(update={'source': str(file)})
    youtube_enqueue = mocker.patch.object(testee, 'queue_youtube_task')
    transcription_enqueue = mocker.patch.object(testee, 'queue_transcription_tasks')

    with owned_path_probes():
        response = client.post('/tasks', json=[pattern.model_dump(mode='json')])

    assert response.status_code == 201
    assert response.json() == {'successful': [resolved.model_dump(mode='json')], 'failed': []}
    youtube_enqueue.assert_not_called()
    transcription_enqueue.assert_called_once_with(ANY, [resolved])


def test_add_tasks_binds_worker_to_api_file_across_working_directories(client, mock_redis_client, tmp_path, monkeypatch):
    """Actual queued payload dispatch reads the API file despite a same-named worker-directory decoy."""
    api_dir = tmp_path / 'api'
    worker_dir = tmp_path / 'worker'
    api_dir.mkdir()
    worker_dir.mkdir()
    filename = 'audio with spaces.custom'
    media = api_dir / filename
    media.write_text('intended API contents')
    (worker_dir / filename).write_text('wrong worker contents')
    monkeypatch.chdir(api_dir)

    response = client.post('/tasks', json=[{'source': f'  {filename}  ', 'language': 'zh-cn', 'transcriber': 'azure'}])

    expected = Task(source=str(media), language='zh-cn', transcriber='azure')
    assert response.status_code == 201
    assert response.json() == {'successful': [expected.model_dump(mode='json')], 'failed': []}
    queued = mock_redis_client.pipeline.return_value.xadd.call_args_list
    assert len(queued) == 1
    stream, fields = queued[0].args
    assert stream == 'stream:azure'
    task = Task.model_validate_json(fields['payload'])
    assert task == expected
    observed = []

    class ReadingWorker(worker_testee.TranscriptionWorker):
        """Read owned media contents through the common worker dispatch contract."""

        def dispatch_task(self, task: Task, source: Path) -> None:
            """Capture the dispatched task, path, and actual file contents."""
            observed.append((task, source, source.read_text()))

    worker = ReadingWorker(expected.transcriber, 'owned-reader', client=mock_redis_client)
    try:
        monkeypatch.chdir(worker_dir)
        worker.process_task(task)
    finally:
        worker.runtime.close()
    assert observed == [(expected, media, 'intended API contents')]
    mock_redis_client.close.assert_not_called()


def test_add_tasks_propagates_queueing_failure(mocker):
    """Test that queueing failures in add_tasks propagate so the global handler can convert them to 500."""
    redis_client = mocker.MagicMock()
    task = Task(source="/tmp/audio.wav", language="en")
    mocker.patch.object(testee, 'is_url', return_value=False)
    mocker.patch.object(testee, 'resolve_filesystem_tasks', return_value=[task])
    mocker.patch.object(testee, 'queue_transcription_tasks', side_effect=RuntimeError("redis down"))

    with pytest.raises(RuntimeError, match="redis down"):
        asyncio.run(testee.add_tasks([task], redis_client=redis_client))


def test_clear_tasks_returns_deleted_queue_snapshot(client, mocker):
    """Test that deleting tasks returns the snapshot of removed queue contents."""
    queue_snapshot = TaskQueues(youtube=[], whisper_pending=[], whisper_active=[], azure_pending=[], azure_active=[])
    mock_clear = mocker.patch.object(testee, 'clear_task_queues', return_value=queue_snapshot)

    response = client.delete("/tasks")

    assert response.status_code == 200
    assert response.json() == queue_snapshot.model_dump(mode='json')
    mock_clear.assert_called_once()


def test_clear_tasks_propagates_queue_clearing_failure(mocker):
    """Test that task-clearing failures propagate so the global handler can convert them to 500."""
    redis_client = mocker.MagicMock()
    mocker.patch.object(testee, 'clear_task_queues', side_effect=RuntimeError("redis down"))

    with pytest.raises(RuntimeError, match="redis down"):
        asyncio.run(testee.clear_tasks(redis_client=redis_client))


def test_get_dead_letters_returns_queue_contents(client, mocker):
    """Test that the dead-letter endpoint returns the queued dead-letter entries."""
    dead_letter = DeadLetter(task=Task(source='/tmp/audio.wav', language='en'), queue='stream:whisper', error='boom')
    mock_list = mocker.patch.object(testee, 'list_dead_letters', return_value=[dead_letter])

    response = client.get("/dead-letters")

    assert response.status_code == 200
    assert response.json() == [dead_letter.model_dump(mode='json')]
    mock_list.assert_called_once()


def test_get_dead_letters_propagates_lookup_failure(mocker):
    """Test that dead-letter lookup failures propagate so the global handler can convert them to 500."""
    redis_client = mocker.MagicMock()
    mocker.patch.object(testee, 'list_dead_letters', side_effect=RuntimeError("redis down"))

    with pytest.raises(RuntimeError, match="redis down"):
        asyncio.run(testee.get_dead_letters(redis_client=redis_client))


def test_clear_dead_letters_returns_deleted_items(client, mocker, mock_redis_client):
    """Test that clearing dead letters returns the deleted entries and removes the queue key."""
    dead_letter = DeadLetter(task=Task(source='/tmp/audio.wav', language='en'), queue='stream:whisper', error='boom')
    mock_list = mocker.patch.object(testee, 'list_dead_letters', return_value=[dead_letter])

    response = client.delete("/dead-letters")

    assert response.status_code == 200
    assert response.json() == [dead_letter.model_dump(mode='json')]
    mock_list.assert_called_once()
    mock_redis_client.delete.assert_called_once_with(testee.DEAD_LETTER_QUEUE)


def test_clear_dead_letters_propagates_delete_failure(mocker):
    """Test that dead-letter clearing failures propagate so the global handler can convert them to 500."""
    redis_client = mocker.MagicMock()
    mocker.patch.object(testee, 'list_dead_letters', side_effect=RuntimeError("redis down"))

    with pytest.raises(RuntimeError, match="redis down"):
        asyncio.run(testee.clear_dead_letters(redis_client=redis_client))


def test_list_assets_empty(client):
    """Test that the assets endpoint returns an empty list when no files exist."""
    response = client.get("/assets")

    assert response.status_code == 200
    assert response.json() == []


def test_list_assets_with_files(client, mock_assets_dir):
    """Test that the assets endpoint lists files present in the assets directory."""
    (mock_assets_dir / "file1.txt").touch()
    (mock_assets_dir / "file2.txt").touch()

    response = client.get("/assets")

    assert response.status_code == 200
    assert sorted(response.json()) == [str(mock_assets_dir / "file1.txt"), str(mock_assets_dir / "file2.txt")]


def test_list_assets_with_subdirectories(client, mock_assets_dir):
    """Test that the assets endpoint lists files in subdirectories recursively."""
    subdir = mock_assets_dir / "subdir"
    subdir.mkdir()
    (mock_assets_dir / "file1.txt").touch()
    (subdir / "file2.txt").touch()

    response = client.get("/assets")

    assert response.status_code == 200
    paths = response.json()
    assert str(mock_assets_dir / "file1.txt") in paths
    assert str(subdir / "file2.txt") in paths
    assert str(subdir) in paths  # rglob("*") includes directory entries


def test_list_assets_propagates_directory_listing_failure(tmp_path, owned_path_probes):
    """Test that asset-listing failures propagate so the global handler can convert them to 500."""
    bad_dir = tmp_path / "missing"

    with owned_path_probes(), pytest.raises(FileNotFoundError, match="missing"):
        asyncio.run(testee.list_assets(dir_path=bad_dir))


def touch_distinct(directory, names):
    """Create the named files and assert the filesystem kept every case variant distinct."""
    for name in names:
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    actual = {str(path.relative_to(directory)) for path in directory.rglob('*') if path.is_file()}
    assert actual == set(names), 'test requires a case-sensitive filesystem'


def test_group_files_by_stem_keeps_actual_case_variants(tmp_path):
    """Files group by exact path without suffix, keeping each on-disk suffix spelling."""
    touch_distinct(tmp_path, ['video.MP4', 'video.Srt', 'video.wav', 'video.WAV', 'Video.mp4'])

    result = testee.group_files_by_stem(tmp_path)

    assert {stem: sorted(files) for stem, files in result.items()} == {
        tmp_path / 'video': sorted(tmp_path / name for name in ('video.MP4', 'video.Srt', 'video.wav', 'video.WAV')),
        tmp_path / 'Video': [tmp_path / 'Video.mp4'],
    }


def test_group_files_by_stem_recurses_into_subdirectories(tmp_path):
    """Test that group_files_by_stem descends into subdirectories, keying by full path."""
    subdir = tmp_path / "sub"
    subdir.mkdir()
    (tmp_path / "video.mp4").touch()
    (subdir / "video.srt").touch()

    result = testee.group_files_by_stem(tmp_path)

    assert result == {tmp_path / "video": [tmp_path / "video.mp4"], subdir / "video": [subdir / "video.srt"]}


def test_group_files_by_stem_retains_file_symlinks_and_excludes_directories(tmp_path):
    """Only files and file symlinks are grouped; directories and broken symlinks are skipped."""
    (tmp_path / "video").mkdir()
    (tmp_path / "audio.wav").touch()
    (tmp_path / "alias.wav").symlink_to(tmp_path / "audio.wav")
    (tmp_path / "broken.wav").symlink_to(tmp_path / "missing.wav")

    result = testee.group_files_by_stem(tmp_path)

    assert result == {tmp_path / "audio": [tmp_path / "audio.wav"], tmp_path / "alias": [tmp_path / "alias.wav"]}


def test_group_files_by_stem_raises_for_missing_directory(tmp_path, owned_path_probes):
    """Test that group_files_by_stem raises when the directory does not exist."""
    with owned_path_probes(), pytest.raises(FileNotFoundError, match="missing"):
        testee.group_files_by_stem(tmp_path / "missing")


def test_redundant_media_paths_selects_actual_transient_paths_of_mixed_case_pairs():
    """A mixed-case MP4 + SRT pair selects every transient case variant by its supplied path."""
    stem = Path('/assets/video')
    files = [stem.with_suffix(suffix) for suffix in ('.MP4', '.Srt', '.Mkv', '.wav', '.WAV', '.MP3', '.txt', '.m4a')]

    result = testee.redundant_media_paths({stem: files})

    assert sorted(result) == sorted(stem.with_suffix(suffix) for suffix in ('.Mkv', '.wav', '.WAV', '.MP3'))


def test_redundant_media_paths_ignores_incomplete_stems():
    """Test that a stem missing either the mp4 or the srt keeps its transient files."""
    result = testee.redundant_media_paths({
        Path('/assets/no_srt'): [Path('/assets/no_srt.MP4'), Path('/assets/no_srt.mkv')],
        Path('/assets/no_mp4'): [Path('/assets/no_mp4.SRT'), Path('/assets/no_mp4.wav')],
    })

    assert result == []


def test_redundant_media_paths_never_selects_mp4_or_srt():
    """Test that the mp4 and srt of a completed stem are never marked redundant, in any case."""
    stem = Path('/assets/video')

    result = testee.redundant_media_paths({stem: [stem.with_suffix(suffix) for suffix in ('.mp4', '.MP4', '.srt', '.SRT')]})

    assert result == []


def test_clean_assets_removes_actual_transient_files(client, mock_assets_dir):
    """Cleaning removes every actual transient case variant of complete stems and nothing else."""
    removed = ['video.mkv', 'video.wav', 'video.WAV', 'video.Mp3', 'sub/clip.Wav']
    retained = [
        'video.MP4', 'video.Srt', 'video.txt', 'sub/clip.mp4', 'sub/clip.SRT',
        'Other.mp4', 'other.srt', 'other.wav', 'Other.wav', 'draft.mp4', 'draft.MKV', 'another.mp4',
    ]
    touch_distinct(mock_assets_dir, removed + retained)

    response = client.delete("/assets")

    assert response.status_code == 200
    assert response.json() == sorted(str(mock_assets_dir / name) for name in removed)
    remaining = {str(path.relative_to(mock_assets_dir)) for path in mock_assets_dir.rglob('*') if path.is_file()}
    assert remaining == set(retained)


def test_clean_assets_skips_selected_file_that_vanished_before_deletion(client, mock_assets_dir, mocker):
    """A selected file already removed before deletion is skipped without failing or being reported."""
    vanished = mock_assets_dir / 'vanished.wav'
    present = mock_assets_dir / 'present.wav'
    present.touch()
    assert not vanished.exists()
    mocker.patch.object(testee, 'redundant_media_paths', return_value=[vanished, present])

    response = client.delete("/assets")

    assert response.status_code == 200
    assert response.json() == [str(present)]
    assert not present.exists()


def test_clean_assets_propagates_other_deletion_failures(mock_assets_dir, mocker):
    """Deletion failures other than an already-missing file propagate for the global 500 handler."""
    blocked = mock_assets_dir / 'blocked.wav'
    blocked.mkdir()  # unlink() of a directory raises IsADirectoryError, an OSError.
    mocker.patch.object(testee, 'redundant_media_paths', return_value=[blocked])

    with pytest.raises(IsADirectoryError):
        asyncio.run(testee.clean_assets(dir_path=mock_assets_dir))
    assert blocked.is_dir()


def test_clean_assets_propagates_directory_listing_failure(tmp_path, owned_path_probes):
    """Test that asset-cleaning listing failures propagate so the global handler can convert them to 500."""
    missing_dir = tmp_path / "missing"

    with owned_path_probes(), pytest.raises(FileNotFoundError, match="missing"):
        asyncio.run(testee.clean_assets(dir_path=missing_dir))


def test_unhandled_exception_returns_sanitized_500(mocker):
    """The global exception handler must return 500 with a generic detail and not leak the original message."""
    mocker.patch.object(testee, 'list_task_queues', side_effect=RuntimeError("internal connection string secret=hunter2"))
    swallowing_client = TestClient(testee.app, raise_server_exceptions=False)

    response = swallowing_client.get("/tasks")

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert "hunter2" not in response.text


def test_create_app_isolates_lifespan_snapshots_clients_and_asset_paths(tmp_path, monkeypatch, mocker):
    """Simultaneous API lifespans retain separate settings and borrowed resources."""
    roots = [tmp_path / 'first', tmp_path / 'second']
    clients = [mocker.MagicMock(spec=StrictRedis), mocker.MagicMock(spec=StrictRedis)]
    settings = [testee.Settings(whisper_assets_dir=root, whisper_models_dir=root / 'models') for root in roots]
    for root in roots:
        root.mkdir()
        (root / 'owned.srt').write_text('complete')
    applications = [testee.create_app(snapshot, client) for snapshot, client in zip(settings, clients, strict=True)]
    lookup = mocker.patch.object(testee, 'list_task_queues', return_value=TaskQueues(youtube=[], whisper_pending=[], whisper_active=[], azure_pending=[], azure_active=[]))
    with TestClient(applications[0]) as first, TestClient(applications[1]) as second:
        monkeypatch.setenv('WHISPER_ASSETS_DIR', str(tmp_path / 'changed'))
        for api, application, root, snapshot, client in zip(
            [first, second], applications, roots, settings, clients, strict=True,
        ):
            assert api.get('/assets').json() == [str(root / 'owned.srt')]
            assert api.get('/tasks').status_code == 200
            lookup.assert_called_with(client)
            assert application.state.runtime.settings is snapshot
    for application, client in zip(applications, clients, strict=True):
        assert not hasattr(application.state, 'runtime')
        client.close.assert_not_called()


@pytest.mark.parametrize('failure', [None, RuntimeError('lifespan'), KeyboardInterrupt('lifespan')])
def test_api_lifespan_closes_owned_client_and_supplied_owned_pool(mocker, failure):
    """API lifespan cleanup disconnects owned pools even on BaseException."""
    from contextlib import nullcontext

    pool, redis_client = mocker.Mock(), mocker.Mock()
    import youtube_whisperer.runtime as runtime_testee

    mocker.patch.object(runtime_testee.redis, 'StrictRedis', return_value=redis_client)
    application = testee.create_app(pool=pool, owns_pool=True)

    async def run_lifespan():
        """Enter real application startup and inject a bounded body failure."""
        async with application.router.lifespan_context(application):
            assert application.state.runtime.client is redis_client
            if failure is not None:
                raise failure

    expected = pytest.raises(type(failure), match='lifespan') if failure is not None else nullcontext()
    with expected:
        asyncio.run(run_lifespan())
    redis_client.close.assert_called_once_with()
    pool.disconnect.assert_called_once_with()
    assert not hasattr(application.state, 'runtime')
