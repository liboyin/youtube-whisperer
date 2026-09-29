import errno
import io
import os
import stat
import subprocess
import sys
import wave
from pathlib import Path
from types import SimpleNamespace

import pytest
from pathlib_extensions import NotAFileError, OverwriteMode

import youtube_whisperer.transcriber.waveform_loader as testee


class ConversionProcess:
    """Provide controlled writes and explicit child completion without background work."""

    def __init__(self, stage, *, returncode=0, interrupt=None, during=None):
        """Own per-test pipes, writes, cancellation state and completion accounting."""
        self.stage = stage
        self.returncode = returncode
        self.interrupt = interrupt
        self.during = during
        self.alive = True
        self.killed = False
        self.events = []
        self.stdin = None
        self.stdout = io.BytesIO()
        self.stderr = io.BytesIO()

    def communicate(self):
        """Write partial bytes before controlled failure or complete bytes on success."""
        self.events.append('communicate')
        if self.killed or not self.alive:
            return b'captured stdout', b'conversion failed'
        self.stage.write_bytes(b'partial')
        if self.during is not None:
            self.during(self.stage, self)
        if self.interrupt is not None:
            raise self.interrupt
        if self.returncode == 0:
            self.stage.write_bytes(b'complete audio')
        self.alive = False
        return b'captured stdout', b'conversion failed'

    def poll(self):
        """Expose completion only when the fake child has stopped writing."""
        return None if self.alive else self.returncode

    def kill(self):
        """Cancel all possible future writes before draining the owned fake child."""
        self.events.append('kill')
        self.killed = True
        self.alive = False


@pytest.fixture
def conversion(mocker, tmp_path):
    """Create a fresh converter graph and process factory for owned temporary input."""
    source = tmp_path / 'input.mp3'
    source.write_bytes(b'synthetic source')
    state = SimpleNamespace(source=source, options={}, processes=[], stages=[])
    stream = mocker.MagicMock()
    stream.output.return_value = stream
    state.stream = stream
    state.input = mocker.patch.object(testee.ffmpeg, 'input', return_value=stream)

    def start(**kwargs):
        """Start a controlled child with its recorded exclusively created stage."""
        stage = Path(stream.output.call_args.args[0])
        state.stages.append(stage)
        process = ConversionProcess(stage, **state.options)
        state.processes.append(process)
        return process

    stream.run_async.side_effect = start
    return state


def test_conversion_interrupt_reaps_and_closes_child_before_stage_removal(conversion, mocker, tmp_path):
    """An interrupted writer is killed and drained before its partial stage is unlinked."""
    output = tmp_path / 'output.wav'
    output.write_bytes(b'previous good audio')
    conversion.options['interrupt'] = KeyboardInterrupt()
    original_unlink = Path.unlink

    def unlink(path, *args, **kwargs):
        """Require cancellation, quiescence and closed owned pipes at cleanup."""
        if path in conversion.stages:
            process = conversion.processes[-1]
            assert process.events == ['communicate', 'kill', 'communicate']
            assert not process.alive
            assert process.stdout.closed and process.stderr.closed
        return original_unlink(path, *args, **kwargs)

    mocker.patch.object(testee.Path, 'unlink', unlink)
    with pytest.raises(KeyboardInterrupt):
        testee.save_as_wav_file(conversion.source, output, OverwriteMode.ALWAYS)

    assert output.read_bytes() == b'previous good audio'
    assert not conversion.stages[0].exists()


