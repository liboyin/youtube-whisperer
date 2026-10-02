from importlib import import_module
from types import SimpleNamespace

import pytest

import youtube_whisperer.workers.__main__ as testee


def test_worker_role_values():
    """Test that the worker role enum exposes the expected CLI values."""
    assert testee.WorkerRole.values() == ('youtube', 'whisper', 'azure')


def test_worker_role_rejects_legacy_local_alias():
    """Test that the worker role enum no longer accepts the legacy `local` alias."""
    with pytest.raises(ValueError, match="'local' is not a valid WorkerRole"):
        testee.WorkerRole('local')


def test_resolve_worker_slot_prefers_explicit_slot(mocker):
    """Test that an explicit slot bypasses settings and hostname lookup."""
    mock_settings = mocker.patch.object(testee, 'Settings')
    mock_hostname = mocker.patch.object(testee.socket, 'gethostname')

    assert testee.resolve_worker_slot('explicit-slot', 'whisper') == 'explicit-slot'
    mock_settings.assert_not_called()
    mock_hostname.assert_not_called()


def test_resolve_worker_slot_falls_back_to_slot_id(mocker):
    """Test that the configured slot ID is combined with the role name."""
    mocker.patch.object(testee, 'Settings', return_value=SimpleNamespace(worker_slot_id='7'))
    mock_hostname = mocker.patch.object(testee.socket, 'gethostname')

    assert testee.resolve_worker_slot(None, 'whisper') == 'whisper-7'
    mock_hostname.assert_not_called()


def test_resolve_worker_slot_falls_back_to_socket_hostname(mocker):
    """Test that slot resolution falls back to `socket.gethostname()`."""
    mocker.patch.object(testee, 'Settings', return_value=SimpleNamespace(worker_slot_id=None))
    mocker.patch.object(testee.socket, 'gethostname', return_value='host-slot')
    assert testee.resolve_worker_slot(None, 'whisper') == 'host-slot'


@pytest.mark.parametrize('explicit, configured, expected', [
    ('override', 'configured', 'override'),
    ('', 'configured', 'azure-configured'),
    (None, '', 'azure-'),
    (None, None, 'owned-host'),
])
def test_resolve_worker_slot_preserves_snapshot_precedence_and_empty_values(mocker, explicit, configured, expected):
    """Supplied settings preserve explicit-slot, empty-id and hostname behavior."""
    settings = testee.Settings(worker_slot_id=configured)
    mocker.patch.object(testee, 'Settings', side_effect=AssertionError('ambient settings'))
    mocker.patch.object(testee.socket, 'gethostname', return_value='owned-host')
    assert testee.resolve_worker_slot(explicit, 'azure', settings=settings) == expected


@pytest.mark.parametrize('role, module_name, class_name', [
    (testee.WorkerRole.YOUTUBE, 'youtube_whisperer.workers.youtube_worker', 'YouTubeWorker'),
    (testee.WorkerRole.WHISPER, 'youtube_whisperer.workers.whisper_worker', 'WhisperWorker'),
    (testee.WorkerRole.AZURE, 'youtube_whisperer.workers.azure_worker', 'AzureWorker'),
])
def test_load_worker_class_maps_each_valid_role_to_its_concrete_class(role, module_name, class_name):
    """Every valid role resolves to the matching concrete worker class."""
    expected_class = getattr(import_module(module_name), class_name)

    assert testee._load_worker_class(role) is expected_class


def test_load_worker_class_rejects_unmapped_role():
    """The private loader rejects values outside its explicit role mapping."""
    with pytest.raises(ValueError, match='^Unsupported worker role: remote$'):
        testee._load_worker_class('remote')


def test_legacy_forwarding_rejects_unknown_class_name():
    """Unknown compatibility names retain ordinary module attribute errors."""
    with pytest.raises(AttributeError, match="has no attribute 'RemoteWorker'"):
        testee.__getattr__('RemoteWorker')


