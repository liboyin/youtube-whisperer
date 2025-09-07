from pathlib import Path
from typing import Iterator

from faster_whisper.utils import format_timestamp
from pathlib_extensions import OverwriteMode, overwrite_existing_path, prepare_output_file
from azure.cognitiveservices.speech import SpeechRecognitionResult
from youtube_whisperer.formatters.srt_deduplicator import SrtBlock, convert_srt_blocks_to_str, yield_deduplicated_srt_blocks


class AzureRecognitionResultAdaptor:
    def __init__(self):
        self.segments: list[SpeechRecognitionResult] = []

    def append(self, segment: SpeechRecognitionResult) -> None:
        self.segments.append(segment)

    @staticmethod
    def recognition_result_to_srt_block(segment: SpeechRecognitionResult) -> SrtBlock:
        """
        Converts a `SpeechRecognitionResult` object to `SrtBlock`.
        """
        start_seconds = segment.offset / 10_000_000
        end_seconds = (segment.offset + segment.duration) / 10_000_000
        return SrtBlock(
            format_timestamp(start_seconds, always_include_hours=True, decimal_marker=','),
            format_timestamp(end_seconds, always_include_hours=True, decimal_marker=','),
            segment.text.strip().split('\n'),
        )

    def yield_as_srt_blocks(self) -> Iterator[SrtBlock]:
        """
        Yields SrtBlock objects from recorded recognition results.
        """
        return map(self.recognition_result_to_srt_block, self.segments)

    def save_as_srt_file(self, file_path: Path, deduplicate: bool = True, overwrite: OverwriteMode = OverwriteMode.PROMPT) -> None:
        """
        Converts recorded recognition results to an SRT file.

        Args:
            file_path (Path): The path to the output SRT file.
            deduplicate (bool, optional): Whether to deduplicate the segments. Defaults to True.
            overwrite (OverwriteMode, optional): Whether to overwrite existing SRT files. Defaults to `prompt`.
        """
        if file_path.is_file() and not overwrite_existing_path(file_path, overwrite):
            return
        output_path = prepare_output_file(file_path)
        srt_blocks_generator = self.yield_as_srt_blocks()
        if deduplicate:
            srt_blocks_generator = yield_deduplicated_srt_blocks(srt_blocks_generator)
        output_path.write_text(convert_srt_blocks_to_str(srt_blocks_generator))
