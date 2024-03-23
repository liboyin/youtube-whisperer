import pytest
from youtube_whisperer.deduplicate_srt import SrtBlock, yield_stripped_lines, yield_srt_blocks, deduplicate_srt_blocks
from pathlib import Path
from textwrap import dedent


@pytest.fixture
def sample_srt_blocks():
    return [
        SrtBlock(start_time="00:00:01,000", end_time="00:00:02,000", content=["First line."]),
        SrtBlock(start_time="00:00:02,000", end_time="00:00:03,000", content=["Second line."]),
        SrtBlock(start_time="00:00:03,000", end_time="00:00:04,000", content=["Second line."])  # Duplicate for testing
    ]


def test_yield_stripped_lines():
    input_lines = ["  line1\n", "line2  ", "\n", "line3"]
    expected = ["line1", "line2", "", "line3"]
    assert list(yield_stripped_lines(input_lines)) == expected


def test_yield_srt_blocks():
    input_lines = [
        "1", "00:00:01,000 --> 00:00:02,000", "First line.", "",
        "2", "00:00:02,000 --> 00:00:03,000", "Second line.", ""
    ]
    blocks = list(yield_srt_blocks(input_lines))
    assert len(blocks) == 2
    assert blocks[0].start_time == "00:00:01,000"
    assert blocks[0].end_time == "00:00:02,000"
    assert blocks[0].content == ["First line."]
    assert blocks[1].content == ["Second line."]


def test_deduplicate_srt_blocks(sample_srt_blocks):
    deduplicated = deduplicate_srt_blocks(sample_srt_blocks)
    assert len(deduplicated) == 2  # Should merge the last two blocks
    assert deduplicated[1].end_time == "00:00:04,000"


def test_srtblock_to_lines():
    block = SrtBlock(start_time="00:00:01,000", end_time="00:00:02,000", content=["Line."])
    expected = ["1", "00:00:01,000 --> 00:00:02,000", "Line.", "\n"]
    assert block.to_lines(1) == expected


def test_main_function(tmp_path: Path):
    test_file = tmp_path / "test.srt"
    test_file.write_text(dedent("""\
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
    
    # Assuming main function is adjusted to accept Path object and return modified data as string for testing
    from youtube_whisperer.deduplicate_srt import deduplicate_single
    deduplicate_single(test_file)  # This needs to be adapted based on how main function is structured for testing
    
    with test_file.open("r") as f:
        content = f.read()
    
    expected_content = dedent("""\
        1
        00:00:01,000 --> 00:00:02,000
        First line.

        2
        00:00:02,000 --> 00:00:04,000
        Second line.
        """)
    assert content.strip() == expected_content.strip()
