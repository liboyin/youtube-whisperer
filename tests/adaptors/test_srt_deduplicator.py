import os
import subprocess
import sys
from pathlib import Path
from textwrap import dedent
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from pathlib_extensions import OverwriteMode

import youtube_whisperer.adaptors.srt_deduplicator as testee


@pytest.fixture(scope="module")
def temp_srt_file(tmp_path_factory):
    """Yield one fixture-owned subtitle file and remove it on teardown."""
    file_path = tmp_path_factory.mktemp("temp") / "test1.srt"
    file_path.write_text(dedent("""\
        1
        00:00:01,000 --> 00:00:02,000
        First line.

        2
        00:00:02,000 --> 00:00:03,000
        Second line.

        3
        00:00:03,000 --> 00:00:04,000
        Second line.
        """))
    yield file_path
    file_path.unlink()


def test_srtblock_from_lines_parses_timing_and_content():
    """Test that from_lines parses the timing line and keeps the remaining content lines."""
    block = testee.SrtBlock.from_lines(["1", "00:00:01,000 --> 00:00:02,000", "First", "line"])

    assert block.start_time == "00:00:01,000"
    assert block.end_time == "00:00:02,000"
    assert block.content == ["First", "line"]


def test_srtblock_from_lines_raises_value_error_on_malformed_block():
    """Test that a too-short block from a downloaded SRT raises a clean ValueError, not an assert."""
    with pytest.raises(ValueError, match="Malformed SRT block"):
        testee.SrtBlock.from_lines(["1", "00:00:01,000 --> 00:00:02,000"])


def test_srtblock_to_lines():
    """Test that an SrtBlock renders to numbered SRT lines with a trailing blank."""
    block = testee.SrtBlock(start_time="00:00:01,000", end_time="00:00:02,000", content=["Line."])
    expected = ["1", "00:00:01,000 --> 00:00:02,000", "Line.", ""]
    assert block.to_lines(1) == expected


def test_yield_srt_blocks_from_lines():
    """Test that blank-line-separated SRT lines are parsed into blocks."""
    input_lines = [
        "1", "00:00:01,000 --> 00:00:02,000", "First line.", "",
        "2", "00:00:02,000 --> 00:00:03,000", "Second line.", "",
    ]
    blocks = list(testee.yield_srt_blocks_from_lines(input_lines))
    assert len(blocks) == 2
    assert blocks[0].start_time == "00:00:01,000"
    assert blocks[0].end_time == "00:00:02,000"
    assert blocks[0].content == ["First line."]
    assert blocks[1].content == ["Second line."]


def test_yield_deduplicated_srt_blocks_duplicate_on_head():
    """Test that a leading duplicate pair is merged by extending the end time."""
    input_blocks = [
        testee.SrtBlock(start_time="00:00:01,000", end_time="00:00:02,000", content=["First line."]),
        testee.SrtBlock(start_time="00:00:01,000", end_time="00:00:02,000", content=["First line."]),
        testee.SrtBlock(start_time="00:00:02,000", end_time="00:00:03,000", content=["Second line."]),
    ]
    deduplicated = list(testee.yield_deduplicated_srt_blocks(input_blocks))
    assert len(deduplicated) == 2  # Should merge the last two blocks
    assert deduplicated[1].end_time == "00:00:03,000"


def test_yield_deduplicated_srt_blocks_duplicate_on_tail():
    """Test that a trailing duplicate pair is merged by extending the end time."""
    input_blocks = [
        testee.SrtBlock(start_time="00:00:01,000", end_time="00:00:02,000", content=["First line."]),
        testee.SrtBlock(start_time="00:00:02,000", end_time="00:00:03,000", content=["Second line."]),
        testee.SrtBlock(start_time="00:00:03,000", end_time="00:00:04,000", content=["Second line."]),
    ]
    deduplicated = list(testee.yield_deduplicated_srt_blocks(input_blocks))
    assert len(deduplicated) == 2  # Should merge the last two blocks
    assert deduplicated[1].end_time == "00:00:04,000"


