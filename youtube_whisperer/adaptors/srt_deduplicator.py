import logging
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

from pathlib_extensions import (
    OverwritePolicy,
    StagedFile,
    prepare_input_file,
    prepare_output_file,
)

from youtube_whisperer.overwrite import require_supported_policy, resolve_output_path

logger = logging.getLogger(__name__)

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

        Args:
            lines (list[str]): The lines of a single SRT block: a sequence number, a
                `start --> end` timing line, and one or more content lines.

        Returns:
            SrtBlock: The parsed subtitle block.

        Raises:
            ValueError: If `lines` has fewer than the three required lines (sequence number,
                timing line, and at least one content line). These lines come from downloaded
                SRT files, so a clean error is raised instead of an assert that vanishes under `python -O`.
        """
        if len(lines) < 3:
            raise ValueError(f"Malformed SRT block, expected at least 3 lines: {lines}")
        start_time, end_time = list(map(str.strip, lines[1].split(ARROW)))
        return cls(start_time, end_time, lines[2:])

    def to_lines(self, line_number: int) -> list[str]:
        """
        Converts the SrtBlock instance back into a list of strings suitable for writing to an SRT file.

        Args:
            line_number (int): The 1-based sequence number to assign to this block.

        Returns:
            list[str]: The block rendered as SRT lines, terminated by an empty line.
        """
        result = [
            str(line_number),
            f'{self.start_time} {ARROW} {self.end_time}',
        ]
        result.extend(self.content)
        result.append('')  # there must be an empty line at the end of each block, including the last one
        return result


def format_srt_timestamp(seconds: float) -> str:
    """Format nonnegative seconds with forced hours and comma milliseconds.

    Round total milliseconds before decomposition so ties and carries preserve
    the converters' faster-whisper formatting contract. Hours have no upper bound.

    Args:
        seconds (float): Timestamp in seconds.

    Returns:
        str: Timestamp in HH:MM:SS,mmm form, with at least two hour digits.

    Raises:
        AssertionError: If seconds is negative.
    """
    assert seconds >= 0, "non-negative timestamp expected"
    milliseconds = round(seconds * 1000.0)
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    seconds_part, milliseconds = divmod(milliseconds, 1_000)
    return f'{hours:02d}:{minutes:02d}:{seconds_part:02d},{milliseconds:03d}'


def timestamps_to_srt_block(start: float, end: float, text: str) -> SrtBlock:
    """Convert seconds and text to a block without depending on an engine.

    Args:
        start (float): Nonnegative start timestamp in seconds.
        end (float): Nonnegative end timestamp in seconds.
        text (str): Content whose outer whitespace is stripped before splitting
            only on newline characters; empty text retains one empty content line.

    Returns:
        SrtBlock: Formatted timestamps and content lines.

    Raises:
        AssertionError: If either timestamp is negative.
    """
    return SrtBlock(format_srt_timestamp(start), format_srt_timestamp(end), text.strip().split('\n'))


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


def publish_srt_text(file_path: Path, text: str, overwrite: OverwritePolicy = OverwritePolicy.ALWAYS) -> None:
    """Publish complete SRT text after writing and closing it inside a `StagedFile`.

    Callers own the existing-output preflight. NEVER preserves even a completed
    file created while staging; ALWAYS replaces the target.
    A publication collision is skipped only if the destination is a file,
    including a symlink to a file; other collisions propagate FileExistsError.
    Existing symlinks are followed and mode bits retained. Inode replacement can
    change ownership, ACLs, and extended attributes; hardlinked aliases keep old
    contents. Abrupt process exit can leave a hidden stage directory, but never
    partial final text. This does not promise power-loss durability or scavenge
    abandoned stages.

    Args:
        file_path (Path): Final SRT path, with parents created as needed.
        text (str): Fully materialized text, preserved with ordinary text I/O.
        overwrite (OverwritePolicy): ALWAYS or NEVER. Defaults to ALWAYS, like every SRT helper
            in this module (D49).

    Raises:
        ValueError: If `overwrite` is not ALWAYS or NEVER.
        OSError: If staging, closing, mode preservation, or publication fails,
            including unsupported hard-link publication. The private stage
            directory is removed on every exit.
    """
    require_supported_policy(overwrite)
    # Exclusive text creation uses 0666 filtered by umask without mutating it.
    with StagedFile(file_path, overwrite) as staged, staged.path.open('x') as writer:
        writer.write(text)


def save_segments_as_srt(blocks: Iterable[SrtBlock], file_path: Path, deduplicate: bool = True, overwrite: OverwritePolicy = OverwritePolicy.ALWAYS) -> None:
    """
    Serialize all SrtBlocks before publishing complete SRT text atomically.

    Declined overwrites avoid lazy consumption. Serialization and rejection finish
    before staging, preserving the previous output if they raise.

    Args:
        blocks (Iterable[SrtBlock]): SrtBlock objects to write, typically produced by mapping a transcriber-specific converter over recognition results.
        file_path (Path): The path to the output SRT file.
        deduplicate (bool, optional): Whether to merge consecutive blocks with identical content. Defaults to True.
        overwrite (OverwritePolicy, optional): ALWAYS replaces an existing file; NEVER keeps it. Defaults to ALWAYS,
            like every SRT helper in this module (D49).

    Raises:
        ValueError: If `overwrite` is not ALWAYS or NEVER.
    """
    if resolve_output_path(file_path, overwrite) is None:
        return
    file_path = prepare_output_file(file_path)
    if deduplicate:
        blocks = yield_deduplicated_srt_blocks(blocks)
    publish_srt_text(file_path, convert_srt_blocks_to_str(blocks), overwrite=overwrite)


def deduplicate_srt_file(input_file_path: Path, output_file_path: Path | None = None, overwrite: OverwritePolicy = OverwritePolicy.ALWAYS) -> Path:
    """
    Read and deduplicate an SRT file before atomically publishing complete text.

    In-place deduplication fully reads and closes input before staging output;
    publication failure preserves the prior file.

    Args:
        input_file_path (Path): The path to the input SRT file.
        output_file_path (Path | None, optional): The path to the output file. If `None`, the input file will be overwritten. Defaults to `None`.
        overwrite (OverwritePolicy, optional): ALWAYS replaces an existing output file; NEVER keeps it,
            so in-place deduplication under NEVER changes nothing. Defaults to ALWAYS, like every SRT
            helper in this module (D49).

    Returns:
        Path: The path to the output file.

    Raises:
        ValueError: If `overwrite` is not ALWAYS or NEVER.
    """
    logger.info("Deduplicating SRT file: %s", input_file_path)
    output_file_path = output_file_path or input_file_path
    if resolve_output_path(output_file_path, overwrite) is None:
        return output_file_path
    with prepare_input_file(input_file_path).open() as file_handler:
        # force a file read before closing file_handler because both generators are lazy
        blocks = list(yield_deduplicated_srt_blocks(yield_srt_blocks_from_lines(file_handler)))
    publish_srt_text(output_file_path, convert_srt_blocks_to_str(blocks), overwrite=overwrite)
    return output_file_path
