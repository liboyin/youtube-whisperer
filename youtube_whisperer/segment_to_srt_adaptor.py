from pathlib import Path
from typing import Iterable, Generator

from faster_whisper.transcribe import Segment
from faster_whisper.utils import format_timestamp

from .srt_deduplicator import SrtBlock


def segment_to_srt_block(segment: Segment) -> SrtBlock:
    """
    Convert a Segment object to an SrtBlock object.
    """
    return SrtBlock(
        format_timestamp(segment.start),
        format_timestamp(segment.end),
        segment.text.strip().split('\n'),
    )


def yield_srt_blocks_from_segments(segments: Iterable[Segment]) -> Generator[SrtBlock, None, None]:
    """
    Generate SrtBlock objects from an iterable of segments.
    """
    for segment in segments:
        print(segment)
        result = segment_to_srt_block(segment)
        print(result)
        yield result


def load_segments_from_lines(lines: Iterable[str]) -> list[Segment]:
    """
    Load segments from an iterable of lines.
    """
    result = []
    for line in lines:
        if line := line.strip():
            result.append(eval(line, globals(), locals()))
    return result


def load_segments_from_file(file_path: Path) -> list[Segment]:
    """
    Load segments from a file.
    """
    return load_segments_from_lines(file_path.read_text().splitlines())

if __name__ == '__main__':
    for _ in yield_srt_blocks_from_segments(load_segments_from_file(Path.cwd() / 'segments.txt')):
        pass