def test_yield_lines_from_srt_blocks():
    """Test that blocks are renumbered sequentially when rendered back to lines."""
    blocks = [
        testee.SrtBlock(start_time="00:00:01,000", end_time="00:00:02,000", content=["First line."]),
        testee.SrtBlock(start_time="00:00:02,000", end_time="00:00:03,000", content=["Second line."]),
    ]
    expected = [
        "1",
        "00:00:01,000 --> 00:00:02,000",
        "First line.",
        "",
        "2",
        "00:00:02,000 --> 00:00:03,000",
        "Second line.",
        "",
    ]
    assert list(testee.yield_lines_from_srt_blocks(blocks)) == expected


def test_convert_srt_blocks_to_str():
    """Test that blocks are joined into a single SRT string."""
    blocks = [
        testee.SrtBlock(start_time="00:00:01,000", end_time="00:00:02,000", content=["First line."]),
        testee.SrtBlock(start_time="00:00:02,000", end_time="00:00:03,000", content=["Second line."]),
    ]
    expected = "1\n00:00:01,000 --> 00:00:02,000\nFirst line.\n\n2\n00:00:02,000 --> 00:00:03,000\nSecond line.\n"
    assert testee.convert_srt_blocks_to_str(blocks) == expected


@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize("failure", [OSError, KeyboardInterrupt])
def test_publish_srt_text_preserves_final_after_partial_write_and_retry(tmp_path, existing, failure):
    """Partial staged writes never replace a valid output or prevent a complete retry."""
    output = tmp_path / "output.srt"
    if existing:
        output.write_text("original")
    original_open = Path.open

    class FailingWriter:
        """Inject a failure after real staged bytes have reached the file."""

        def __init__(self, path):
            """Open only the test-owned staging path for exclusive creation."""
            self.stream = original_open(path, 'x')

        def __enter__(self):
            """Return the injected writer while retaining ownership of its real stream."""
            return self

        def write(self, text):
            """Flush a real prefix before raising the requested injected failure."""
            self.stream.write(text[:3])
            self.stream.flush()
            assert output.read_text() == "original" if existing else not output.exists()
            raise failure("injected write failure")

        def __exit__(self, *args):
            """Close the owned stream even when the injected write fails."""
            self.stream.close()

    def failing_open(path, mode='r', *args, **kwargs):
        """Inject failures only for exclusive staging writes, keeping owned reads real."""
        return FailingWriter(path) if mode == 'x' else original_open(path, mode, *args, **kwargs)

    with patch.object(testee.Path, 'open', failing_open), pytest.raises(failure, match="injected write failure"):
        testee.publish_srt_text(output, "complete\n字幕\n\n")
    assert output.read_text() == "original" if existing else not output.exists()
    assert list(tmp_path.iterdir()) == ([output] if existing else [])
    testee.publish_srt_text(output, "complete\n字幕\n\n")
    assert output.read_text() == "complete\n字幕\n\n"
    assert list(tmp_path.iterdir()) == [output]


def test_publish_srt_text_exclusive_creation_does_not_remove_an_unowned_collision(tmp_path):
    """A colliding stage name fails safely without removing another writer's file."""
    output = tmp_path / "output.srt"
    output.write_text("original")
    collision = tmp_path / ".srt-collision.tmp"
    collision.write_text("other writer")
    with patch.object(testee, 'uuid4', return_value=SimpleNamespace(hex='collision')), pytest.raises(FileExistsError):
        testee.publish_srt_text(output, "candidate")
    assert output.read_text() == "original"
    assert collision.exists()
    assert collision.read_text() == "other writer"
    assert set(tmp_path.iterdir()) == {output, collision}


@pytest.mark.parametrize("failure", [OSError, KeyboardInterrupt])
def test_publish_srt_text_preserves_final_when_stage_close_fails(tmp_path, failure):
    """Failure while closing staged output prevents publication and releases the owned file."""
    output = tmp_path / "output.srt"
    output.write_text("original")
    original_open = Path.open

    class FailingClose:
        """Own a real stage and raise after closing it to prevent publication."""

        def __init__(self, path):
            """Open only the test-owned staging path for exclusive creation."""
            self.stream = original_open(path, 'x')

        def __enter__(self):
            """Return the real stream to permit an otherwise complete staged write."""
            return self.stream

        def __exit__(self, *args):
            """Close the owned stream even when the injected write fails."""
            self.stream.close()
            assert output.read_text() == "original"
            assert Path(self.stream.name).read_text() == "complete"
            raise failure("injected close failure")

    def failing_open(path, mode='r', *args, **kwargs):
        """Inject failures only for exclusive staging writes, keeping owned reads real."""
        return FailingClose(path) if mode == 'x' else original_open(path, mode, *args, **kwargs)

    with patch.object(testee.Path, 'open', failing_open), pytest.raises(failure, match="injected close failure"):
        testee.publish_srt_text(output, "complete")
    assert output.read_text() == "original"
    assert list(tmp_path.iterdir()) == [output]
    testee.publish_srt_text(output, "complete")
    assert output.read_text() == "complete"
    assert list(tmp_path.iterdir()) == [output]


