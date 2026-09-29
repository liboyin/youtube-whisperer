import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest

import youtube_whisperer.domain as testee


def test_transcriber_type_preserves_values_order_and_string_identity():
    """Test that each public engine value resolves to its canonical string enum member."""
    assert testee.TranscriberType.values() == ('whisper', 'azure', 'none')
    assert tuple(testee.TranscriberType) == (
        testee.TranscriberType.WHISPER, testee.TranscriberType.AZURE, testee.TranscriberType.NONE,
    )
    for name, value in (('WHISPER', 'whisper'), ('AZURE', 'azure'), ('NONE', 'none')):
        member = getattr(testee.TranscriberType, name)
        assert testee.TranscriberType(value) is member
        assert member == value


@pytest.mark.parametrize('value', ['local', 'remote', 'WHISPER', ''])
def test_transcriber_type_rejects_unsupported_values(value):
    """Test that relocation does not add aliases or normalize unsupported engine names."""
    with pytest.raises(ValueError, match='is not a valid TranscriberType'):
        testee.TranscriberType(value)


@pytest.mark.parametrize('text, expected', [
    ('http://example.com', True),
    ('https://www.example.com/path?query=1#fragment', True),
    ('http://EXAMPLE.com', True),
    ('https://example.co:8443/path', True),
    ('http://example.com trailing text', True),
    ('http://12.co', True),
    ('ftp://example.com', False),
    ('example.com', False),
    ('http:/example.com', False),
    ('http://', False),
    ('', False),
    ('not a url', False),
    (' https://example.com', False),
    ('HTTPS://example.com', False),
    ('http://example.COM', False),
    ('http://a.co', False),
    ('http://example.invalid', False),
    ('http://example.com123', False),
])
def test_is_url_preserves_existing_prefix_classification(text, expected):
    """Test the existing classifier's scheme, host, suffix and prefix-match boundaries."""
    assert testee.is_url(text) is expected


@pytest.mark.parametrize('module_name', [
    'youtube_whisperer.domain', 'youtube_whisperer.models', 'youtube_whisperer.queueing',
])
def test_domain_imports_and_model_construction_create_no_resources(tmp_path, module_name):
    """Test each fresh domain entry point with owned settings and resource-construction traps."""
    script = dedent('''
        import importlib
        import socket
        import sys
        from unittest.mock import patch

        import pydantic_settings
        import redis

        with (
            patch.object(pydantic_settings.BaseSettings, '__init__', side_effect=AssertionError('Settings construction')),
            patch.object(redis.ConnectionPool, '__init__', side_effect=AssertionError('Redis pool construction')),
            patch.object(redis.Redis, '__init__', side_effect=AssertionError('Redis client construction')),
            patch.object(socket, 'socket', side_effect=AssertionError('network access')),
        ):
            importlib.import_module(sys.argv[1])
            import youtube_whisperer.domain as domain_testee
            import youtube_whisperer.models as testee
            import youtube_whisperer.queueing as queue_testee

            assert 'youtube_whisperer.config' not in sys.modules
            assert 'youtube_whisperer.utils' not in sys.modules
            assert testee.TranscriberType is domain_testee.TranscriberType
            assert queue_testee.TranscriberType is domain_testee.TranscriberType
            task = testee.Task(source='  https://example.com/video  ')
            assert task.model_dump(mode='json') == {
                'source': 'https://example.com/video', 'transcriber': 'whisper', 'language': 'en-us',
            }
            assert testee.Task.model_validate_json(task.model_dump_json()) == task
            assert domain_testee.is_url(task.source)
            assert queue_testee.get_stream_name(task.transcriber) == 'stream:whisper'
            download = testee.Task(source='https://example.com/video', transcriber='none', language='zh-cn')
            response = testee.AddTasksResponse(successful=[download], failed=[task])
            assert testee.AddTasksResponse.model_validate_json(response.model_dump_json()) == response
            queues = testee.TaskQueues(
                youtube=[download], whisper_pending=[task], whisper_active=[], azure_pending=[], azure_active=[],
            )
            assert testee.TaskQueues.model_validate_json(queues.model_dump_json()) == queues
            dead_letter = testee.DeadLetter(task=task, queue='stream:whisper', error='owned failure')
            assert testee.DeadLetter.model_validate_json(dead_letter.model_dump_json()) == dead_letter
        print('resource-free domain construction passed')
    ''')
    environment = {
        'HOME': str(tmp_path),
        'PYTHONPATH': str(Path(__file__).resolve().parents[1]),
        'PYTHONDONTWRITEBYTECODE': '1',
        'TMPDIR': str(tmp_path),
        'REDIS_HOST': 'domain.test.invalid',
        'REDIS_PORT': '6391',
        'WHISPER_ASSETS_DIR': str(tmp_path / 'assets'),
        'WHISPER_MODELS_DIR': str(tmp_path / 'models'),
        'WHISPER_USE_CUDA': 'false',
        'WHISPER_MODEL': 'test-model',
    }
    result = subprocess.run(
        [sys.executable, '-c', script, module_name],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == 'resource-free domain construction passed'
