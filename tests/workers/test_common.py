import json
from pathlib import Path

import pytest
import redis

import youtube_whisperer.workers.common as testee
from youtube_whisperer.adaptors.lang_code_adaptor import LanguageCode
from youtube_whisperer.models import Task
from youtube_whisperer.utils import TranscriberType


@pytest.fixture
def mock_redis(mocker):
    """Fixture providing a mock Redis client to inject into workers and queue helpers."""
    client = mocker.MagicMock()
    client.xautoclaim.return_value = (b'0-0', [], [])  # no stranded tasks to claim by default
    return client


@pytest.mark.parametrize('stage, log_prefix', [
    ('pel', 'Resuming orphaned'),
    ('claim', 'Claimed stranded'),
    ('new', 'Claimed new'),
])
@pytest.mark.parametrize('payload', [b'{"source":"owned","language":"en"}', b'invalid-json'])
def test_yield_task_preserves_stage_logs_and_payload_validation(mock_redis, mocker, caplog, stage, log_prefix, payload):
    """Every read stage logs its payload and propagates malformed task validation."""
    mocker.patch.object(testee, 'ensure_consumer_group')
    messages = [(b'1-0', {b'payload': payload})]
    response = [(b'stream', messages)]
    mock_redis.xreadgroup.side_effect = [response] if stage == 'pel' else [[], response]
    if stage == 'claim':
        mock_redis.xautoclaim.return_value = (b'0-0', messages, [])
    generator = testee.yield_task(mock_redis, 'stream', 'group', 'consumer')
    with caplog.at_level('INFO', logger=testee.__name__):
        try:
            if payload == b'invalid-json':
                with pytest.raises(ValueError, match='Invalid JSON'):
                    next(generator)
            else:
                assert next(generator) == (b'1-0', Task(source='owned', language='en'))
        finally:
            generator.close()
    assert caplog.messages == [f'{log_prefix} task from stream: {payload.decode()}']


@pytest.mark.parametrize('poll,idle,error', [(0, 21600, 'poll_interval'), (-1, 21600, 'poll_interval'), (5, -1, 'claim_min_idle')])
def test_yield_task_rejects_invalid_timing_before_any_redis_command(mock_redis, poll, idle, error):
    """Invalid generator timing fails on first iteration before group creation."""
    generator = testee.yield_task(mock_redis, 'stream', 'group', 'consumer', poll, idle)
    assert mock_redis.mock_calls == []
    with pytest.raises(ValueError, match=error):
        next(generator)
    assert mock_redis.mock_calls == []


@pytest.mark.parametrize('poll,idle', [(5, 21600), (2, 7), (1, 0)])
def test_yield_task_converts_finite_polling_and_nonnegative_claim_idle(mock_redis, mocker, tmp_path, poll, idle):
    """Finite empty reads revisit recovery with millisecond timings including zero idle."""
    mocker.patch.object(testee, 'ensure_consumer_group')
    payload = Task(source=str(tmp_path / 'audio.wav'), language='en').model_dump_json().encode()
    mock_redis.xreadgroup.side_effect = [[], [], []]
    mock_redis.xautoclaim.side_effect = [(b'9-0', [], []), (b'0-0', [(b'10-0', {b'payload': payload})], [])]
    args = {} if (poll, idle) == (5, 21600) else {'poll_interval_seconds': poll, 'claim_min_idle_seconds': idle}
    generator = testee.yield_task(mock_redis, 'stream', 'group', 'consumer', **args)
    assert next(generator)[0] == b'10-0'
    generator.close()
    assert mock_redis.xautoclaim.call_count == 2
    assert [call.kwargs['min_idle_time'] for call in mock_redis.xautoclaim.call_args_list] == [idle * 1000] * 2
    assert mock_redis.xautoclaim.call_args.kwargs['start_id'] == b'9-0'
    assert mock_redis.xreadgroup.call_args_list[1].kwargs['block'] == poll * 1000


