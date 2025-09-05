import argparse
from pathlib import Path
from typing import Generator, Iterable, Iterator, Self

from faster_whisper.transcribe import Segment
from faster_whisper.utils import format_timestamp
from pathlib_extensions import OverwriteMode, overwrite_existing_path, prepare_input_file, prepare_output_file

from youtube_whisperer.formatters.srt_deduplicator import SrtBlock, convert_srt_blocks_to_str, yield_deduplicated_srt_blocks


class WhisperSegmentAdaptor:
    def __init__(self, segments: Iterable[Segment]) -> None:
        self.segment_iter = iter(segments)  # default to lazy evaluation

    @staticmethod
    def yield_segments_from_lines(lines: Iterable[str]) -> Iterator[Segment]:
        for line in lines:
            if line := line.strip():
                yield eval(line, globals(), locals())

    @staticmethod
    def segment_to_srt_block(segment: Segment) -> SrtBlock:
        """
        Converts a Segment object to an SrtBlock object.
        """
        return SrtBlock(
            format_timestamp(segment.start, always_include_hours=True, decimal_marker=','),
            format_timestamp(segment.end, always_include_hours=True, decimal_marker=','),
            segment.text.strip().split('\n'),
        )

    @classmethod
    def from_lines(cls, lines: Iterable[str]) -> Self:
        """
        Loads Segments from an iterable of lines.
        """
        return cls(list(cls.yield_segments_from_lines(lines)))  # eager evaluation
    
    @classmethod
    def from_file(cls, file_path: Path) -> Self:
        """
        Loads Segments from a file.
        """
        with file_path.open() as file_handler:
            return cls(list(cls.yield_segments_from_lines(file_handler)))  # eager evaluation

    def tee_to_file(self, file_path: Path, flush_interval_lines: int = 100, overwrite: OverwriteMode = OverwriteMode.PROMPT) -> Generator[Segment, None, None]:
        """
        Writes Segments to a file, and yield them.

        Args:
            file_path (Path): The path to the file to write to.
            flush_interval_lines (int): Flush the file every X lines. Defaults to 100.
            overwrite (OverwriteMode): Whether to overwrite existing Segment files. Defaults to `prompt`.

        Yields:
            Segments from input as-is.
        """
        if file_path.is_file() and not overwrite_existing_path(file_path, overwrite):
            return
        with prepare_output_file(file_path).open('w') as file_handler:
            for i, x in enumerate(self.segment_iter):
                # write a newline between Segments, but not after the last one
                if i:
                    file_handler.write(f'\n{x}')
                else:
                    file_handler.write(str(x))
                if (i + 1) % flush_interval_lines == 0:
                    file_handler.flush()
                yield x

    def save_to_file(self, file_path: Path, overwrite: OverwriteMode = OverwriteMode.PROMPT) -> None:
        """
        Writes Segments to a file.

        Args:
            file_path (Path): The path to the file to write to.
            overwrite (OverwriteMode): Whether to overwrite existing Segment files. Defaults to `prompt`.
        """
        if file_path.is_file() and not overwrite_existing_path(file_path, overwrite):
            return
        prepare_output_file(file_path).write_text('\n'.join(map(str, self.segment_iter)))

    def yield_srt_blocks(self) -> Iterator[SrtBlock]:
        """
        Yields SrtBlock objects from the segments.
        """
        for segment in self.segment_iter:
            print(segment)
            result = self.segment_to_srt_block(segment)
            print(result)
            yield result

    def save_as_srt_file(self, file_path: Path, deduplicate: bool = True, overwrite: OverwriteMode = OverwriteMode.PROMPT) -> None:
        """
        Converts a segments file to an SRT file.

        Args:
            file_path (Path): The path to the output SRT file.
            deduplicate (bool, optional): Whether to deduplicate the segments. Defaults to True.
            overwrite (OverwriteMode, optional): Whether to overwrite existing SRT files. Defaults to `prompt`.
        """
        if file_path.is_file() and not overwrite_existing_path(file_path, overwrite):
            return
        file_path = prepare_output_file(file_path)
        srt_blocks_generator = self.yield_srt_blocks()
        if deduplicate:
            srt_blocks_generator = yield_deduplicated_srt_blocks(srt_blocks_generator)
        file_path.write_text(convert_srt_blocks_to_str(srt_blocks_generator))


def convert_segments_file_to_srt(input_file_path: Path, output_file_path: Path | None = None, deduplicate: bool = True, overwrite: OverwriteMode = OverwriteMode.PROMPT) -> Path:
    """
    Converts a segments file to an SRT file.

    Args:
        input_file_path (Path): The path to the input segments file.
        output_file_path (Path | None, optional): The path to the output SRT file. If not provided, a file with the same name as the input file and the .srt extension will be created. Defaults to None.
        deduplicate (bool, optional): Whether to deduplicate the segments. Defaults to True.
        overwrite (OverwriteMode, optional): Whether to overwrite existing SRT files. Defaults to `prompt`.

    Returns:
        Path: The path to the output SRT file.
    """
    prepare_input_file(input_file_path)
    output_file_path = output_file_path or input_file_path.with_suffix('.srt')
    if output_file_path.is_file() and not overwrite_existing_path(output_file_path, overwrite):
        return output_file_path
    WhisperSegmentAdaptor.from_file(input_file_path).save_as_srt_file(output_file_path, deduplicate=deduplicate, overwrite=overwrite)
    return output_file_path


def main() -> None:
    """
    CLI entry point to convert Segment files to SRT.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", type=Path, nargs='+', metavar='path', help="Segment file paths to convert to SRT.")
    parser.add_argument("-o", "--overwrite", type=OverwriteMode, choices=OverwriteMode.values(), default=OverwriteMode.PROMPT, help="Whether to overwrite existing SRT files. Defaults to `prompt`.")
    args = parser.parse_args()
    overwrite = args.overwrite
    for path in args.paths:
        convert_segments_file_to_srt(path, overwrite=overwrite)


if __name__ == '__main__':
    main()