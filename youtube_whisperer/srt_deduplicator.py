import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Generator, Iterable, Self

ARROW = '-->'

@dataclass
class SrtBlock:
    """
    Represents a subtitle block within an SRT file, including its start and end times, along with the subtitle content.
    """
    start_time: str
    end_time: str
    content: list[str]

    @classmethod
    def from_lines(cls, lines: list[str]) -> Self:
        """
        Creates an SrtBlock instance from a list of strings, where the first line is the start and end times, 
        followed by the subtitle content lines.
        
        :param lines: List of strings representing the subtitle block.
        :return: An instance of SrtBlock.
        """
        assert len(lines) >= 3, lines
        start_time, end_time = list(map(str.strip, lines[1].split(ARROW)))
        return cls(start_time, end_time, lines[2:])

    def to_lines(self, line_number: int, trailing_new_line: bool = True) -> list[str]:
        """
        Converts the SrtBlock instance back into a list of strings suitable for writing to an SRT file.
        
        :param line_number: The sequence number of the subtitle block.
        :param trailing_new_line: Whether to append a new line at the end.
        :return: A list of strings representing the SrtBlock in SRT file format.
        """
        result = [
            str(line_number),
            ''.join([self.start_time, ' ', ARROW, ' ', self.end_time]),
        ] + self.content
        if trailing_new_line:
            result.append('\n')
        return result


def yield_stripped_lines(text: Iterable[str]) -> Generator[str, None, None]:
    """
    Generator that yields stripped lines from an iterable of strings, removing leading and trailing whitespace.
    
    :param text: Iterable of strings.
    :yield: Stripped string.
    """
    for line in text:
        yield line.strip()


def yield_srt_blocks(text: Iterable[str]) -> Generator[SrtBlock, None, None]:
    """
    Generator that yields SrtBlock instances from an iterable of lines from an SRT file.
    
    :param text: Iterable of strings representing the SRT file content.
    :yield: SrtBlock instances.
    """
    block_lines: list[str] = []
    for line in text:
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


def deduplicate_srt_blocks(blocks: Iterable[SrtBlock]) -> list[SrtBlock]:
    """
    Deduplicates consecutive SrtBlock instances with identical content by merging their time spans.
    
    :param blocks: Iterable of SrtBlock instances.
    :return: List of deduplicated SrtBlock instances.
    """
    result: list[SrtBlock] = []
    for block in blocks:
        if result and block.content == result[-1].content:
            result[-1].end_time = block.end_time
        else:
            result.append(block)
    return result


def deduplicate_single(file_path: Path) -> None:
    """
    Main function to read an SRT file, deduplicate subtitle blocks, and write the results back to the same file.
    
    :param file_path: Path to the SRT file.
    """
    print(f"Processing {file_path}")
    with file_path.open(mode='r') as file_handler:
        blocks = deduplicate_srt_blocks(yield_srt_blocks(yield_stripped_lines(file_handler)))
    with file_path.open(mode='w') as file_handler:
        lines = ('\n'.join(block.to_lines(i)) for i, block in enumerate(blocks, start=1))
        file_handler.writelines(lines)


def deduplicate_multi(dir_path: Path, recursive: bool = True) -> None:
    """
    Main function to read all SRT files in a directory and its subdirectories (if recursive is True), 
    deduplicate subtitle blocks, and write the results back to the same files.

    :param dir_path: Path to the directory containing SRT files.
    :param recursive: Whether to search for SRT files recursively in subdirectories. Default is True.
    """
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