def test_yield_task(mock_redis, mocker):
    """Test the streaming task generator connects properly and resolves messages natively."""
    task_dict = {'source': 'http://example.com', 'language': 'en'}
    task_json = json.dumps(task_dict).encode('utf-8')
    expected_task = Task(
        source=task_dict['source'],
        language=LanguageCode(task_dict['language']),
        transcriber=TranscriberType.WHISPER,
    )

    # > new message scrape yields task.
    mock_redis.xreadgroup.side_effect = [
        [], # 0-0 call: empty PEL
        [[b'stream:name', [[b'1234-0', {b'payload': task_json}]]]], # > call: new msg
        Exception("Test exception"), # next loop
    ]

    task_generator = testee.yield_task(mock_redis, 'stream:name', 'group_name', 'consumer', poll_interval_seconds=1)

    msg_id, task = next(task_generator)
    assert msg_id == b'1234-0'
    assert task == expected_task

    with pytest.raises(Exception, match="Test exception"):
        next(task_generator)

    assert mock_redis.xreadgroup.call_args_list == [
        mocker.call('group_name', 'consumer', {'stream:name': '0-0'}, count=1),
        mocker.call('group_name', 'consumer', {'stream:name': '>'}, count=1, block=1000),
        mocker.call('group_name', 'consumer', {'stream:name': '0-0'}, count=1),
    ]


def test_yield_task_recovers_orphaned_tasks(mock_redis, mocker):
    """Test that yield_task recovers messages stuck inside PEL before fetching newly queued assignments."""
    task_json = Task(source='/tmp/audio.wav', language='en').model_dump_json().encode('utf-8')

    # Return orphaned task on 0-0
    mock_redis.xreadgroup.side_effect = [
        [[b'stream:name', [[b'9999-0', {b'payload': task_json}]]]], # 0-0 call finds orphaned msg
    ]

    task_generator = testee.yield_task(mock_redis, 'stream:name', 'group_name', 'consumer')
    msg_id, task = next(task_generator)

    assert msg_id == b'9999-0'
    assert task == Task(source='/tmp/audio.wav', language='en')
    mock_redis.xreadgroup.assert_called_once_with('group_name', 'consumer', {'stream:name': '0-0'}, count=1)


def test_yield_task_drains_the_pel_before_claiming_or_reading_new_work(mock_redis, mocker):
    """Test that resuming after an orphaned task re-reads the PEL instead of claiming or blocking for new work."""
    task_json = Task(source='/tmp/audio.wav', language='en').model_dump_json().encode('utf-8')
    mock_redis.xreadgroup.side_effect = [
        [[b'stream:name', [[b'1111-0', {b'payload': task_json}]]]],  # 0-0: first orphan
        [[b'stream:name', [[b'2222-0', {b'payload': task_json}]]]],  # 0-0: second orphan after the continue
    ]

    gen = testee.yield_task(mock_redis, 'stream:name', 'grp', 'c1', poll_interval_seconds=1)
    first_id, _first_task = next(gen)
    second_id, _second_task = next(gen)

    assert (first_id, second_id) == (b'1111-0', b'2222-0')
    # Recovering this consumer's own backlog takes priority; claiming and blocking reads stay untouched.
    assert mock_redis.xreadgroup.call_args_list == [
        mocker.call('grp', 'c1', {'stream:name': '0-0'}, count=1),
        mocker.call('grp', 'c1', {'stream:name': '0-0'}, count=1),
    ]
    mock_redis.xautoclaim.assert_not_called()


def test_yield_task_advances_to_claiming_when_the_pel_response_has_no_messages(mock_redis, mocker):
    """Test that a PEL response carrying an empty message list advances to the claim step instead of indexing it."""
    task_json = Task(source='/tmp/audio.wav', language='en').model_dump_json().encode('utf-8')
    # A finite side effect turns a regression that keeps re-reading the PEL into a StopIteration
    # rather than a hang; the correct implementation consumes only the first response.
    mock_redis.xreadgroup.side_effect = [[[b'stream:name', []]], [[b'stream:name', []]]]
    mock_redis.xautoclaim.return_value = (b'0-0', [(b'4242-0', {b'payload': task_json})], [])

    gen = testee.yield_task(mock_redis, 'stream:name', 'grp', 'c1', poll_interval_seconds=1)
    msg_id, _task = next(gen)

    assert msg_id == b'4242-0'
    mock_redis.xreadgroup.assert_called_once_with('grp', 'c1', {'stream:name': '0-0'}, count=1)


def test_yield_task_claims_stranded_tasks_from_dead_consumers(mock_redis, mocker):
    """Test that yield_task claims PEL entries stranded by a dead consumer identity past the idle threshold."""
    task_json = Task(source='/tmp/audio.wav', language='en').model_dump_json().encode('utf-8')
    mock_redis.xreadgroup.return_value = []  # this consumer's own PEL is empty
    mock_redis.xautoclaim.return_value = (b'0-0', [(b'4242-0', {b'payload': task_json})], [])

    gen = testee.yield_task(mock_redis, 'stream:name', 'grp', 'c1', poll_interval_seconds=1, claim_min_idle_seconds=120)
    msg_id, task = next(gen)

    assert msg_id == b'4242-0'
    assert task == Task(source='/tmp/audio.wav', language='en')
    # The configured idle threshold (seconds) is passed to XAUTOCLAIM in milliseconds so live in-flight tasks are not stolen.
    mock_redis.xautoclaim.assert_called_once_with('stream:name', 'grp', 'c1', min_idle_time=120_000, start_id='0-0', count=1)


