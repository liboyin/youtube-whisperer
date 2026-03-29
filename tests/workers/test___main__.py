import os

import youtube_whisperer.workers.__main__ as testee


def test_resolve_worker_slot_prefers_explicit_slot(mocker):
    """Test that an explicit slot overrides environment-derived slot names."""
    mocker.patch.dict(os.environ, {'WORKER_SLOT_ID': '0'})
    mocker.patch('socket.gethostname', return_value='host-slot')

    assert testee.resolve_worker_slot('explicit-slot', 'whisper') == 'explicit-slot'


def test_resolve_worker_slot_falls_back_to_slot_id(mocker):
    """Test that the worker slot uses `WORKER_SLOT_ID` combined with the role name."""
    mocker.patch.dict(os.environ, {'WORKER_SLOT_ID': '7'})
    mocker.patch('socket.gethostname', return_value='host-slot')

    assert testee.resolve_worker_slot(None, 'whisper') == 'whisper-7'


def test_resolve_worker_slot_falls_back_to_socket_hostname(mocker):
    """Test that slot resolution falls back to `socket.gethostname()`."""
    mocker.patch.dict(os.environ, {}, clear=True)
    mocker.patch('socket.gethostname', return_value='host-slot')
    assert testee.resolve_worker_slot(None, 'whisper') == 'host-slot'
