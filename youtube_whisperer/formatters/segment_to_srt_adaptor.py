import argparse
from pathlib import Path
from typing import Iterable, Iterator

from faster_whisper.transcribe import Segment
from faster_whisper.utils import format_timestamp
from pathlib_extensions import prepare_input_file, prepare_output_file

from youtube_whisperer.formatters.segment_handler import load_segments_from_file
from youtube_whisperer.formatters.srt_deduplicator import SrtBlock, convert_srt_blocks_to_str, yield_deduplicated_srt_blocks


def segment_to_srt_block(segment: Segment) -> SrtBlock:
    """
    Convert a Segment object to an SrtBlock object.
    """
    return SrtBlock(
        format_timestamp(segment.start, always_include_hours=True, decimal_marker=','),
        format_timestamp(segment.end, always_include_hours=True, decimal_marker=','),
        segment.text.strip().split('\n'),
    )


def yield_srt_blocks_from_segments(segments: Iterable[Segment]) -> Iterator[SrtBlock]:
    """
    Yield SrtBlock objects from an iterable of Segments. Print each Segment and SrtBlock to stdout.
    """
    for segment in segments:
        print(segment)
        result = segment_to_srt_block(segment)
        print(result)
        yield result


def convert_segments_file_to_srt(input_file_path: Path, output_file_path: Path | None = None, deduplicate: bool = True) -> Path:
    """
    Converts a segments file to an SRT file.

    Args:
        input_file_path (Path): The path to the input segments file.
        output_file_path (Path, optional): The path to the output SRT file. If not provided, a file with the same name as the input file and the .srt extension will be created. Defaults to None.
        deduplicate (bool, optional): Whether to deduplicate the segments. Defaults to True.

    Returns:
        Path: The path to the output SRT file.
    """
    prepare_input_file(input_file_path)
    output_file_path = prepare_output_file(output_file_path or input_file_path.with_suffix('.srt'))
    srt_blocks_generator = yield_srt_blocks_from_segments(load_segments_from_file(input_file_path))
    if deduplicate:
        srt_blocks_generator = yield_deduplicated_srt_blocks(srt_blocks_generator)
    output_file_path.write_text(convert_srt_blocks_to_str(srt_blocks_generator))
    return output_file_path


def main() -> None:
    """
    CLI entry point to convert Segment files to SRT.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", type=Path, nargs='+', metavar='path', help="Segment file paths to convert to SRT.")
    for path in parser.parse_args().paths:
        convert_segments_file_to_srt(path)


if __name__ == '__main__':
    main()