def test_yield_task_rereads_the_pel_after_claiming_a_stranded_task(mock_redis, mocker):
    """Test that resuming after a claimed task restarts at the PEL read instead of blocking for new work."""
    task_json = Task(source='/tmp/audio.wav', language='en').model_dump_json().encode('utf-8')
    mock_redis.xreadgroup.return_value = []  # this consumer's own PEL stays empty
    mock_redis.xautoclaim.side_effect = [
        (b'0-0', [(b'1111-0', {b'payload': task_json})], []),
        (b'0-0', [(b'2222-0', {b'payload': task_json})], []),
    ]

    gen = testee.yield_task(mock_redis, 'stream:name', 'grp', 'c1', poll_interval_seconds=1)
    first_id, _first_task = next(gen)
    second_id, _second_task = next(gen)

    assert (first_id, second_id) == (b'1111-0', b'2222-0')
    # Both cycles restart at the PEL read, so a claimed task never bypasses backlog recovery.
    assert mock_redis.xreadgroup.call_args_list == [
        mocker.call('grp', 'c1', {'stream:name': '0-0'}, count=1),
        mocker.call('grp', 'c1', {'stream:name': '0-0'}, count=1),
    ]


def test_yield_task_scans_empty_pages_and_retains_cursor_across_yields(mock_redis, mocker):
    """Advance past ineligible pages while preserving new-work opportunities and yielded-task cursors."""
    payload = Task(source='/tmp/audio.wav', language='en').model_dump_json().encode()
    # Redis scans a bounded prefix of ineligible entries before finding a later eligible task.
    mock_redis.xautoclaim.side_effect = [
        (b'10-0', [], []),
        (b'20-0', [], []),
        (b'30-0', [(b'25-0', {b'payload': payload})], []),
        (b'0-0', [], []),
        (b'40-0', [(b'35-0', {b'payload': payload})], []),
    ]
    mock_redis.xreadgroup.side_effect = [
        [], [],  # First empty page still reads new work.
        [], [[b'stream:name', [(b'new-0', {b'payload': payload})]]],
        [],  # Claimed task resumes at the own-PEL read.
        [], [],  # Wrap page still reads new work.
        [],
    ]
    gen = testee.yield_task(mock_redis, 'stream:name', 'grp', 'c1', poll_interval_seconds=1)
    try:
        assert [next(gen)[0] for _ in range(3)] == [b'new-0', b'25-0', b'35-0']
    finally:
        gen.close()
    assert [call.kwargs['start_id'] for call in mock_redis.xautoclaim.call_args_list] == [
        '0-0', b'10-0', b'20-0', b'30-0', b'0-0',
    ]
    assert all(call.kwargs['count'] == 1 for call in mock_redis.xautoclaim.call_args_list)
    assert [call.args[2] for call in mock_redis.xreadgroup.call_args_list] == [
        {'stream:name': '0-0'}, {'stream:name': '>'},
        {'stream:name': '0-0'}, {'stream:name': '>'},
        {'stream:name': '0-0'}, {'stream:name': '0-0'},
        {'stream:name': '>'}, {'stream:name': '0-0'},
    ]


@pytest.mark.parametrize('missing_group_path', ['pel', 'claim', 'new'])
def test_yield_task_resets_advanced_cursor_after_any_group_recreation(mock_redis, mocker, missing_group_path):
    """Restart an advanced claim scan after NOGROUP on each of the three polling paths."""
    payload = Task(source='/tmp/audio.wav', language='en').model_dump_json().encode()
    mock_ensure = mocker.patch.object(testee, 'ensure_consumer_group')
    missing = redis.exceptions.ResponseError('NOGROUP missing')
    first_new = [[b'stream:name', [(b'new-0', {b'payload': payload})]]]
    reads = [[], first_new]
    claims = [(b'10-0', [], [])]
    if missing_group_path == 'pel':
        reads += [missing, []]
    elif missing_group_path == 'claim':
        reads += [[], []]
        claims += [missing]
    else:
        reads += [[], missing, []]
        claims += [(b'20-0', [], [])]
    claims += [(b'0-0', [(b'claimed-0', {b'payload': payload})], [])]
    mock_redis.xreadgroup.side_effect = reads
    mock_redis.xautoclaim.side_effect = claims
    gen = testee.yield_task(mock_redis, 'stream:name', 'grp', 'c1')
    try:
        assert next(gen)[0] == b'new-0'
        assert next(gen)[0] == b'claimed-0'
    finally:
        gen.close()
    expected_cursors = ['0-0', '0-0'] if missing_group_path == 'pel' else ['0-0', b'10-0', '0-0']
    assert [call.kwargs['start_id'] for call in mock_redis.xautoclaim.call_args_list] == expected_cursors
    assert mock_ensure.call_args_list == [
        mocker.call(mock_redis, 'stream:name', 'grp'),
        mocker.call(mock_redis, 'stream:name', 'grp'),
    ]


