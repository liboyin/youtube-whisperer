from pathlib import Path
from typing import Iterable, Iterator

from faster_whisper.transcribe import Segment
from pathlib_extensions import prepare_output_file


def load_segments_from_lines(lines: Iterable[str]) -> list[Segment]:
    """
    Loads Segments from an iterable of lines.
    """
    result = []
    for line in lines:
        if line := line.strip():
            result.append(eval(line, globals(), locals()))
    return result


def load_segments_from_file(file_path: Path) -> list[Segment]:
    """
    Loads Segments from a file.
    """
    with file_path.open() as file_handler:
        return load_segments_from_lines(file_handler)


def write_segments_to_file(segments: Iterable[Segment], file_path: Path) -> None:
    """
    Writes Segments to a file.

    Args:
        segments (Iterable[Segment]): The Segments to write.
        file_path (Path): The path to the file to write to.
    """
    prepare_output_file(file_path).write_text('\n'.join(map(str, segments)))


def duplicate_segments_to_file(segments: Iterable[Segment], file_path: Path, flush: bool = False) -> Iterator[Segment]:
    """
    Writes Segments to a file, and yield them.

    Args:
        segments (Iterable[Segment]): The Segments to write.
        file_path (Path): The path to the file to write to.
        flush (bool, optional): Whether to flush the file after writing each Segment. Defaults to False.

    Yields:
        Segments from input as-is.
    """
    with prepare_output_file(file_path).open('w') as file_handler:
        for i, x in enumerate(segments):
            # write a newline between Segments, but not after the last one
            if i:
                file_handler.write(f'\n{x}')
            else:
                file_handler.write(str(x))
            if flush:
                # wait until the current Segment is written to disk
                file_handler.flush()
            yield x
