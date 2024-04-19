import argparse
from pathlib import Path
from typing import Iterable, Generator

from faster_whisper.transcribe import Segment
from faster_whisper.utils import format_timestamp

from youtube_whisperer.pathlib_extensions import prepare_output_file
from youtube_whisperer.srt_deduplicator import SrtBlock, yield_lines_from_srt_blocks


def load_segments_from_lines(lines: Iterable[str]) -> list[Segment]:
    """
    Load Segments from an iterable of lines.
    """
    result = []
    for line in lines:
        if line := line.strip():
            result.append(eval(line, globals(), locals()))
    return result


def load_segments_from_file(file_path: Path) -> list[Segment]:
    """
    Load Segments from a file.
    """
    with file_path.open() as file_handler:
        return load_segments_from_lines(file_handler)


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
    Generate SrtBlock objects from an iterable of Segments.
    """
    for segment in segments:
        print(segment)
        result = segment_to_srt_block(segment)
        print(result)
        yield result


def segments_to_srt_file(input_file_path: Path, output_file_path: Path | None = None) -> Path:
    """
    Convert a Segment file to an SRT file.
    """
    output_file_path = output_file_path or input_file_path.with_suffix('.srt')
    blocks = yield_srt_blocks_from_segments(load_segments_from_file(input_file_path))
    prepare_output_file(output_file_path).write_text('\n'.join(yield_lines_from_srt_blocks(blocks)))
    return output_file_path


def main() -> None:
    """
    CLI entry point to convert a Segment file to an SRT file.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path, help="Segment file path to convert to an SRT file.")
    args = parser.parse_args()
    p = args.path
    if p.is_file():
        segments_to_srt_file(p)
    else:
        raise FileNotFoundError(f"{p} is not a file")

if __name__ == '__main__':
    main()
