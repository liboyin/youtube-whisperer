from faster_whisper.transcribe import Segment
import pytest

from youtube_whisperer.segment_handler import (
    duplicate_segments_to_file,
    load_segments_from_file,
    load_segments_from_lines,
    write_segments_to_file,
)

SEGMENTS = [
    Segment(id=1, seek=2704, start=0.0, end=1.24, text='Segment', tokens=[50365, 4511], temperature=0.0, avg_logprob=-0.309651929245898, compression_ratio=1.2782608695652173, no_speech_prob=0.72765052318573, words=None),
    Segment(id=2, seek=2704, start=1.24, end=4.24, text='to', tokens=[50427, 41410], temperature=0.0, avg_logprob=-0.309651929245898, compression_ratio=1.2782608695652173, no_speech_prob=0.72765052318573, words=None),
    Segment(id=3, seek=2704, start=4.24, end=6.24, text='file', tokens=[50577, 11706], temperature=0.0, avg_logprob=-0.309651929245898, compression_ratio=1.2782608695652173, no_speech_prob=0.72765052318573, words=None),
]


def test_duplicate_segments_to_file(tmp_path):
    output_file_path = tmp_path / "output.txt"
    segments_generator = duplicate_segments_to_file(SEGMENTS, output_file_path)
    # the file should not exist at this point
    assert not output_file_path.exists()
    for i, x in enumerate(SEGMENTS):
        assert next(segments_generator) is x
        if not i:
            # the file should be created after the first flush
            assert output_file_path.is_file()
    with pytest.raises(StopIteration):
        next(segments_generator)
    assert output_file_path.read_text() == '\n'.join(map(str, SEGMENTS))
    output_file_path.unlink()


def test_write_segments_to_file(tmp_path):
    output_file_path = tmp_path / "output.txt"
    assert write_segments_to_file(SEGMENTS, output_file_path) is None
    assert output_file_path.is_file()
    assert output_file_path.read_text() == '\n'.join(map(str, SEGMENTS))
    output_file_path.unlink()


def test_load_segments_from_lines():
    segments = load_segments_from_lines(map(str, SEGMENTS))
    assert len(segments) == 3
    assert all(isinstance(x, Segment) for x in segments)
    assert segments[0].text == 'Segment'
    assert segments[1].text == 'to'
    assert segments[2].text == 'file'


def test_load_segments_from_file(tmp_path):
    file_path = tmp_path / 'segments.txt'
    file_path.write_text('\n'.join(map(str, SEGMENTS)))
    segments = load_segments_from_file(file_path)
    assert len(segments) == 3
    assert all(isinstance(x, Segment) for x in segments)
    assert segments[0].text == 'Segment'
    assert segments[1].text == 'to'
    assert segments[2].text == 'file'
