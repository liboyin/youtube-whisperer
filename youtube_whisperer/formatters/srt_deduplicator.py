import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

from pathlib_extensions import OverwriteMode, overwrite_existing_path, prepare_input_file, prepare_output_file

ARROW = '-->'


@dataclass
class SrtBlock:
    """
    Represents a subtitle block within an SRT file, including its start and end times, along with the subtitle content.

    Attributes:
        start_time (str): Start time of the subtitle block.
        end_time (str): End time of the subtitle block.
        content (list[str]): Content of the subtitle block.
    """
    start_time: str
    end_time: str
    content: list[str]

    @classmethod
    def from_lines(cls, lines: list[str]) -> 'SrtBlock':
        """
        Creates an SrtBlock instance from a list of strings.
        """
        assert len(lines) >= 3, lines
        start_time, end_time = list(map(str.strip, lines[1].split(ARROW)))
        return cls(start_time, end_time, lines[2:])

    def to_lines(self, line_number: int) -> list[str]:
        """
        Converts the SrtBlock instance back into a list of strings suitable for writing to an SRT file.
        """
        result = [
            str(line_number),
            ''.join([self.start_time, ' ', ARROW, ' ', self.end_time]),
        ]
        result.extend(self.content)
        result.append('')  # there must be an empty line at the end of each block, including the last one
        return result


def yield_srt_blocks_from_lines(lines: Iterable[str]) -> Iterator[SrtBlock]:
    """
    Yields SrtBlock instances from an iterable of lines from an SRT file.
    
    Args:
        text (Iterable[str]): Iterable of strings representing the SRT file content.
    
    Yields:
        SrtBlock instances.
    """
    block_lines: list[str] = []
    for line in lines:
        line = line.strip()
        if not line and block_lines:
            # terminate an SRT block when an empty line is encountered
            yield SrtBlock.from_lines(block_lines)
            block_lines.clear()
        elif line:
            # handle consecutive empty lines or a file that starts with an empty line
            block_lines.append(line)
    if block_lines:
        # ensure the last block is yielded if file doesn't end with an empty line
        yield SrtBlock.from_lines(block_lines)


def yield_deduplicated_srt_blocks(blocks: Iterable[SrtBlock]) -> Iterator[SrtBlock]:
    """
    Yields deduplicated SrtBlock instances from an iterable of SrtBlock instances.
    
    Args:
        blocks (Iterable[SrtBlock]): Iterable of SrtBlock instances.
    
    Yields:
        Deduplicated SrtBlock instances.
    """
    previous: SrtBlock | None = None
    for current in blocks:
        if previous and current.content == previous.content:
            previous.end_time = current.end_time
        else:
            if previous:
                yield previous
            previous = current
    if previous:
        yield previous


def yield_lines_from_srt_blocks(blocks: Iterable[SrtBlock]) -> Iterator[str]:
    """
    Yields lines from an iterable of SrtBlock objects.

    Args:
        blocks (Iterable[SrtBlock]): An iterable of SrtBlock objects.

    Yields:
        str: A line from the string representation of the SRT file content.
    """
    for i, block in enumerate(blocks, start=1):
        yield from block.to_lines(i)


def convert_srt_blocks_to_str(blocks: Iterable[SrtBlock]) -> str:
    """
    Converts an iterable of SrtBlock instances to a single string suitable for writing to an SRT file.
    
    Args:
        blocks (Iterable[SrtBlock]): An iterable of SrtBlock objects.
    
    Returns:
        String representation of the SRT file content.
    """
    return '\n'.join(yield_lines_from_srt_blocks(blocks))


def deduplicate_srt_file(input_file_path: Path, output_file_path: Path | None = None, overwrite: OverwriteMode = OverwriteMode.PROMPT) -> Path:
    """
    Deduplicates the contents of an SRT file and writes the deduplicated content to a new file.

    Args:
        input_file_path (Path): The path to the input SRT file.
        output_file_path (Path | None, optional): The path to the output file. If not provided, the input file will be overwritten. Defaults to None.
        overwrite (OverwriteMode, optional): Whether to overwrite existing SRT files. Defaults to `OverwriteMode.PROMPT`.

    Returns:
        Path: The path to the output file.
    """
    print("Deduplicating SRT file:", input_file_path)
    output_file_path = output_file_path or input_file_path
    if output_file_path.is_file() and not overwrite_existing_path(output_file_path, overwrite):
        return output_file_path
    output_file_path = prepare_output_file(output_file_path)
    assert isinstance(output_file_path, Path)  # narrow down type from `Path | None` to `Path`
    with prepare_input_file(input_file_path).open() as file_handler:
        # force a file read before closing file_handler because both generators are lazy
        blocks = list(yield_deduplicated_srt_blocks(yield_srt_blocks_from_lines(file_handler)))
    output_file_path.write_text(convert_srt_blocks_to_str(blocks))
    return output_file_path


def main() -> None:
    """
    CLI entry point to deduplicate SRT files.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", type=Path, nargs='+', metavar='path', help="SRT file paths to deduplicate.")
    parser.add_argument("-o", "--overwrite", choices=OverwriteMode.values(), default=OverwriteMode.PROMPT.value, help="Whether to overwrite existing SRT files. Defaults to `OverwriteMode.PROMPT`.")
    args = parser.parse_args()
    overwrite = OverwriteMode(args.overwrite)
    for path in args.paths:
        deduplicate_srt_file(path, overwrite=overwrite)


if __name__ == '__main__':
    main()
