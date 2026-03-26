from typing import Generator, Iterable

from faster_whisper.transcribe import Segment


REJECTED_SUBSTRINGS: tuple[str, ...] = (
    '明镜与点点',
    '杨茜茜',
)


class RejectedTranscriptionError(RuntimeError):
    """
    Raised when Whisper emits a known bad output substring.
    """


def get_rejected_substring(text: str) -> str | None:
    """
    Returns the matched rejected substring, if any.
    """
    for rejected_substring in REJECTED_SUBSTRINGS:
        if rejected_substring in text:
            return rejected_substring
    return None


def reject_bad_segments(segments_generator: Iterable[Segment]) -> Generator[Segment, None, None]:
    """
    Raises RejectedTranscriptionError when Whisper emits a known bad segment.
    """
    for segment in segments_generator:
        print(segment)
        if rejected_substring := get_rejected_substring(segment.text):
            raise RejectedTranscriptionError(
                f"Segment contains rejected substring: {rejected_substring!r}"
            )
        yield segment
