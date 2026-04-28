from pathlib import Path
from textwrap import dedent
from types import SimpleNamespace

from pathlib_extensions import OverwriteMode
import pytest

import youtube_whisperer.adaptors.srt_deduplicator as testee


@pytest.fixture(scope="module")
def temp_srt_file(tmp_path_factory):
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


def test_srtblock_to_lines():
    block = testee.SrtBlock(start_time="00:00:01,000", end_time="00:00:02,000", content=["Line."])
    expected = ["1", "00:00:01,000 --> 00:00:02,000", "Line.", ""]
    assert block.to_lines(1) == expected


def test_yield_srt_blocks_from_lines():
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
    input_blocks = [
        testee.SrtBlock(start_time="00:00:01,000", end_time="00:00:02,000", content=["First line."]),
        testee.SrtBlock(start_time="00:00:01,000", end_time="00:00:02,000", content=["First line."]),
        testee.SrtBlock(start_time="00:00:02,000", end_time="00:00:03,000", content=["Second line."]),
    ]
    deduplicated = list(testee.yield_deduplicated_srt_blocks(input_blocks))
    assert len(deduplicated) == 2  # Should merge the last two blocks
    assert deduplicated[1].end_time == "00:00:03,000"


def test_yield_deduplicated_srt_blocks_duplicate_on_tail():
    input_blocks = [
        testee.SrtBlock(start_time="00:00:01,000", end_time="00:00:02,000", content=["First line."]),
        testee.SrtBlock(start_time="00:00:02,000", end_time="00:00:03,000", content=["Second line."]),
        testee.SrtBlock(start_time="00:00:03,000", end_time="00:00:04,000", content=["Second line."]),
    ]
    deduplicated = list(testee.yield_deduplicated_srt_blocks(input_blocks))
    assert len(deduplicated) == 2  # Should merge the last two blocks
    assert deduplicated[1].end_time == "00:00:04,000"


def test_yield_lines_from_srt_blocks():
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
    blocks = [
        testee.SrtBlock(start_time="00:00:01,000", end_time="00:00:02,000", content=["First line."]),
        testee.SrtBlock(start_time="00:00:02,000", end_time="00:00:03,000", content=["Second line."]),
    ]
    expected = "1\n00:00:01,000 --> 00:00:02,000\nFirst line.\n\n2\n00:00:02,000 --> 00:00:03,000\nSecond line.\n"
    assert testee.convert_srt_blocks_to_str(blocks) == expected


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


def test_deduplicate_srt_file(temp_srt_file: Path):
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
    srt_file = tmp_path / "test.srt"
    srt_file.write_text("1\n00:00:01,000 --> 00:00:02,000\nOriginal\n\n")
    original_content = srt_file.read_text()
    result = testee.deduplicate_srt_file(srt_file, overwrite=OverwriteMode.NEVER)
    assert result is srt_file
    assert srt_file.read_text() == original_content


def test_main_deduplicates_given_paths(mocker, tmp_path):
    srt_file = tmp_path / "test.srt"
    args = SimpleNamespace(paths=[srt_file], overwrite=OverwriteMode.ALWAYS)
    mocker.patch("argparse.ArgumentParser.parse_args", return_value=args)
    mock_dedup = mocker.patch.object(testee, "deduplicate_srt_file")

    testee.main()

    mock_dedup.assert_called_once_with(srt_file, overwrite=OverwriteMode.ALWAYS)