def test_yield_task_self_heals_after_nogroup_on_claim(mock_redis, mocker):
    """Test that a NOGROUP error on the XAUTOCLAIM path also recreates the consumer group."""
    task_json = Task(source='/tmp/audio.wav', language='en').model_dump_json().encode('utf-8')
    mock_ensure = mocker.patch.object(testee, 'ensure_consumer_group')
    mock_redis.xreadgroup.return_value = []  # PEL always empty so the claim step is reached
    mock_redis.xautoclaim.side_effect = [
        redis.exceptions.ResponseError("NOGROUP No such key 'stream:name'"),  # group gone during claim
        (b'0-0', [(b'5555-0', {b'payload': task_json})], []),                  # claim succeeds after heal
    ]

    gen = testee.yield_task(mock_redis, 'stream:name', 'grp', 'c1', poll_interval_seconds=1)
    msg_id, _task = next(gen)

    assert msg_id == b'5555-0'
    assert mock_ensure.call_count == 2  # once at startup + once after NOGROUP on claim


def test_yield_task_raises_non_nogroup_errors_from_the_claim(mock_redis, mocker):
    """Test that a non-NOGROUP ResponseError during the claim step propagates instead of being swallowed."""
    mocker.patch.object(testee, 'ensure_consumer_group')
    mock_redis.xreadgroup.return_value = []  # PEL empty so the claim step is reached
    # A single-element side effect turns a swallowing regression into a StopIteration rather than a hang.
    mock_redis.xautoclaim.side_effect = [redis.exceptions.ResponseError("WRONGTYPE unexpected")]

    gen = testee.yield_task(mock_redis, 'stream:name', 'grp', 'c1', poll_interval_seconds=1)
    with pytest.raises(redis.exceptions.ResponseError, match="WRONGTYPE"):
        next(gen)


def test_yield_task_polls_again_when_the_blocking_read_times_out(mock_redis, mocker):
    """Test that a blocking read returning nothing starts another poll cycle instead of ending the generator."""
    task_json = Task(source='/tmp/audio.wav', language='en').model_dump_json().encode('utf-8')
    mock_redis.xreadgroup.side_effect = [
        [],                                                          # 0-0: empty PEL
        [],                                                          # >: blocking read timed out
        [],                                                          # 0-0: empty PEL on the next cycle
        [[b'stream:name', [[b'7777-0', {b'payload': task_json}]]]],  # >: a task finally arrives
    ]

    gen = testee.yield_task(mock_redis, 'stream:name', 'grp', 'c1', poll_interval_seconds=1)
    msg_id, _task = next(gen)

    assert msg_id == b'7777-0'
    assert mock_redis.xreadgroup.call_count == 4  # an idle queue keeps polling rather than stopping the worker


def test_yield_task_polls_again_when_the_blocking_read_returns_no_messages(mock_redis, mocker):
    """Test that a blocking read carrying an empty message list starts another poll cycle instead of indexing it."""
    task_json = Task(source='/tmp/audio.wav', language='en').model_dump_json().encode('utf-8')
    mock_redis.xreadgroup.side_effect = [
        [],                                                          # 0-0: empty PEL
        [[b'stream:name', []]],                                      # >: stream named, but no messages
        [],                                                          # 0-0: empty PEL on the next cycle
        [[b'stream:name', [[b'8888-0', {b'payload': task_json}]]]],  # >: a task finally arrives
    ]

    gen = testee.yield_task(mock_redis, 'stream:name', 'grp', 'c1', poll_interval_seconds=1)
    msg_id, _task = next(gen)

    assert msg_id == b'8888-0'
    assert mock_redis.xreadgroup.call_count == 4


