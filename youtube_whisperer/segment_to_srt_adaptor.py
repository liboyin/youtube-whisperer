import argparse
from pathlib import Path
from typing import Iterable, Generator

from faster_whisper.transcribe import Segment
from faster_whisper.utils import format_timestamp

from youtube_whisperer.pathlib_extensions import prepare_input_file, prepare_output_file
from youtube_whisperer.srt_deduplicator import SrtBlock, yield_lines_from_srt_blocks, yield_deduplicated_srt_blocks


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


def convert_segments_file_to_srt(input_file_path: Path, output_file_path: Path | None = None, deduplicate: bool = False) -> Path:
    """
    Converts a segments file to an SRT file.

    Args:
        input_file_path (Path): The path to the input segments file.
        output_file_path (Path, optional): The path to the output SRT file. If not provided, a file with the same name as the input file and the .srt extension will be created. Defaults to None.
        deduplicate (bool, optional): Whether to deduplicate the segments. Defaults to False.

    Returns:
        Path: The path to the output SRT file.
    """
    prepare_input_file(input_file_path)
    output_file_path = prepare_output_file(output_file_path or input_file_path.with_suffix('.srt'))
    blocks = yield_srt_blocks_from_segments(load_segments_from_file(input_file_path))
    if deduplicate:
        blocks = yield_deduplicated_srt_blocks(blocks)
    output_file_path.write_text('\n'.join(yield_lines_from_srt_blocks(blocks)))
    return output_file_path


def main() -> None:
    """
    CLI entry point to convert a Segment file to an SRT file.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path, help="Segment file path to convert to an SRT file.")
    convert_segments_file_to_srt(parser.parse_args().path)

if __name__ == '__main__':
    main()
