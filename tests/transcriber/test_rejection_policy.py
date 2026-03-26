from types import SimpleNamespace

import pytest

import youtube_whisperer.transcriber.rejection_policy as testee


def make_segment(text: str) -> SimpleNamespace:
    return SimpleNamespace(text=text)


def test_get_rejected_substring_returns_none_for_safe_text():
    assert testee.get_rejected_substring("hello world") is None


def test_get_rejected_substring_returns_match_for_rejected_substring():
    rejected_substring = testee.REJECTED_SUBSTRINGS[0]

    assert testee.get_rejected_substring(rejected_substring) == rejected_substring


def test_reject_bad_segments_yields_safe_segments():
    segments = [make_segment("hello"), make_segment("world")]

    result = list(testee.reject_bad_segments(segments))

    assert [segment.text for segment in result] == ["hello", "world"]


def test_reject_bad_segments_raises_for_segment_containing_rejected_substring():
    rejected_substring = testee.REJECTED_SUBSTRINGS[0]
    segments = [make_segment(f"prefix {rejected_substring} suffix")]

    with pytest.raises(testee.RejectedTranscriptionError, match="Segment contains rejected substring"):
        list(testee.reject_bad_segments(segments))