def test_yield_task_self_heals_after_nogroup_on_pel_read(mock_redis, mocker):
    """Test that a NOGROUP error on the PEL read path triggers consumer group recreation."""
    task_json = Task(source='/tmp/audio.wav', language='en').model_dump_json().encode('utf-8')
    mock_ensure = mocker.patch.object(testee, 'ensure_consumer_group')

    mock_redis.xreadgroup.side_effect = [
        redis.exceptions.ResponseError("NOGROUP No such key 'stream:name'"),   # 0-0: group gone
        [],                                                                      # 0-0: empty PEL after heal
        [[b'stream:name', [[b'5555-0', {b'payload': task_json}]]]],             # >: new msg
    ]

    gen = testee.yield_task(mock_redis, 'stream:name', 'grp', 'c1', poll_interval_seconds=1)
    msg_id, task = next(gen)

    assert msg_id == b'5555-0'
    assert task.source == '/tmp/audio.wav'
    assert mock_ensure.call_count == 2  # once at startup + once after NOGROUP


def test_yield_task_self_heals_after_nogroup_on_the_blocking_read(mock_redis, mocker):
    """Test that a NOGROUP error on the blocking read recreates the consumer group and resumes polling."""
    task_json = Task(source='/tmp/audio.wav', language='en').model_dump_json().encode('utf-8')
    mock_ensure = mocker.patch.object(testee, 'ensure_consumer_group')
    mock_redis.xreadgroup.side_effect = [
        [],                                                          # 0-0: empty PEL
        redis.exceptions.ResponseError("NOGROUP No such key 'stream:name'"),  # >: group gone
        [],                                                          # 0-0: empty PEL after heal
        [[b'stream:name', [[b'6666-0', {b'payload': task_json}]]]],  # >: new task
    ]

    gen = testee.yield_task(mock_redis, 'stream:name', 'grp', 'c1', poll_interval_seconds=1)
    msg_id, _task = next(gen)

    assert msg_id == b'6666-0'
    # Both the startup call and the recovery call must recreate this worker's own group on its own
    # stream. Counting the calls alone would pass even if recovery named a different stream, which
    # would leave the real group missing and the worker looping on NOGROUP forever.
    assert mock_ensure.call_args_list == [
        mocker.call(mock_redis, 'stream:name', 'grp'),
        mocker.call(mock_redis, 'stream:name', 'grp'),
    ]


def test_yield_task_raises_non_nogroup_errors(mock_redis, mocker):
    """Test that non-NOGROUP ResponseErrors are propagated instead of swallowed."""
    mocker.patch.object(testee, 'ensure_consumer_group')

    mock_redis.xreadgroup.side_effect = redis.exceptions.ResponseError("WRONGTYPE unexpected")

    gen = testee.yield_task(mock_redis, 'stream:name', 'grp', 'c1')
    with pytest.raises(redis.exceptions.ResponseError, match="WRONGTYPE"):
        next(gen)


def test_yield_task_raises_non_nogroup_errors_from_the_blocking_read(mock_redis, mocker):
    """Test that a non-NOGROUP ResponseError on the blocking read propagates instead of being swallowed."""
    mocker.patch.object(testee, 'ensure_consumer_group')
    # A single-element side effect turns a swallowing regression into a StopIteration rather than a hang.
    mock_redis.xreadgroup.side_effect = [
        [],                                                       # 0-0: empty PEL
        redis.exceptions.ResponseError("WRONGTYPE unexpected"),   # >: unexpected server failure
    ]

    gen = testee.yield_task(mock_redis, 'stream:name', 'grp', 'c1', poll_interval_seconds=1)
    with pytest.raises(redis.exceptions.ResponseError, match="WRONGTYPE"):
        next(gen)


def test_model_copy_preserves_non_source_fields():
    """Test copying a task while only replacing its source."""
    task = Task(
        source='https://example.com/playlist',
        language='en',
        transcriber=TranscriberType.AZURE,
    )
    result = task.model_copy(update={'source': 'https://example.com/video'})
    assert result == Task(
        source='https://example.com/video',
        language='en',
        transcriber=TranscriberType.AZURE,
    )


class MockWorker(testee.TranscriptionWorker):
    def dispatch_task(self, task: Task, source: Path) -> None:
        pass


