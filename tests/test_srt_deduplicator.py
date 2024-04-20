from youtube_whisperer.srt_deduplicator import (
    SrtBlock,
    deduplicate_multi,
    deduplicate_single,
    srt_blocks_to_str,
    yield_deduplicated_srt_blocks,
    yield_lines_from_srt_blocks,
    yield_srt_blocks,
)
from pathlib import Path
from textwrap import dedent
from unittest import mock

import pytest


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
    return file_path


def test_yield_srt_blocks():
    input_lines = [
        "1", "00:00:01,000 --> 00:00:02,000", "First line.", "",
        "2", "00:00:02,000 --> 00:00:03,000", "Second line.", "",
    ]
    blocks = list(yield_srt_blocks(input_lines))
    assert len(blocks) == 2
    assert blocks[0].start_time == "00:00:01,000"
    assert blocks[0].end_time == "00:00:02,000"
    assert blocks[0].content == ["First line."]
    assert blocks[1].content == ["Second line."]


def test_yield_deduplicated_srt_blocks_duplicate_on_head():
    input_blocks = [
        SrtBlock(start_time="00:00:01,000", end_time="00:00:02,000", content=["First line."]),
        SrtBlock(start_time="00:00:01,000", end_time="00:00:02,000", content=["First line."]),
        SrtBlock(start_time="00:00:02,000", end_time="00:00:03,000", content=["Second line."]),
    ]
    deduplicated = list(yield_deduplicated_srt_blocks(input_blocks))
    assert len(deduplicated) == 2  # Should merge the last two blocks
    assert deduplicated[1].end_time == "00:00:03,000"


def test_yield_deduplicated_srt_blocks_duplicate_on_tail():
    input_blocks = [
        SrtBlock(start_time="00:00:01,000", end_time="00:00:02,000", content=["First line."]),
        SrtBlock(start_time="00:00:02,000", end_time="00:00:03,000", content=["Second line."]),
        SrtBlock(start_time="00:00:03,000", end_time="00:00:04,000", content=["Second line."]),
    ]
    deduplicated = list(yield_deduplicated_srt_blocks(input_blocks))
    assert len(deduplicated) == 2  # Should merge the last two blocks
    assert deduplicated[1].end_time == "00:00:04,000"


def test_srtblock_to_lines():
    block = SrtBlock(start_time="00:00:01,000", end_time="00:00:02,000", content=["Line."])
    expected = ["1", "00:00:01,000 --> 00:00:02,000", "Line.", ""]
    assert block.to_lines(1) == expected


def test_yield_lines_from_srt_blocks():
    blocks = [
        SrtBlock(start_time="00:00:01,000", end_time="00:00:02,000", content=["First line."]),
        SrtBlock(start_time="00:00:02,000", end_time="00:00:03,000", content=["Second line."]),
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
    assert list(yield_lines_from_srt_blocks(blocks)) == expected


def test_srt_blocks_to_str():
    blocks = [
        SrtBlock(start_time="00:00:01,000", end_time="00:00:02,000", content=["First line."]),
        SrtBlock(start_time="00:00:02,000", end_time="00:00:03,000", content=["Second line."]),
    ]
    expected = "1\n00:00:01,000 --> 00:00:02,000\nFirst line.\n\n2\n00:00:02,000 --> 00:00:03,000\nSecond line.\n"
    assert srt_blocks_to_str(blocks) == expected


def test_deduplicate_single(temp_srt_file: Path):
    deduplicate_single(temp_srt_file)
    expected = dedent("""\
        1
        00:00:01,000 --> 00:00:02,000
        First line.

        2
        00:00:02,000 --> 00:00:04,000
        Second line.
        """)
    assert temp_srt_file.read_text().strip() == expected.strip()


def test_deduplicate_multi(temp_srt_file: Path):
    temp_dir_path = temp_srt_file.parent
    with mock.patch('youtube_whisperer.srt_deduplicator.deduplicate_single') as mock_deduplicate_single:
        deduplicate_multi(temp_dir_path, recursive=False)
    assert mock_deduplicate_single.call_count == 1
