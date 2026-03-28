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


def test_process_queue_routes_youtube_work(mocker):
    """Test that the queue entry point dispatches YouTube work to the YouTube processor."""
    mock_worker = mocker.patch.object(testee, 'YouTubeWorker')

    testee.process_queue(role=testee.WorkerRole.YOUTUBE, poll_interval_seconds=7)

    mock_worker.assert_called_once_with()
    mock_worker.return_value.process_queue.assert_called_once_with(poll_interval_seconds=7)


def test_process_queue_routes_whisper_work(mocker):
    """Test that the queue entry point dispatches Whisper work with a resolved slot."""
    mock_slot = mocker.patch.object(testee, 'resolve_worker_slot', return_value='gpu-0')
    mock_worker = mocker.patch.object(testee, 'WhisperWorker')

    testee.process_queue(role=testee.WorkerRole.WHISPER, poll_interval_seconds=7)

    mock_slot.assert_called_once_with(None, testee.WorkerRole.WHISPER.value)
    mock_worker.assert_called_once_with('gpu-0')
    mock_worker.return_value.process_queue.assert_called_once_with(poll_interval_seconds=7)


def test_process_queue_routes_azure_work(mocker):
    """Test that the queue entry point dispatches Azure work with a resolved slot."""
    mock_slot = mocker.patch.object(testee, 'resolve_worker_slot', return_value='azure-0')
    mock_worker = mocker.patch.object(testee, 'AzureWorker')

    testee.process_queue(role=testee.WorkerRole.AZURE, poll_interval_seconds=7)

    mock_slot.assert_called_once_with(None, testee.WorkerRole.AZURE.value)
    mock_worker.assert_called_once_with('azure-0')
    mock_worker.return_value.process_queue.assert_called_once_with(poll_interval_seconds=7)


def test_process_queue_rejects_unknown_worker_role():
    """Test that unsupported worker roles raise a clear error."""
    with pytest.raises(ValueError, match='Unsupported worker role'):
        testee.process_queue(role='remote')


def test_main_parses_arguments_and_dispatches(mocker):
    """Test that the worker CLI parses arguments and dispatches to `process_queue`."""
    mock_process = mocker.patch.object(testee, 'process_queue')
    mocker.patch(
        'argparse.ArgumentParser.parse_args',
        return_value=SimpleNamespace(role='youtube', slot='yt-0', poll_interval_seconds=9),
    )

    testee.main()

    mock_process.assert_called_once_with(role='youtube', slot='yt-0', poll_interval_seconds=9)
