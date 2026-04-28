import os
import threading
from pathlib import Path
from typing import Any

import azure.cognitiveservices.speech as speechsdk
from azure.cognitiveservices.speech import SpeechRecognitionResult
from faster_whisper.utils import format_timestamp
from pathlib_extensions import OverwriteMode, overwrite_existing_path
import soundfile as sf

from youtube_whisperer.adaptors.lang_code_adaptor import LanguageCode
from youtube_whisperer.adaptors.srt_deduplicator import SrtBlock, save_segments_as_srt

AZURE_SPEECH_API_KEY = os.getenv("AZURE_SPEECH_API_KEY")
AZURE_SERVICE_REGION = os.getenv("AZURE_SERVICE_REGION")


def get_audio_duration_seconds(audio_file: Path) -> float:
    """Get the duration of an audio file in seconds."""
    return sf.info(str(audio_file)).duration


def recognition_result_to_srt_block(segment: SpeechRecognitionResult) -> SrtBlock:
    """
    Convert an Azure SpeechRecognitionResult into an SrtBlock.

    Args:
        segment (SpeechRecognitionResult): An Azure recognition result whose `offset` and `duration` are expressed in 100-nanosecond ticks.

    Returns:
        SrtBlock: The SrtBlock representation of the input recognition result.
    """
    start_seconds = segment.offset / 10_000_000
    end_seconds = (segment.offset + segment.duration) / 10_000_000
    return SrtBlock(
        format_timestamp(start_seconds, always_include_hours=True, decimal_marker=','),
        format_timestamp(end_seconds, always_include_hours=True, decimal_marker=','),
        segment.text.strip().split('\n'),
    )


def transcribe_audio_file(input_file_path: Path, language: LanguageCode, output_file_path: Path | None = None, overwrite: OverwriteMode = OverwriteMode.PROMPT) -> Path | None:
    """
    Transcribes an audio file using Azure AI Speech service.

    This function blocks until Azure recognition completes, fails, or times
    out. The synchronous behavior keeps queue state aligned with actual task
    completion in the Azure worker.

    Args:
        input_file_path (Path): The path to the audio file to transcribe.
        language (LanguageCode): The language of the audio file.
        output_file_path (Path | None, optional): The path to the output SRT file. If `None`, it will be the input file path with a `.srt` extension. Defaults to `None`.
        overwrite (OverwriteMode, optional): Whether to overwrite existing SRT files. Defaults to `prompt`.

    Returns:
        Path | None: Output SRT file path, or `None` if transcription failed.
    """
    output_file_path = output_file_path or input_file_path.with_suffix('.srt')
    if output_file_path.is_file() and not overwrite_existing_path(output_file_path, overwrite):
        return output_file_path
    speech_config = speechsdk.SpeechConfig(subscription=AZURE_SPEECH_API_KEY, region=AZURE_SERVICE_REGION)
    speech_config.speech_recognition_language = language.get_source_as_BCP()
    audio_config = speechsdk.audio.AudioConfig(filename=str(input_file_path))
    speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)
    recognition_results: list[SpeechRecognitionResult] = []
    done = threading.Event()
    transcription_error: Exception | None = None

    def stop_cb(evt: Any) -> None:
        print(f'CLOSED: {evt}')
        done.set()

    def recognized_cb(evt: Any) -> None:
        print(f'UPDATE: {evt}')
        if evt.result.text:  # sometimes there is an empty update at the end of the recognition
            recognition_results.append(evt.result)

    def canceled_cb(evt: Any) -> None:
        nonlocal transcription_error
        print(f'CANCELED: {evt}')
        if evt.cancellation_details.reason == speechsdk.CancellationReason.Error:
            transcription_error = RuntimeError(evt.cancellation_details.error_details)
        done.set()

    speech_recognizer.recognized.connect(recognized_cb)
    speech_recognizer.canceled.connect(canceled_cb)
    speech_recognizer.session_stopped.connect(stop_cb)

    print("Starting transcription on Azure...")
    speech_recognizer.start_continuous_recognition()

    timeout_seconds = get_audio_duration_seconds(input_file_path) * 1.5  # time out after 1.5x audio duration
    try:
        if not done.wait(timeout_seconds):
            raise TimeoutError(f"Transcription timed out after {timeout_seconds} seconds")
    finally:
        speech_recognizer.stop_continuous_recognition()

    if transcription_error is not None:
        raise transcription_error

    save_segments_as_srt(map(recognition_result_to_srt_block, recognition_results), output_file_path, deduplicate=True)
    return output_file_path


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("audio_file", type=Path, help="Path to the audio file to transcribe")
    parser.add_argument("source_language", type=LanguageCode.from_str, help="Source language code (e.g., en-US)")
    args = parser.parse_args()
    transcribe_audio_file(
        input_file_path=args.audio_file,
        language=args.source_language
    )