def test_base_worker_supports_explicit_identity_and_legacy_accessor_overrides(mocker, mock_redis):
    """Legacy constructors and getter overrides retain queue identity and runtime ownership."""
    class LegacyWorker(testee.BaseWorker):
        """Model a public subclass using the original constructor and accessors."""

        def __init__(self, client):
            """Set legacy identity before calling the original base constructor."""
            self.stream_name = 'legacy-stream'
            self.slot = 'legacy-consumer'
            super().__init__(client)

        def get_stream_name(self) -> str:
            """Return the legacy stream identity."""
            return self.stream_name

        def get_consumer_name(self) -> str:
            """Return the legacy consumer identity."""
            return self.slot

        def process_task(self, task: Task) -> None:
            """Complete a synthetic task without external resources."""

    legacy = LegacyWorker(mock_redis)
    runtime = mocker.Mock(client=mock_redis)
    explicit = MockWorker(TranscriberType.WHISPER, 'first', runtime=runtime)
    assert explicit.transcriber is TranscriberType.WHISPER
    assert explicit.stream_name == 'stream:whisper'
    explicit.slot, explicit.stream_name = 'changed-consumer', 'changed-stream'
    assert explicit.get_consumer_name() == 'changed-consumer'
    assert explicit.get_stream_name() == 'changed-stream'
    yield_task = mocker.patch.object(testee, 'yield_task', return_value=iter([]))
    legacy.yield_tasks(7)
    assert yield_task.call_args.kwargs['stream_name'] == 'legacy-stream'
    assert yield_task.call_args.kwargs['consumer_name'] == 'legacy-consumer'
    assert yield_task.call_args.kwargs['client'] is mock_redis
    legacy.runtime.close()
    runtime.close.assert_not_called()


def test_base_worker_legacy_read_only_identity_properties_are_not_assigned(mocker):
    """The original constructor leaves subclass read-only identity properties intact."""
    class PropertyWorker(testee.BaseWorker):
        """Model a legacy subclass exposing read-only identity data."""

        @property
        def stream_name(self) -> str:
            """Return the legacy stream without a setter."""
            return 'property-stream'

        @property
        def slot(self) -> str:
            """Return the legacy consumer without a setter."""
            return 'property-consumer'

        def get_stream_name(self) -> str:
            """Return the read-only legacy stream property."""
            return self.stream_name

        def get_consumer_name(self) -> str:
            """Return the read-only legacy consumer property."""
            return self.slot

        def process_task(self, task: Task) -> None:
            """Complete a synthetic task without external resources."""

    worker = PropertyWorker(runtime=mocker.Mock())
    assert worker.get_stream_name() == 'property-stream'
    assert worker.get_consumer_name() == 'property-consumer'


@pytest.mark.parametrize('accessor', ['get_stream_name', 'get_consumer_name'])
def test_base_worker_missing_identity_requires_legacy_override(mocker, accessor):
    """An omitted identity produces an explicit error rather than an invalid Redis key."""
    class IdentitylessWorker(testee.BaseWorker):
        """Supply task handling while leaving identity unconfigured."""

        def process_task(self, task: Task) -> None:
            """Complete a synthetic task without external resources."""

    worker = IdentitylessWorker(runtime=mocker.Mock())
    with pytest.raises(NotImplementedError, match='identity is not configured'):
        getattr(worker, accessor)()


@pytest.mark.parametrize('poll', [0, -1])
def test_worker_yield_tasks_rejects_invalid_poll_without_redis(mock_redis, poll):
    """The worker polling entry point rejects invalid intervals without Redis calls."""
    worker = MockWorker(TranscriberType.WHISPER, 'owned', client=mock_redis)
    with pytest.raises(ValueError, match='poll_interval_seconds'):
        worker.yield_tasks(poll)
    assert mock_redis.mock_calls == []
    worker.runtime.close()


def test_transcription_worker_consumes_its_transcriber_stream_under_its_slot(mocker, mock_redis):
    """Test that a transcription worker reads its transcriber's stream under the slot identity it was given."""
    mock_yield = mocker.patch.object(testee, 'yield_task', return_value=iter([]))
    settings = testee.Settings(worker_claim_min_idle_seconds=99)
    worker = MockWorker(TranscriberType.WHISPER, 'gpu-0', client=mock_redis, settings=settings)

    assert list(worker.yield_tasks(poll_interval_seconds=7)) == []

    # The slot is the consumer identity that makes this worker's PEL recoverable after a restart.
    mock_yield.assert_called_once_with(
        client=mock_redis,
        stream_name=testee.get_stream_name(TranscriberType.WHISPER),
        group_name=testee.WORKERS_GROUP,
        consumer_name='gpu-0',
        poll_interval_seconds=7,
        claim_min_idle_seconds=99,
    )