@pytest.mark.parametrize("existing", [False, True])
def test_publish_srt_text_preserves_final_and_cleans_stage_on_replace_failure(tmp_path, existing):
    """A failed final rename preserves existing output and removes only the owned stage."""
    output = tmp_path / "output.srt"
    unrelated = tmp_path / "unrelated.tmp"
    unrelated.write_text("unrelated")
    if existing:
        output.write_text("original")
    with patch.object(testee.Path, 'replace', side_effect=OSError("injected replace failure")), pytest.raises(OSError, match="injected replace failure"):
        testee.publish_srt_text(output, "complete")
    assert output.read_text() == "original" if existing else not output.exists()
    assert set(tmp_path.iterdir()) == ({output, unrelated} if existing else {unrelated})
    testee.publish_srt_text(output, "complete")
    assert output.read_text() == "complete"
    assert unrelated.read_text() == "unrelated"


@pytest.mark.parametrize("existing", [False, True])
def test_publish_srt_text_process_exit_before_publication_leaves_retry_possible(tmp_path, existing):
    """Abrupt process exit after staged bytes leaves the final path untouched and retryable."""
    output = tmp_path / "output.srt"
    if existing:
        output.write_text("original")
    script = '''
import os
from pathlib import Path
from unittest.mock import patch
import youtube_whisperer.adaptors.srt_deduplicator as testee
assert Path(testee.__file__).is_relative_to(Path(os.environ["PYTHONPATH"]))
original_open = Path.open
class InterruptedWriter:
    """Own a staged stream until the child exits without running cleanup."""
    def __init__(self, path):
        """Exclusively create a child-owned staging file."""
        self.stream = original_open(path, 'x')
    def __enter__(self):
        """Supply the child-owned writer."""
        return self
    def write(self, text):
        """Flush staged bytes and interrupt the process without Python cleanup."""
        self.stream.write(text[:3])
        self.stream.flush()
        os._exit(73)
    def __exit__(self, *args):
        """Close the stream if control returns normally."""
        self.stream.close()
with patch.object(testee.Path, 'open', lambda path, mode='r', **kwargs: InterruptedWriter(path) if mode == 'x' else original_open(path, mode, **kwargs)):
    testee.publish_srt_text(Path('output.srt'), 'complete')
'''
    source_root = Path(testee.__file__).parents[2]
    result = subprocess.run([sys.executable, '-c', script], cwd=tmp_path, env={'PYTHONPATH': str(source_root)}, capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode == 73, result.stderr
    assert output.read_text() == "original" if existing else not output.exists()
    stages = set(tmp_path.iterdir()) - {output}
    assert len(stages) == 1
    assert next(iter(stages)).read_text() == "com"
    testee.publish_srt_text(output, "complete")
    assert output.read_text() == "complete"
    for stage in stages:
        stage.unlink()
    assert list(tmp_path.iterdir()) == [output]


def test_publish_srt_text_preserves_existing_mode_and_symlink_target(tmp_path):
    """Replacing a symlink destination keeps the link and the target's permission bits."""
    target = tmp_path / "target.srt"
    target.write_text("original")
    target.chmod(0o640)
    link = tmp_path / "output.srt"
    link.symlink_to(target.name)
    testee.publish_srt_text(link, "complete")
    assert link.is_symlink()
    assert target.read_text() == "complete"
    assert target.stat().st_mode & 0o777 == 0o640
    assert set(tmp_path.iterdir()) == {target, link}


def test_publish_srt_text_preserves_mode_bits_and_leaves_hardlinked_alias_unchanged(tmp_path):
    """Atomic replacement preserves all mode bits while hardlinked aliases retain old text."""
    output = tmp_path / "output.srt"
    output.write_text("original")
    output.chmod(0o7640)
    alias = tmp_path / "alias.srt"
    os.link(output, alias)
    testee.publish_srt_text(output, "complete")
    assert output.read_text() == "complete"
    assert alias.read_text() == "original"
    assert output.stat().st_mode & 0o7777 == 0o7640
    assert set(tmp_path.iterdir()) == {output, alias}


def test_publish_srt_text_preserves_exact_text_without_new_output_restrictions(tmp_path):
    """Empty text, legacy content, Unicode, and CRLF remain valid publication inputs."""
    output = tmp_path / "nested" / "output.srt"
    for text in ("", "legacy non-SRT text", "字幕\r\n\r\n"):
        testee.publish_srt_text(output, text)
        assert output.is_file()
        assert output.read_bytes() == text.encode()
        assert list(output.parent.iterdir()) == [output]


def test_publish_srt_text_new_file_mode_matches_ordinary_creation(tmp_path):
    """New SRT permissions follow ordinary text-file creation under the inherited umask."""
    reference = tmp_path / "reference.txt"
    reference.write_text("reference")
    output = tmp_path / "output.srt"
    with patch.object(testee.os, "umask", side_effect=AssertionError("global umask accessed")):
        testee.publish_srt_text(output, "complete")
    assert output.stat().st_mode & 0o777 == reference.stat().st_mode & 0o777


@pytest.mark.parametrize("overwrite", [OverwriteMode.NEVER, OverwriteMode.RENAME])
def test_publish_srt_text_never_preserves_competing_output_at_publication(tmp_path, overwrite):
    """NEVER cannot replace a completed competing output that appears while staging."""
    output = tmp_path / "output.srt"
    original_link = os.link

    def competing_link(source, destination):
        """Create a competing completed file immediately before no-clobber publication."""
        output.write_text("competing")
        return original_link(source, destination)

    collision = None
    with patch.object(testee.os, 'link', competing_link):
        try:
            testee.publish_srt_text(output, "candidate", overwrite=overwrite)
        except FileExistsError as error:
            collision = error
    assert collision is None, "A completed competing file must be accepted"
    assert output.read_text() == "competing"
    assert list(tmp_path.iterdir()) == [output]


@pytest.mark.parametrize("overwrite", [OverwriteMode.NEVER, OverwriteMode.RENAME])
def test_publish_srt_text_no_clobber_accepts_late_symlink_to_completed_file(tmp_path, overwrite):
    """A late symlink to a completed file is preserved and accepted as competing output."""
    completed = tmp_path / "completed.srt"
    completed.write_text("competing")
    output = tmp_path / "output.srt"
    original_link = os.link

    def competing_link(source, destination):
        """Create a valid symlink at the final path immediately before the real link."""
        output.symlink_to(completed.name)
        return original_link(source, destination)

    collision = None
    with patch.object(testee.os, 'link', competing_link):
        try:
            testee.publish_srt_text(output, "candidate", overwrite=overwrite)
        except FileExistsError as error:
            collision = error
    assert collision is None, "A symlink to a completed competing file must be accepted"
    assert output.is_symlink()
    assert output.readlink() == Path(completed.name)
    assert output.read_text() == completed.read_text() == "competing"
    assert set(tmp_path.iterdir()) == {completed, output}


@pytest.mark.parametrize("overwrite", [OverwriteMode.NEVER, OverwriteMode.RENAME])
def test_publish_srt_text_no_clobber_rejects_late_directory_and_allows_retry(tmp_path, overwrite):
    """A late directory propagates the collision and cleans the stage without claiming completion."""
    output = tmp_path / "output.srt"
    original_link = os.link

    def competing_link(source, destination):
        """Create a directory at the final path immediately before the real link."""
        output.mkdir()
        return original_link(source, destination)

    with patch.object(testee.os, 'link', competing_link), pytest.raises(FileExistsError):
        testee.publish_srt_text(output, "candidate", overwrite=overwrite)
    assert output.is_dir()
    assert list(output.iterdir()) == []
    assert list(tmp_path.iterdir()) == [output]
    output.rmdir()
    testee.publish_srt_text(output, "complete", overwrite=overwrite)
    assert output.read_text() == "complete"
    assert list(tmp_path.iterdir()) == [output]


@pytest.mark.parametrize("overwrite", [OverwriteMode.NEVER, OverwriteMode.RENAME])
def test_publish_srt_text_no_clobber_rejects_late_dangling_symlink_and_allows_retry(tmp_path, overwrite):
    """A late dangling symlink propagates the collision and remains untouched after stage cleanup."""
    output = tmp_path / "output.srt"
    missing = tmp_path / "missing.srt"
    original_link = os.link

    def competing_link(source, destination):
        """Create a dangling symlink at the final path immediately before the real link."""
        output.symlink_to(missing.name)
        return original_link(source, destination)

    with patch.object(testee.os, 'link', competing_link), pytest.raises(FileExistsError):
        testee.publish_srt_text(output, "candidate", overwrite=overwrite)
    assert output.is_symlink()
    assert output.readlink() == Path(missing.name)
    assert not output.is_file()
    assert not missing.exists()
    assert list(tmp_path.iterdir()) == [output]
    output.unlink()
    testee.publish_srt_text(output, "complete", overwrite=overwrite)
    assert output.read_text() == "complete"
    assert list(tmp_path.iterdir()) == [output]


@pytest.mark.parametrize("overwrite", [OverwriteMode.NEVER, OverwriteMode.RENAME])
def test_publish_srt_text_no_clobber_publishes_complete_new_output(tmp_path, overwrite):
    """No-clobber policies permit a complete new final file when the destination stays absent."""
    output = tmp_path / "output.srt"
    testee.publish_srt_text(output, "complete\n\n", overwrite=overwrite)
    assert output.is_file()
    assert output.read_text() == "complete\n\n"
    assert list(tmp_path.iterdir()) == [output]


@pytest.mark.parametrize("overwrite", [OverwriteMode.NEVER, OverwriteMode.RENAME])
def test_publish_srt_text_no_clobber_preserves_existing_output_and_symlink(tmp_path, overwrite):
    """No-clobber publication preserves an existing target reached through a symlink."""
    target = tmp_path / "target.srt"
    target.write_text("original")
    output = tmp_path / "output.srt"
    output.symlink_to(target.name)
    testee.publish_srt_text(output, "candidate", overwrite=overwrite)
    assert output.is_symlink()
    assert target.read_text() == "original"
    assert set(tmp_path.iterdir()) == {target, output}


@pytest.mark.parametrize("overwrite", [OverwriteMode.NEVER, OverwriteMode.RENAME])
def test_publish_srt_text_no_clobber_preserves_competitor_created_after_stage_close(tmp_path, overwrite):
    """A real competitor created after closing the stage wins without check-then-replace races."""
    output = tmp_path / "output.srt"
    original_open = Path.open

    class CompetingClose:
        """Close an owned real stage before publishing a competing final file."""

        def __init__(self, path):
            """Exclusively create one test-owned stage."""
            self.stream = original_open(path, 'x')

        def __enter__(self):
            """Supply the real writer for complete stage contents."""
            return self.stream

        def __exit__(self, *args):
            """Close the stage and create final output at the publication boundary."""
            self.stream.close()
            output.write_text("competing")

    def competing_open(path, mode='r', *args, **kwargs):
        """Wrap only exclusive stage creation and keep all test-owned ordinary I/O real."""
        return CompetingClose(path) if mode == 'x' else original_open(path, mode, *args, **kwargs)

    with patch.object(testee.Path, 'open', competing_open):
        testee.publish_srt_text(output, "candidate", overwrite=overwrite)
    assert output.read_text() == "competing"
    assert list(tmp_path.iterdir()) == [output]


def test_publish_srt_text_link_failure_cleans_stage_and_allows_retry(tmp_path):
    """Unsupported no-clobber publication propagates without creating a completion marker."""
    output = tmp_path / "output.srt"
    with patch.object(testee.os, 'link', side_effect=OSError("unsupported link")), pytest.raises(OSError, match="unsupported link"):
        testee.publish_srt_text(output, "candidate", overwrite=OverwriteMode.NEVER)
    assert list(tmp_path.iterdir()) == []
    testee.publish_srt_text(output, "complete", overwrite=OverwriteMode.NEVER)
    assert output.read_text() == "complete"
    assert list(tmp_path.iterdir()) == [output]


def test_save_segments_as_srt_writes_blocks(tmp_path):
    """Writes a non-deduplicated SRT for the supplied blocks."""
    blocks = [
        testee.SrtBlock("00:00:00,000", "00:00:01,240", ["Segment"]),
        testee.SrtBlock("00:00:01,240", "00:00:04,240", ["to"]),
        testee.SrtBlock("00:00:04,240", "00:00:06,240", ["SRT"]),
    ]
    output_file_path = tmp_path / "output.srt"
    testee.save_segments_as_srt(iter(blocks), output_file_path, deduplicate=False, overwrite=OverwriteMode.ALWAYS)
    expected = "1\n00:00:00,000 --> 00:00:01,240\nSegment\n\n2\n00:00:01,240 --> 00:00:04,240\nto\n\n3\n00:00:04,240 --> 00:00:06,240\nSRT\n"
    assert output_file_path.is_file()
    assert output_file_path.read_text() == expected


def test_save_segments_as_srt_deduplicates_consecutive(tmp_path):
    """Merges consecutive blocks with identical content when deduplicate is True."""
    blocks = [
        testee.SrtBlock("00:00:00,000", "00:00:01,000", ["Same"]),
        testee.SrtBlock("00:00:01,000", "00:00:02,000", ["Same"]),
    ]
    output_file_path = tmp_path / "output.srt"
    testee.save_segments_as_srt(iter(blocks), output_file_path, deduplicate=True, overwrite=OverwriteMode.ALWAYS)
    assert output_file_path.read_text().count("Same") == 1


def test_save_segments_as_srt_skips_existing_when_overwrite_never(tmp_path):
    """Leaves an existing SRT untouched when overwrite mode is NEVER."""
    output_file_path = tmp_path / "output.srt"
    output_file_path.write_text("original content")
    blocks = [testee.SrtBlock("00:00:00,000", "00:00:01,000", ["new"])]
    testee.save_segments_as_srt(iter(blocks), output_file_path, overwrite=OverwriteMode.NEVER)
    assert output_file_path.read_text() == "original content"


@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize("overwrite", [OverwriteMode.NEVER, OverwriteMode.RENAME])
def test_save_segments_as_srt_never_preserves_competitor_after_lazy_materialization(tmp_path, existing, overwrite):
    """Lazy serialization respects NEVER and is skipped entirely for an existing output."""
    output = tmp_path / "output.srt"
    if existing:
        output.write_text("original")
    consumed = []

    def blocks():
        """Record consumption and create competing output during lazy serialization."""
        consumed.append(True)
        output.write_text("competing")
        yield testee.SrtBlock("00:00:00,000", "00:00:01,000", ["candidate"])

    testee.save_segments_as_srt(blocks(), output, overwrite=overwrite)
    assert output.read_text() == ("original" if existing else "competing")
    assert consumed == ([] if existing else [True])
    assert list(tmp_path.iterdir()) == [output]


@pytest.mark.parametrize("existing", [False, True])
def test_save_segments_as_srt_consumes_all_lazy_blocks_before_opening_stage(tmp_path, existing):
    """A late generator failure finishes before any staged write and preserves final output."""
    output = tmp_path / "output.srt"
    if existing:
        output.write_text("original")
    consumed = []

    def blocks():
        """Yield two real blocks then fail to prove complete lazy materialization."""
        for content in ("first", "second"):
            consumed.append(content)
            yield testee.SrtBlock("00:00:00,000", "00:00:01,000", [content])
        raise ValueError("late generator failure")

    with patch.object(testee.Path, 'open', side_effect=AssertionError("premature write")) as opened, pytest.raises(ValueError, match="late generator failure"):
        testee.save_segments_as_srt(blocks(), output, overwrite=OverwriteMode.ALWAYS)
    opened.assert_not_called()
    assert consumed == ["first", "second"]
    assert output.read_text() == "original" if existing else not output.exists()
    assert list(tmp_path.iterdir()) == ([output] if existing else [])


@pytest.mark.parametrize("approved", [False, True])
def test_save_segments_as_srt_prompt_is_decided_once_before_lazy_work(tmp_path, approved):
    """One existing-output prompt authorizes publication or skips lazy serialization entirely."""
    output = tmp_path / "output.srt"
    output.write_text("original")
    consumed = []

    def blocks():
        """Record lazy work only when preflight allows replacing existing output."""
        consumed.append(True)
        yield testee.SrtBlock("00:00:00,000", "00:00:01,000", ["candidate"])

    with patch.object(testee, 'overwrite_existing_path', return_value=approved) as preflight:
        testee.save_segments_as_srt(blocks(), output, overwrite=OverwriteMode.PROMPT)
    preflight.assert_called_once_with(output, OverwriteMode.PROMPT)
    assert consumed == ([True] if approved else [])
    assert output.read_text() == ("1\n00:00:00,000 --> 00:00:01,000\ncandidate\n" if approved else "original")


def test_deduplicate_srt_file(temp_srt_file: Path):
    """Test that duplicate blocks in a file are merged and written back in place."""
    assert testee.deduplicate_srt_file(temp_srt_file, overwrite=OverwriteMode.ALWAYS) is temp_srt_file
    expected = dedent("""\
        1
        00:00:01,000 --> 00:00:02,000
        First line.

        2
        00:00:02,000 --> 00:00:04,000
        Second line.
        """)
    assert temp_srt_file.read_text().strip() == expected.strip()


def test_deduplicate_srt_file_returns_early_when_overwrite_never(tmp_path):
    """Test that an existing file is left untouched when overwrite mode is NEVER."""
    srt_file = tmp_path / "test.srt"
    srt_file.write_text("1\n00:00:01,000 --> 00:00:02,000\nOriginal\n\n")
    original_content = srt_file.read_text()
    result = testee.deduplicate_srt_file(srt_file, overwrite=OverwriteMode.NEVER)
    assert result is srt_file
    assert srt_file.read_text() == original_content


@pytest.mark.parametrize("failure", [OSError, KeyboardInterrupt])
def test_deduplicate_srt_file_in_place_preserves_input_on_publication_failure_and_retry(tmp_path, failure):
    """In-place dedup reads first and preserves the original file when publication fails."""
    output = tmp_path / "input.srt"
    original = "1\n00:00:00,000 --> 00:00:01,000\nSame\n\n2\n00:00:03,000 --> 00:00:04,000\nSame\n"
    output.write_text(original)
    with patch.object(testee.Path, 'replace', side_effect=failure("injected publication failure")), pytest.raises(failure, match="injected publication failure"):
        testee.deduplicate_srt_file(output, overwrite=OverwriteMode.ALWAYS)
    assert output.read_text() == original
    assert list(tmp_path.iterdir()) == [output]
    assert testee.deduplicate_srt_file(output, overwrite=OverwriteMode.ALWAYS) == output
    assert output.read_text() == "1\n00:00:00,000 --> 00:00:04,000\nSame\n"
    assert list(tmp_path.iterdir()) == [output]


@pytest.mark.parametrize("overwrite", [OverwriteMode.NEVER, OverwriteMode.RENAME])
def test_deduplicate_srt_file_no_clobber_preserves_competitor_created_after_input_read(tmp_path, overwrite):
    """Dedup forwards no-clobber policy when completed competing output appears after input closes."""
    input_path = tmp_path / "input.srt"
    original = "1\n00:00:00,000 --> 00:00:01,000\nSame\n\n2\n00:00:03,000 --> 00:00:04,000\nSame\n"
    input_path.write_text(original)
    output = tmp_path / "output.srt"
    original_open = Path.open

    class CompetingRead:
        """Own the real input stream and create output only after the read completes."""

        def __init__(self):
            """Open only this test's input file."""
            self.stream = original_open(input_path)

        def __enter__(self):
            """Provide the real input stream for complete lazy parsing."""
            return self.stream

        def __exit__(self, *args):
            """Close the input and publish a competitor before staging can begin."""
            self.stream.close()
            output.write_text("competing")

    def competing_open(path, mode='r', *args, **kwargs):
        """Intercept only the owned input read and keep all publication I/O real."""
        return CompetingRead() if path == input_path and mode == 'r' else original_open(path, mode, *args, **kwargs)

    with patch.object(testee.Path, 'open', competing_open):
        assert testee.deduplicate_srt_file(input_path, output, overwrite=overwrite) == output
    assert input_path.read_text() == original
    assert output.read_text() == "competing"
    assert set(tmp_path.iterdir()) == {input_path, output}
