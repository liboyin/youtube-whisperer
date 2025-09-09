from faster_whisper.transcribe import Segment
from pathlib_extensions import OverwriteMode

from youtube_whisperer.formatters.srt_deduplicator import SrtBlock
from youtube_whisperer.formatters.whisper_adaptor import WhisperSegmentAdaptor

SEGMENTS = [
    Segment(id=1, seek=2704, start=0.0, end=1.24, text='Segment', tokens=[50365, 4511], temperature=0.0, avg_logprob=-0.309651929245898, compression_ratio=1.2782608695652173, no_speech_prob=0.72765052318573, words=None),
    Segment(id=2, seek=2704, start=1.24, end=4.24, text='to', tokens=[50427, 41410], temperature=0.0, avg_logprob=-0.309651929245898, compression_ratio=1.2782608695652173, no_speech_prob=0.72765052318573, words=None),
    Segment(id=3, seek=2704, start=4.24, end=6.24, text='SRT', tokens=[50577, 11706], temperature=0.0, avg_logprob=-0.309651929245898, compression_ratio=1.2782608695652173, no_speech_prob=0.72765052318573, words=None),
]


def test_from_lines():
    handler = WhisperSegmentAdaptor.from_lines(map(str, SEGMENTS))
    segments = list(handler.segment_iter)
    assert len(segments) == 3
    assert all(isinstance(x, Segment) for x in segments)
    assert segments[0].text == 'Segment'
    assert segments[1].text == 'to'
    assert segments[2].text == 'SRT'


def test_from_file(tmp_path):
    file_path = tmp_path / 'segments.seg'
    file_path.write_text('\n'.join(map(str, SEGMENTS)))
    handler = WhisperSegmentAdaptor.from_file(file_path)
    segments = list(handler.segment_iter)
    assert len(segments) == 3
    assert all(isinstance(x, Segment) for x in segments)
    assert segments[0].text == 'Segment'
    assert segments[1].text == 'to'
    assert segments[2].text == 'SRT'


def test_segment_to_srt_block():
    srt_block = WhisperSegmentAdaptor.segment_to_srt_block(SEGMENTS[0])
    assert isinstance(srt_block, SrtBlock)
    assert srt_block.start_time == '00:00:00,000'
    assert srt_block.end_time == '00:00:01,240'
    assert srt_block.content == ['Segment']


def test_yield_as_srt_blocks():
    handler = WhisperSegmentAdaptor(SEGMENTS)
    srt_blocks = list(handler.yield_as_srt_blocks())
    assert len(srt_blocks) == 3
    assert all(isinstance(x, SrtBlock) for x in srt_blocks)
    assert srt_blocks[0].content == ['Segment']
    assert srt_blocks[1].content == ['to']
    assert srt_blocks[2].content == ['SRT']


def test_save_as_srt_file(tmp_path):
    input_file_path = tmp_path / 'segments.seg'
    input_file_path.write_text('\n'.join(map(str, SEGMENTS)))
    handler = WhisperSegmentAdaptor.from_file(input_file_path)
    output_file_path = tmp_path / "output.srt"
    handler.save_as_srt_file(output_file_path, deduplicate=False, overwrite=OverwriteMode.ALWAYS)
    assert output_file_path.is_file()
    expected = "1\n00:00:00,000 --> 00:00:01,240\nSegment\n\n2\n00:00:01,240 --> 00:00:04,240\nto\n\n3\n00:00:04,240 --> 00:00:06,240\nSRT\n"
    assert output_file_path.read_text() == expected