def test_worker_snapshot_claim_threshold_isolated_after_environment_mutation(mocker, monkeypatch):
    """Borrowed clients and two supplied worker snapshots retain their own claim thresholds."""
    snapshots = [testee.Settings(worker_claim_min_idle_seconds=value) for value in [31, 47]]
    clients = [mocker.Mock(), mocker.Mock()]
    workers = [MockWorker(TranscriberType.WHISPER, str(index), client, settings=snapshot)
               for index, (client, snapshot) in enumerate(zip(clients, snapshots, strict=True))]
    mock_yield = mocker.patch.object(testee, 'yield_task', return_value=iter([]))
    monkeypatch.setenv('WORKER_CLAIM_MIN_IDLE_SECONDS', '999')
    for worker, client, snapshot in zip(workers, clients, snapshots, strict=True):
        worker.yield_tasks(3)
        assert mock_yield.call_args.kwargs['claim_min_idle_seconds'] == snapshot.worker_claim_min_idle_seconds
        assert mock_yield.call_args.kwargs['client'] is client
        assert worker.settings is snapshot


@pytest.mark.parametrize('failure', [None, RuntimeError('queue'), KeyboardInterrupt('queue')])
def test_standalone_worker_queue_closes_owned_runtime_on_every_exit(mocker, failure):
    """A directly constructed worker closes its owned runtime on normal and interrupted exit."""
    from contextlib import nullcontext

    runtime = mocker.patch.object(testee, 'Runtime').return_value
    worker = MockWorker(TranscriberType.WHISPER, 'owned')
    mocker.patch.object(worker, 'yield_tasks', return_value=iter([]), side_effect=failure)
    expected = pytest.raises(type(failure), match='queue') if failure is not None else nullcontext()
    with expected:
        worker.process_queue()
    runtime.close.assert_called_once_with()


@pytest.mark.parametrize('failure', [None, RuntimeError('borrowed'), KeyboardInterrupt('borrowed')])
def test_worker_queue_leaves_borrowed_runtime_open(mocker, failure):
    """Queue completion does not steal ownership from the caller's runtime."""
    from contextlib import nullcontext

    runtime = mocker.Mock()
    worker = MockWorker(TranscriberType.WHISPER, 'owned', runtime=runtime)
    mocker.patch.object(worker, 'yield_tasks', return_value=iter([]), side_effect=failure)
    expected = pytest.raises(type(failure), match='borrowed') if failure is not None else nullcontext()
    with expected:
        worker.process_queue()
    runtime.close.assert_not_called()


@pytest.mark.parametrize('poll', [0, -1])
@pytest.mark.parametrize('borrowed', [False, True])
def test_worker_invalid_poll_preserves_runtime_ownership(mocker, mock_redis, poll, borrowed):
    """Invalid direct execution closes only the worker-owned runtime before Redis commands."""
    runtime = mocker.Mock(client=mock_redis)
    factory = mocker.patch.object(testee, 'Runtime', return_value=runtime)
    worker = MockWorker(TranscriberType.WHISPER, 'owned', runtime=runtime if borrowed else None)
    with pytest.raises(ValueError, match='poll_interval_seconds'):
        worker.process_queue(poll)
    assert mock_redis.mock_calls == []
    assert runtime.close.call_count == (0 if borrowed else 1)
    assert factory.call_count == (0 if borrowed else 1)


def test_process_active_slot_queue_full_flow(mocker, mock_redis):
    """Test successful end-to-end processing guarantees message acknowledging and deletion."""
    task = Task(source='/tmp/audio.wav', language='en', transcriber=TranscriberType.WHISPER)
    mocker.patch.object(testee.TranscriptionWorker, 'yield_tasks', return_value=iter([(b'000-1', task)]))
    mocker.patch.object(testee, 'is_url', return_value=False)
    worker = MockWorker(TranscriberType.WHISPER, 'gpu-0', client=mock_redis)
    dispatch_task = mocker.patch.object(worker, 'dispatch_task')
    mock_dead_letter = mocker.patch.object(testee, 'queue_dead_letter')

    worker.process_queue()

    dispatch_task.assert_called_once_with(task, Path('/tmp/audio.wav'))
    mock_dead_letter.assert_not_called()
    mock_pipe = mock_redis.pipeline.return_value
    mock_pipe.xack.assert_called_once_with(testee.get_stream_name(TranscriberType.WHISPER), testee.WORKERS_GROUP, b'000-1')
    mock_pipe.xdel.assert_called_once_with(testee.get_stream_name(TranscriberType.WHISPER), b'000-1')
    mock_pipe.execute.assert_called_once()


