from pathlib_extensions import OverwriteMode

import youtube_whisperer.adaptors.azure_adaptor as testee
from youtube_whisperer.adaptors.srt_deduplicator import SrtBlock


class MockSpeechRecognitionResult:
    def __init__(self, offset: int, duration: int, text: str):
        self.offset = offset
        self.duration = duration
        self.text = text


def test_recognition_result_to_srt_block():
    # 1 second offset, 2 seconds duration
    segment = MockSpeechRecognitionResult(offset=10_000_000, duration=20_000_000, text="Hello world")
    result = testee.AzureRecognitionResultAdaptor.recognition_result_to_srt_block(segment)
    expected = SrtBlock(
        start_time="00:00:01,000",
        end_time="00:00:03,000",
        content=["Hello world"],
    )
    assert result == expected


def test_yield_as_srt_blocks():
    adaptor = testee.AzureRecognitionResultAdaptor()
    adaptor.append(MockSpeechRecognitionResult(offset=10_000_000, duration=20_000_000, text="First line"))
    adaptor.append(MockSpeechRecognitionResult(offset=30_000_000, duration=15_000_000, text="Second line"))
    result = list(adaptor.yield_as_srt_blocks())
    expected = [
        SrtBlock(start_time="00:00:01,000", end_time="00:00:03,000", content=["First line"]),
        SrtBlock(start_time="00:00:03,000", end_time="00:00:04,500", content=["Second line"]),
    ]
    assert result == expected


def test_save_as_srt_file(tmp_path):
    output_file = tmp_path / "test.srt"
    adaptor = testee.AzureRecognitionResultAdaptor()
    adaptor.append(MockSpeechRecognitionResult(offset=10_000_000, duration=20_000_000, text="Hello"))
    adaptor.save_as_srt_file(output_file, overwrite=OverwriteMode.ALWAYS)
    assert output_file.is_file()
    result = output_file.read_text()
    expected = "1\n00:00:01,000 --> 00:00:03,000\nHello\n"
    assert result == expected


def test_save_as_srt_file_skips_existing_when_overwrite_never(tmp_path):
    output_file = tmp_path / "test.srt"
    output_file.write_text("original content")
    adaptor = testee.AzureRecognitionResultAdaptor()
    adaptor.append(MockSpeechRecognitionResult(offset=10_000_000, duration=20_000_000, text="Hello"))
    adaptor.save_as_srt_file(output_file, overwrite=OverwriteMode.NEVER)
    assert output_file.read_text() == "original content"