@pytest.mark.parametrize('poll', [0, -1])
def test_process_queue_rejects_invalid_poll_before_resource_creation(mocker, poll):
    """Python dispatch rejects invalid polling before runtime or worker construction."""
    runtime = mocker.patch.object(testee, 'Runtime')
    loader = mocker.patch.object(testee, '_load_worker_class')
    with pytest.raises(ValueError, match='poll_interval_seconds'):
        testee.process_queue(poll_interval_seconds=poll)
    runtime.assert_not_called()
    loader.assert_not_called()


def test_process_queue_routes_youtube_work(mocker):
    """Test that the queue entry point dispatches YouTube work to the YouTube processor."""
    mock_slot = mocker.patch.object(testee, 'resolve_worker_slot', return_value='youtube-0')
    mock_worker = mocker.Mock()
    loader = mocker.patch.object(testee, '_load_worker_class', return_value=mock_worker)
    runtime = mocker.patch.object(testee, 'Runtime').return_value.__enter__.return_value

    testee.process_queue(role=testee.WorkerRole.YOUTUBE, poll_interval_seconds=7)

    mock_slot.assert_called_once_with(None, testee.WorkerRole.YOUTUBE.value, settings=runtime.settings)
    loader.assert_called_once_with(testee.WorkerRole.YOUTUBE)
    mock_worker.assert_called_once_with('youtube-0', runtime=runtime)
    mock_worker.return_value.process_queue.assert_called_once_with(poll_interval_seconds=7)


def test_process_queue_routes_whisper_work(mocker):
    """Test that the queue entry point dispatches Whisper work with a resolved slot."""
    mock_slot = mocker.patch.object(testee, 'resolve_worker_slot', return_value='gpu-0')
    mock_worker = mocker.Mock()
    loader = mocker.patch.object(testee, '_load_worker_class', return_value=mock_worker)
    runtime = mocker.patch.object(testee, 'Runtime').return_value.__enter__.return_value

    testee.process_queue(role=testee.WorkerRole.WHISPER, poll_interval_seconds=7)

    mock_slot.assert_called_once_with(None, testee.WorkerRole.WHISPER.value, settings=runtime.settings)
    loader.assert_called_once_with(testee.WorkerRole.WHISPER)
    mock_worker.assert_called_once_with('gpu-0', runtime=runtime)
    mock_worker.return_value.process_queue.assert_called_once_with(poll_interval_seconds=7)


def test_process_queue_defaults_to_whisper(mocker):
    """Direct queue execution selects Whisper when no role is provided."""
    worker = mocker.Mock()
    loader = mocker.patch.object(testee, '_load_worker_class', return_value=worker)
    mocker.patch.object(testee, 'Runtime')

    testee.process_queue()

    loader.assert_called_once_with(testee.WorkerRole.WHISPER)
    worker.return_value.process_queue.assert_called_once_with(poll_interval_seconds=5)


def test_process_queue_routes_azure_work(mocker):
    """Test that the queue entry point dispatches Azure work with a resolved slot."""
    mock_slot = mocker.patch.object(testee, 'resolve_worker_slot', return_value='azure-0')
    mock_worker = mocker.Mock()
    loader = mocker.patch.object(testee, '_load_worker_class', return_value=mock_worker)
    runtime = mocker.patch.object(testee, 'Runtime').return_value.__enter__.return_value

    testee.process_queue(role=testee.WorkerRole.AZURE, poll_interval_seconds=7)

    mock_slot.assert_called_once_with(None, testee.WorkerRole.AZURE.value, settings=runtime.settings)
    loader.assert_called_once_with(testee.WorkerRole.AZURE)
    mock_worker.assert_called_once_with('azure-0', runtime=runtime)
    mock_worker.return_value.process_queue.assert_called_once_with(poll_interval_seconds=7)


def test_process_queue_rejects_unknown_worker_role():
    """Test that unsupported worker roles raise a clear error."""
    with pytest.raises(ValueError, match='^Unsupported worker role: remote$'):
        testee.process_queue(role='remote')