def test_conversion_interrupt_reaps_real_owned_child_before_unlink(mocker, tmp_path):
    """A pipe handshake interrupts a real owned child and cleanup observes its exit."""
    source = tmp_path / 'input.mp3'
    source.write_bytes(b'synthetic source')
    output = tmp_path / 'output.wav'
    stream = mocker.MagicMock()
    stream.output.return_value = stream
    mocker.patch.object(testee.ffmpeg, 'input', return_value=stream)
    children = []
    stages = []

    def start(**kwargs):
        """Block an owned child on stdin after signalling its partial write."""
        stage = Path(stream.output.call_args.args[0])
        stages.append(stage)
        script = "import pathlib,sys; pathlib.Path(sys.argv[1]).write_bytes(b'partial'); sys.stdout.buffer.write(b'ready'); sys.stdout.flush(); sys.stdin.buffer.read()"
        child = subprocess.Popen([sys.executable, '-c', script, str(stage)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        children.append(child)
        communicate = child.communicate

        def interrupt_once():
            """Observe explicit readiness before raising the injected interruption."""
            assert child.stdout.read(5) == b'ready'
            mocker.patch.object(child, 'communicate', communicate)
            raise KeyboardInterrupt

        mocker.patch.object(child, 'communicate', interrupt_once)
        return child

    stream.run_async.side_effect = start
    original_unlink = Path.unlink

    def unlink(path, *args, **kwargs):
        """Require the real child to be reaped with all owned pipes closed."""
        if path in stages:
            child = children[0]
            assert child.returncode is not None
            assert child.poll() is not None
            assert all(pipe.closed for pipe in (child.stdin, child.stdout, child.stderr))
        return original_unlink(path, *args, **kwargs)

    mocker.patch.object(testee.Path, 'unlink', unlink)
    try:
        with pytest.raises(KeyboardInterrupt):
            testee.save_as_wav_file(source, output)
        assert not output.exists()
        assert not stages[0].exists()
    finally:
        for child in children:
            if child.poll() is None:
                child.kill()
            try:
                # Production failure may already have closed pipes before reaping.
                child.wait()
            finally:
                for pipe in (child.stdin, child.stdout, child.stderr):
                    if pipe is not None:
                        pipe.close()


@pytest.mark.parametrize('existing', [False, True])
def test_save_as_wav_file_partial_failure_preserves_final_and_retry_completes(conversion, tmp_path, caplog, existing):
    """Partial failed conversion leaves no false marker and retry publishes complete bytes."""
    output = tmp_path / 'output.wav'
    if existing:
        output.write_bytes(b'previous good audio')
    conversion.options['returncode'] = 1
    with pytest.raises(testee.ffmpeg.Error) as caught:
        testee.save_as_wav_file(conversion.source, output, OverwriteMode.ALWAYS)
    assert caught.value.stdout == b'captured stdout'
    assert caught.value.stderr == b'conversion failed'
    assert 'ffmpeg failed: conversion failed' in caplog.text
    if existing:
        assert output.read_bytes() == b'previous good audio'
    else:
        assert not output.exists()
    assert all(not stage.exists() for stage in conversion.stages)
    assert not conversion.processes[0].alive
    assert conversion.processes[0].stdout.closed and conversion.processes[0].stderr.closed

    conversion.options.clear()
    assert testee.save_as_wav_file(conversion.source, output, OverwriteMode.ALWAYS) == output
    assert output.read_bytes() == b'complete audio'
    assert len(conversion.processes) == 2
    assert all(not stage.exists() for stage in conversion.stages)


def test_save_as_wav_file_startup_error_cleans_owned_stage(conversion, tmp_path):
    """Failure to start ffmpeg preserves prior output and removes the owned stage."""
    output = tmp_path / 'output.wav'
    output.write_bytes(b'previous good audio')
    conversion.stream.run_async.side_effect = FileNotFoundError('ffmpeg missing')
    with pytest.raises(FileNotFoundError, match='ffmpeg missing'):
        testee.save_as_wav_file(conversion.source, output, OverwriteMode.ALWAYS)
    assert output.read_bytes() == b'previous good audio'
    assert not list(tmp_path.glob('.wav-*'))


@pytest.mark.parametrize('policy, consent', [(OverwriteMode.NEVER, None), (OverwriteMode.RENAME, None), (OverwriteMode.PROMPT, False)])
def test_save_as_wav_file_declined_overwrite_avoids_conversion_and_prompt_duplication(conversion, mocker, tmp_path, policy, consent):
    """Declined overwrite skips all conversion and preserves the existing file."""
    output = tmp_path / 'output.wav'
    output.write_bytes(b'previous good audio')
    import pathlib_extensions.overwrite as helpers
    prompt = mocker.patch.object(helpers, 'user_confirms_overwrite', return_value=consent)
    assert testee.save_as_wav_file(conversion.source, output, policy) is None
    assert output.read_bytes() == b'previous good audio'
    conversion.input.assert_not_called()
    assert prompt.call_count == (1 if policy == OverwriteMode.PROMPT else 0)
    assert not list(tmp_path.glob('.wav-*'))


@pytest.mark.parametrize('policy', [OverwriteMode.ALWAYS, OverwriteMode.PROMPT])
def test_save_as_wav_file_approved_overwrite_publishes_after_completion_with_one_prompt(conversion, mocker, tmp_path, policy):
    """Approved conversion preserves prior output until completion and prompts once."""
    output = tmp_path / 'output.aiff'
    output.write_bytes(b'previous good audio')
    import pathlib_extensions.overwrite as helpers
    prompt = mocker.patch.object(helpers, 'user_confirms_overwrite', return_value=True)

    def during(stage, process):
        """Inspect the previous output while partial bytes remain unpublished."""
        assert stage != output
        assert stage.parent == output.parent
        assert stage.suffix == output.suffix
        assert output.read_bytes() == b'previous good audio'
        assert stage.read_bytes() == b'partial'
        assert process.alive

    conversion.options['during'] = during
    result = None
    error = None
    try:
        result = testee.save_as_wav_file(conversion.source, output, policy)
    except (testee.ffmpeg.Error, OSError) as caught:
        error = caught
    assert error is None, f'Approved conversion failed: {error!r}'
    assert result == output
    assert output.read_bytes() == b'complete audio'
    conversion.input.assert_called_once_with(str(conversion.source))
    assert conversion.stream.output.call_args.kwargs == {'acodec': 'pcm_s16le', 'ac': 1, 'ar': 16000}
    assert conversion.stream.run_async.call_args.kwargs == {'overwrite_output': True, 'pipe_stdout': True, 'pipe_stderr': True}
    assert prompt.call_count == (1 if policy == OverwriteMode.PROMPT else 0)
    assert all(not stage.exists() for stage in conversion.stages)


@pytest.mark.parametrize('suffix', ['.wav', '.WAV', '.aiff', ''])
def test_save_as_wav_file_default_and_explicit_suffix_preserve_container_inference(conversion, tmp_path, suffix):
    """Default output is WAV while explicit suffixes reach ffmpeg without forced format."""
    output = None if suffix == '.wav' else tmp_path / f'output{suffix}'
    final = output or conversion.source.with_suffix('.wav')
    assert testee.save_as_wav_file(conversion.source, output, OverwriteMode.NEVER) == final
    assert conversion.stages[0].suffix == suffix
    assert final.read_bytes() == b'complete audio'
    assert 'format' not in conversion.stream.output.call_args.kwargs


def test_save_as_wav_file_input_and_output_helpers_reject_invalid_files(conversion, tmp_path):
    """Helper validation rejects missing input and directory output before ffmpeg."""
    with pytest.raises(FileNotFoundError):
        testee.save_as_wav_file(tmp_path / 'missing.mp3')
    with pytest.raises(OSError) as rejected:
        testee.save_as_wav_file(conversion.source, tmp_path)
    assert isinstance(rejected.value, NotAFileError)
    conversion.input.assert_not_called()


def test_save_as_wav_file_symlink_target_mode_and_hardlinked_alias_are_preserved(conversion, tmp_path):
    """Replacement follows symlinks, retains modes and leaves hardlink aliases unchanged."""
    target = tmp_path / 'nested' / 'target.bin'
    target.parent.mkdir()
    target.write_bytes(b'previous good audio')
    target.chmod(0o640)
    alias = tmp_path / 'alias.wav'
    os.link(target, alias)
    output = tmp_path / 'output.aiff'
    output.symlink_to(target)
    assert testee.save_as_wav_file(conversion.source, output, OverwriteMode.ALWAYS) == output
    assert output.is_symlink()
    assert target.read_bytes() == b'complete audio'
    assert stat.S_IMODE(target.stat().st_mode) == 0o640
    assert alias.read_bytes() == b'previous good audio'
    assert conversion.stages[0].parent == target.parent
    assert conversion.stages[0].suffix == '.aiff'


def test_save_as_wav_file_new_file_uses_inherited_ordinary_creation_mode(conversion, tmp_path):
    """New publication has the same mode as ordinary exclusive file creation."""
    control = tmp_path / 'control'
    with control.open('xb'):
        pass
    output = tmp_path / 'output.wav'
    testee.save_as_wav_file(conversion.source, output)
    assert stat.S_IMODE(output.stat().st_mode) == stat.S_IMODE(control.stat().st_mode)


@pytest.mark.parametrize('policy', [OverwriteMode.NEVER, OverwriteMode.RENAME])
@pytest.mark.parametrize('competitor', ['file', 'symlink', 'directory', 'dangling'])
def test_save_as_wav_file_no_clobber_accepts_only_completed_competing_files(conversion, tmp_path, policy, competitor):
    """Late completed competitors survive while directory and dangling collisions raise."""
    output = tmp_path / 'output.wav'
    other = tmp_path / 'other.wav'

    def during(stage, process):
        """Create a controlled competitor after preflight and before publication."""
        if competitor == 'file':
            output.write_bytes(b'competitor')
        elif competitor == 'symlink':
            other.write_bytes(b'competitor')
            output.symlink_to(other)
        elif competitor == 'directory':
            output.mkdir()
        else:
            output.symlink_to(other)

    conversion.options['during'] = during
    if competitor in ('file', 'symlink'):
        result = None
        error = None
        try:
            result = testee.save_as_wav_file(conversion.source, output, policy)
        except (testee.ffmpeg.Error, OSError) as caught:
            error = caught
        assert error is None, f'Completed competing output rejected: {error!r}'
        assert result == output
        assert output.read_bytes() == b'competitor'
    else:
        with pytest.raises(FileExistsError):
            testee.save_as_wav_file(conversion.source, output, policy)
        assert output.is_dir() if competitor == 'directory' else output.is_symlink() and not other.exists()
    assert all(not stage.exists() for stage in conversion.stages)


@pytest.mark.parametrize('policy', [OverwriteMode.ALWAYS, OverwriteMode.NEVER, OverwriteMode.RENAME])
def test_save_as_wav_file_publication_failure_cleans_stage_without_fallback(conversion, mocker, tmp_path, policy):
    """Replacement and unsupported hard-link errors propagate without clobbering output."""
    output = tmp_path / 'output.wav'
    if policy == OverwriteMode.ALWAYS:
        output.write_bytes(b'previous good audio')
        mocker.patch.object(testee.Path, 'replace', side_effect=PermissionError('publication failed'))
    else:
        mocker.patch.object(testee.os, 'link', side_effect=OSError(errno.EOPNOTSUPP, 'publication failed'))
    with pytest.raises(OSError, match='publication failed'):
        testee.save_as_wav_file(conversion.source, output, policy)
    if policy == OverwriteMode.ALWAYS:
        assert output.read_bytes() == b'previous good audio'
    else:
        assert not output.exists()
    assert all(not stage.exists() for stage in conversion.stages)


def test_save_as_wav_file_exclusive_creation_collision_never_cleans_unowned_file(conversion, mocker, tmp_path):
    """An exclusive-create collision preserves the other writer's stage and skips ffmpeg."""
    mocker.patch.object(testee, 'uuid4', return_value=SimpleNamespace(hex='collision'))
    other_stage = tmp_path / '.wav-collision.wav'
    other_stage.write_bytes(b'another writer')
    with pytest.raises(FileExistsError):
        testee.save_as_wav_file(conversion.source, tmp_path / 'output.wav')
    assert other_stage.is_file()
    assert other_stage.read_bytes() == b'another writer'
    conversion.input.assert_not_called()


def test_save_as_wav_file_stage_close_failure_cleans_only_owned_artifacts(conversion, mocker, tmp_path):
    """Owned creation followed by close failure removes only that stage before conversion."""
    other_stage = tmp_path / '.wav-unrelated.wav'
    other_stage.write_bytes(b'another writer')
    original_open = Path.open

    def open_stage(path, *args, **kwargs):
        """Close the actual owned stream before injecting its close error."""
        stream = original_open(path, *args, **kwargs)
        if args == ('xb',):
            wrapper = mocker.MagicMock()

            def close():
                """Prevent descriptor leaks while reproducing a close failure."""
                stream.close()
                raise OSError('close failed')

            wrapper.close.side_effect = close
            return wrapper
        return stream

    mocker.patch.object(testee.Path, 'open', open_stage)
    with pytest.raises(OSError, match='close failed'):
        testee.save_as_wav_file(conversion.source, tmp_path / 'output.wav')
    assert list(tmp_path.glob('.wav-*')) == [other_stage]
    assert other_stage.read_bytes() == b'another writer'
    conversion.input.assert_not_called()


def test_save_as_wav_file_real_ffmpeg_publishes_mono_pcm16_at_16khz(tmp_path):
    """Synthetic local conversion verifies ffmpeg child completion and actual WAV encoding."""
    source = tmp_path / 'input.wav'
    with wave.open(str(source), 'wb') as writer:
        writer.setnchannels(2)
        writer.setsampwidth(2)
        writer.setframerate(8000)
        writer.writeframes(b'\x00\x00\x01\x00' * 800)
    output = tmp_path / 'output.wav'
    assert testee.save_as_wav_file(source, output) == output
    with wave.open(str(output), 'rb') as reader:
        assert (reader.getnchannels(), reader.getsampwidth(), reader.getframerate(), reader.getnframes()) == (1, 2, 16000, 1600)
        assert len(reader.readframes(1600)) == 3200
    assert not list(tmp_path.glob('.wav-*'))
