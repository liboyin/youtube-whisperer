from pathlib import Path
from typing import Iterable, Iterator

from faster_whisper.transcribe import Segment
from faster_whisper.utils import format_timestamp
from pathlib_extensions import OverwriteMode, overwrite_existing_path, prepare_output_file

from youtube_whisperer.formatters.srt_deduplicator import SrtBlock, convert_srt_blocks_to_str, yield_deduplicated_srt_blocks


class WhisperSegmentAdaptor:
    def __init__(self, segments: Iterable[Segment]) -> None:
        self.segment_iter = iter(segments)  # lazy evaluation

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

    def yield_as_srt_blocks(self) -> Iterator[SrtBlock]:
        """
        Yields SrtBlock objects from the segments.
        """
        return map(self.segment_to_srt_block, self.segment_iter)

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
        srt_blocks_generator = self.yield_as_srt_blocks()
        if deduplicate:
            srt_blocks_generator = yield_deduplicated_srt_blocks(srt_blocks_generator)
        file_path.write_text(convert_srt_blocks_to_str(srt_blocks_generator))