@pytest.mark.parametrize('phase', ['loader', 'constructor', 'execution'])
@pytest.mark.parametrize('failure', [RuntimeError('worker'), KeyboardInterrupt('worker')])
def test_worker_entrypoint_closes_runtime_on_constructor_and_execution_failure(mocker, phase, failure):
    """Entrypoint ownership covers worker construction and execution BaseException."""
    settings = testee.Settings(worker_slot_id='owned')
    import youtube_whisperer.runtime as runtime_testee

    pool, client = mocker.Mock(), mocker.Mock()
    mocker.patch.object(runtime_testee, 'create_redis_pool', return_value=pool)
    mocker.patch.object(runtime_testee.redis, 'StrictRedis', return_value=client)
    worker = mocker.Mock()
    loader = mocker.patch.object(testee, '_load_worker_class', return_value=worker)
    if phase == 'loader':
        loader.side_effect = failure
    elif phase == 'constructor':
        worker.side_effect = failure
    else:
        worker.return_value.process_queue.side_effect = failure
    with pytest.raises(type(failure), match='worker'):
        testee.process_queue('whisper', settings=settings)
    client.close.assert_called_once_with()
    pool.disconnect.assert_called_once_with()
    loader.assert_called_once_with(testee.WorkerRole.WHISPER)
    if phase != 'loader':
        assert worker.call_args.args == ('whisper-owned',)
        runtime = worker.call_args.kwargs['runtime']
        assert runtime.settings is settings
        assert runtime.client is client


@pytest.mark.parametrize('value', ['0', '-1', 'text', '1.5'])
def test_main_real_argparse_rejects_invalid_polling(mocker, monkeypatch, capsys, value):
    """Real argparse rejects invalid integer polling before queue dispatch."""
    import sys

    monkeypatch.setattr(sys, 'argv', ['worker', '--poll-interval-seconds', value])
    process = mocker.patch.object(testee, 'process_queue')
    with pytest.raises(SystemExit) as error:
        testee.main()
    assert error.value.code == 2
    assert 'poll interval must be a positive integer' in capsys.readouterr().err
    process.assert_not_called()


def test_main_real_argparse_forwards_positive_polling(mocker, monkeypatch):
    """Real argparse forwards positive integer seconds without changing their value."""
    import sys

    monkeypatch.setattr(sys, 'argv', ['worker', '--poll-interval-seconds', '3'])
    process = mocker.patch.object(testee, 'process_queue')
    testee.main()
    assert process.call_args.kwargs['poll_interval_seconds'] == 3


def test_main_parses_arguments_and_dispatches(mocker):
    """Test that the worker CLI parses arguments and dispatches to `process_queue`."""
    mock_process = mocker.patch.object(testee, 'process_queue')
    settings = SimpleNamespace(worker_role='whisper')
    mocker.patch.object(testee, 'Settings', return_value=settings)
    mocker.patch(
        'argparse.ArgumentParser.parse_args',
        return_value=SimpleNamespace(role='youtube', slot='yt-0', poll_interval_seconds=9),
    )

    testee.main()

    mock_process.assert_called_once_with(role='youtube', slot='yt-0', poll_interval_seconds=9, settings=settings)


def test_main_resolves_one_snapshot_for_default_role_and_execution(mocker, monkeypatch):
    """Real argparse defaults and queue dispatch use the exact CLI snapshot."""
    monkeypatch.setenv('WORKER_ROLE', 'azure')
    monkeypatch.setenv('WORKER_SLOT_ID', 'owned')
    settings = testee.Settings()
    factory = mocker.patch.object(testee, 'Settings', return_value=settings)
    process = mocker.patch.object(testee, 'process_queue')
    import sys

    mocker.patch.object(sys, 'argv', ['worker'])
    testee.main()
    factory.assert_called_once_with()
    process.assert_called_once_with(role='azure', slot=None, poll_interval_seconds=5, settings=settings)


def test_main_defaults_to_whisper_without_worker_role(mocker, monkeypatch):
    """The CLI defaults to Whisper when WORKER_ROLE is absent."""
    monkeypatch.delenv('WORKER_ROLE')
    settings = testee.Settings()
    mocker.patch.object(testee, 'Settings', return_value=settings)
    process = mocker.patch.object(testee, 'process_queue')
    import sys

    mocker.patch.object(sys, 'argv', ['worker'])
    testee.main()
    process.assert_called_once_with(role='whisper', slot=None, poll_interval_seconds=5, settings=settings)
