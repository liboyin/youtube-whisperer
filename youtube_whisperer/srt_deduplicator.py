import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Generator, Iterable, Self

from youtube_whisperer.pathlib_extensions import prepare_input_file, prepare_input_dir

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
    def from_lines(cls, lines: list[str]) -> Self:
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


def yield_srt_blocks(lines: Iterable[str]) -> Generator[SrtBlock, None, None]:
    """
    Generator that yields SrtBlock instances from an iterable of lines from an SRT file.
    
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


def yield_deduplicated_srt_blocks(blocks: Iterable[SrtBlock]) -> Generator[SrtBlock, None, None]:
    """
    Generator that yields deduplicated SrtBlock instances from an iterable of SrtBlock instances.
    
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


def yield_lines_from_srt_blocks(blocks: Iterable[SrtBlock]) -> Generator[str, None, None]:
    """
    Generator that yields lines from an iterable of SrtBlock objects.

    Args:
        blocks (Iterable[SrtBlock]): An iterable of SrtBlock objects.

    Yields:
        str: A line from the string representation of the SRT file content.
    """
    for i, block in enumerate(blocks, start=1):
        yield from block.to_lines(i)


def srt_blocks_to_str(blocks: Iterable[SrtBlock]) -> str:
    """
    Converts an iterable of SrtBlock instances to a single string suitable for writing to an SRT file.
    
    Args:
        blocks (Iterable[SrtBlock]): An iterable of SrtBlock objects.
    
    Returns:
        String representation of the SRT file content.
    """
    return '\n'.join(yield_lines_from_srt_blocks(blocks))


def deduplicate_single(file_path: Path) -> None:
    """
    Main function to read an SRT file, deduplicate subtitle blocks, and write the results back to the same file.
    
    Args:
        file_path: Path to the SRT file.
    """
    print(f"Processing {file_path}")
    with prepare_input_file(file_path).open() as file_handler:
        # force a file read before closing file_handler because both generators are lazy
        blocks = list(yield_deduplicated_srt_blocks(yield_srt_blocks(file_handler)))
    file_path.write_text(srt_blocks_to_str(blocks))


def deduplicate_multi(dir_path: Path, recursive: bool = True) -> None:
    """
    Main function to read all SRT files in a directory and its subdirectories (if recursive is True), 
    deduplicate subtitle blocks, and write the results back to the same files.

    Args:
        dir_path: Path to the directory containing SRT files.
        recursive: Whether to search for SRT files recursively in subdirectories. Default is True.
    """
    prepare_input_dir(dir_path)
    file_iterator = dir_path.rglob('*.srt') if recursive else dir_path.glob('*.srt')
    for file_path in file_iterator:
        deduplicate_single(file_path)


def main() -> None:
    """
    CLI entry point for deduplicating SRT files.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path, help="SRT file path to read from and to write to, or a directory containing SRT files.")
    args = parser.parse_args()
    p = args.path
    if p.is_file():
        deduplicate_single(p)
    elif p.is_dir():
        deduplicate_multi(p)
    else:
        raise FileNotFoundError(f"{p} is not a file or a directory")

if __name__ == '__main__':
    main()
