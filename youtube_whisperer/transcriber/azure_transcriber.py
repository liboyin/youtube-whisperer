import os
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import azure.cognitiveservices.speech as speechsdk
from pathlib_extensions import OverwriteMode, overwrite_existing_path
import soundfile as sf

from youtube_whisperer.adaptors.azure_adaptor import AzureRecognitionResultAdaptor
from youtube_whisperer.adaptors.lang_code_adaptor import LanguageCode

AZURE_SPEECH_API_KEY = os.getenv("AZURE_SPEECH_API_KEY")
AZURE_SERVICE_REGION = os.getenv("AZURE_SERVICE_REGION")
THREAD_POOL = ThreadPoolExecutor(max_workers=10)


def get_audio_duration_seconds(audio_file: Path) -> float:
    """Get the duration of an audio file in seconds."""
    return sf.info(str(audio_file)).duration


def transcribe_audio_file(input_file_path: Path, language: LanguageCode, output_file_path: Path | None = None, overwrite: OverwriteMode = OverwriteMode.PROMPT) -> Path | None:
    """
    Transcribes an audio file using Azure AI Speech service. Blocks until the transcription is complete/failed/timed out.

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
    result_adaptor = AzureRecognitionResultAdaptor()
    done = False

    def stop_cb(evt):
        nonlocal done
        print(f'CLOSED: {evt}')
        done = True

    def recognized_cb(evt):
        print(f'UPDATE: {evt}')
        if evt.result.text:  # sometimes there is an empty update at the end of the recognition
            result_adaptor.append(evt.result)

    def canceled_cb(evt):
        print(f'CANCELED: {evt}')
        if evt.cancellation_details.reason == speechsdk.CancellationReason.Error:
            raise Exception(evt.cancellation_details.error_details)

    speech_recognizer.recognized.connect(recognized_cb)
    speech_recognizer.canceled.connect(canceled_cb)
    speech_recognizer.session_stopped.connect(stop_cb)

    print("Starting transcription on Azure...")
    speech_recognizer.start_continuous_recognition()

    start_time = time.time()
    timeout_seconds = get_audio_duration_seconds(input_file_path)  # time out after audio duration
    while not done:
        if time.time() - start_time > timeout_seconds:
            speech_recognizer.stop_continuous_recognition()
            raise Exception(f"Transcription timed out after {timeout_seconds} seconds")
        time.sleep(5)

    speech_recognizer.stop_continuous_recognition()
    result_adaptor.save_as_srt_file(output_file_path, deduplicate=True)
    return output_file_path


def transcribe_audio_file_fire_and_forget(input_file_path: Path, language: LanguageCode, output_file_path: Path | None = None, overwrite: OverwriteMode = OverwriteMode.PROMPT) -> None:
    """
    Transcribes an audio file using Azure AI Speech service in a separate thread. Does not block.

    Tasks are submitted to a ThreadPoolExecutor with a maximum of 10 concurrent workers.

    Args:
        input_file_path (Path): The path to the audio file to transcribe.
        language (LanguageCode): The language of the audio file.
        output_file_path (Path | None, optional): The path to the output SRT file. If `None`, it will be the input file path with a `.srt` extension. Defaults to `None`.
        overwrite (OverwriteMode, optional): Whether to overwrite existing SRT files. Defaults to `prompt`.
    """
    THREAD_POOL.submit(transcribe_audio_file, input_file_path, language, output_file_path, overwrite)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("audio_file", type=Path, help="Path to the audio file to transcribe")
    parser.add_argument("source_language", type=str, help="Source language code (e.g., en-US)")
    args = parser.parse_args()
    transcribe_audio_file(
        input_file_path=args.audio_file,
        language=args.source_language
    )
