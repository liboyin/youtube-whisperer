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


def duplicate_segments_to_file(segments: Iterable[Segment], output_file_path: Path, flush_every: int = 100) -> Iterator[Segment]:
    """
    Writes Segments to a file, and yield them.

    Args:
        segments (Iterable[Segment]): The Segments to write.
        output_file_path (Path): The path to the file to write to.
        flush_every (int): Flush the file every X lines. Defaults to 100.

    Yields:
        Segments from input as-is.
    """
    assert isinstance(flush_every, int) and flush_every > 0, flush_every
    with prepare_output_file(output_file_path).open('w') as file_handler:
        for i, x in enumerate(segments):
            if x.text == '请不吝点赞 订阅 转发 打赏支持明镜与点点栏目':
                return
            # write a newline between Segments, but not after the last one
            if i:
                file_handler.write(f'\n{x}')
            else:
                file_handler.write(str(x))
            if (i + 1) % flush_every == 0:
                file_handler.flush()
            yield x