def test_process_active_slot_queue_dead_letters_failures(mocker, mock_redis):
    """Test that transcription failures fall strictly to dead lettering but still invoke xack logic safely."""
    task = Task(source='/tmp/audio.wav', language='en', transcriber=TranscriberType.WHISPER)
    mocker.patch.object(testee.TranscriptionWorker, 'yield_tasks', return_value=iter([(b'999-8', task)]))
    mocker.patch.object(testee, 'is_url', return_value=False)
    worker = MockWorker(TranscriberType.WHISPER, 'gpu-0', client=mock_redis)
    dispatch_task = mocker.patch.object(worker, 'dispatch_task', side_effect=RuntimeError('boom'))
    mock_dead_letter = mocker.patch.object(testee, 'queue_dead_letter')

    worker.process_queue()

    dispatch_task.assert_called_once_with(task, Path('/tmp/audio.wav'))
    mock_dead_letter.assert_called_once_with(
        mock_redis,
        task,
        testee.get_stream_name(TranscriberType.WHISPER),
        'boom',
    )
    mock_pipe = mock_redis.pipeline.return_value
    mock_pipe.xack.assert_called_once_with(testee.get_stream_name(TranscriberType.WHISPER), testee.WORKERS_GROUP, b'999-8')
    mock_pipe.execute.assert_called_once()


def test_process_active_slot_queue_dead_letters_url_tasks(mocker, mock_redis):
    """Test that unexpected URL tasks identically invoke safe xack pipeline behavior to discard format mismatches."""
    task = Task(source='https://example.com/video', language='en', transcriber=TranscriberType.WHISPER)
    mocker.patch.object(testee.TranscriptionWorker, 'yield_tasks', return_value=iter([(b'123-1', task)]))
    mocker.patch.object(testee, 'is_url', return_value=True)
    worker = MockWorker(TranscriberType.WHISPER, 'gpu-0', client=mock_redis)
    dispatch_task = mocker.patch.object(worker, 'dispatch_task')
    mock_dead_letter = mocker.patch.object(testee, 'queue_dead_letter')

    worker.process_queue()

    dispatch_task.assert_not_called()
    mock_dead_letter.assert_called_once_with(
        mock_redis,
        task,
        testee.get_stream_name(TranscriberType.WHISPER),
        f"Transcription worker received URL task: {task.source}",
    )
    mock_pipe = mock_redis.pipeline.return_value
    mock_pipe.xack.assert_called_once_with(testee.get_stream_name(TranscriberType.WHISPER), testee.WORKERS_GROUP, b'123-1')
    mock_pipe.xdel.assert_called_once_with(testee.get_stream_name(TranscriberType.WHISPER), b'123-1')
    mock_pipe.execute.assert_called_once()


def test_process_queue_leaves_task_pending_on_base_exception(mocker, mock_redis):
    """Test that a BaseException mid-task leaves the message un-acked so a restart can recover it."""
    task = Task(source='/tmp/audio.wav', language='en', transcriber=TranscriberType.WHISPER)
    mocker.patch.object(testee.TranscriptionWorker, 'yield_tasks', return_value=iter([(b'777-7', task)]))
    mocker.patch.object(testee, 'is_url', return_value=False)
    worker = MockWorker(TranscriberType.WHISPER, 'gpu-0', client=mock_redis)
    mocker.patch.object(worker, 'dispatch_task', side_effect=KeyboardInterrupt)
    mock_dead_letter = mocker.patch.object(testee, 'queue_dead_letter')

    with pytest.raises(KeyboardInterrupt):
        worker.process_queue()

    mock_dead_letter.assert_not_called()
    mock_redis.pipeline.assert_not_called()


def test_process_queue_leaves_task_pending_when_dead_letter_fails(mocker, mock_redis):
    """Test that a failed dead-letter write leaves the message un-acked instead of dropping it."""
    task = Task(source='/tmp/audio.wav', language='en', transcriber=TranscriberType.WHISPER)
    mocker.patch.object(testee.TranscriptionWorker, 'yield_tasks', return_value=iter([(b'888-8', task)]))
    mocker.patch.object(testee, 'is_url', return_value=False)
    worker = MockWorker(TranscriberType.WHISPER, 'gpu-0', client=mock_redis)
    mocker.patch.object(worker, 'dispatch_task', side_effect=RuntimeError('boom'))
    mocker.patch.object(testee, 'queue_dead_letter', side_effect=RuntimeError('redis down'))

    with pytest.raises(RuntimeError, match='redis down'):
        worker.process_queue()

    mock_redis.pipeline.assert_not_called()
