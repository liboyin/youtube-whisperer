import asyncio
import time
from pathlib import Path
from typing import List, Tuple, Optional

import azure.cognitiveservices.speech as speechsdk
from pathlib_extensions import OverwriteMode, overwrite_existing_path
import soundfile as sf

from youtube_whisperer.adaptors.azure_adaptor import AzureRecognitionResultAdaptor
from youtube_whisperer.adaptors.lang_code_adaptor import LanguageCode
from youtube_whisperer.utils import load_and_get_env_vars

AZURE_SPEECH_API_KEY, AZURE_SERVICE_REGION = load_and_get_env_vars("AZURE_SPEECH_API_KEY", "AZURE_SERVICE_REGION")


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


async def transcribe_audio_file_async(input_file_path: Path, source_language: str) -> None:
    """
    Asynchronously transcribes an audio file using Azure AI Speech service.

    Args:
        audio_file (Path): The path to the audio file to transcribe.
        source_language (str): The language of the audio file.

    Raises:
        Exception: If there is an error during transcription.
    """
    speech_config = speechsdk.SpeechConfig(subscription=AZURE_SPEECH_API_KEY, region=AZURE_SERVICE_REGION)
    speech_config.speech_recognition_language = source_language
    audio_config = speechsdk.audio.AudioConfig(filename=str(input_file_path))
    speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)
    result_adaptor = AzureRecognitionResultAdaptor()
    
    done = asyncio.Event()
    error = None

    def stop_cb(evt: speechsdk.SessionEventArgs):
        print(f'CLOSING session: {evt}')
        done.set()

    def recognized_cb(evt: speechsdk.SpeechRecognitionEventArgs):
        print(f'RECOGNIZED: {evt}')
        if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
            result_adaptor.append(evt.result)

    def canceled_cb(evt: speechsdk.SpeechRecognitionCanceledEventArgs):
        nonlocal error
        print(f'CANCELED: {evt.reason}')
        if evt.reason == speechsdk.CancellationReason.Error:
            error = Exception(evt.error_details)
        done.set()

    speech_recognizer.recognized.connect(recognized_cb)
    speech_recognizer.session_stopped.connect(stop_cb)
    speech_recognizer.canceled.connect(canceled_cb)

    speech_recognizer.start_continuous_recognition()
    
    timeout = get_audio_duration_seconds(input_file_path) + 10 # Add a 10s buffer
    try:
        await asyncio.wait_for(done.wait(), timeout=timeout)
    except asyncio.TimeoutError:
        speech_recognizer.stop_continuous_recognition()
        raise Exception(f"Transcription timed out after {timeout} seconds")

    speech_recognizer.stop_continuous_recognition()

    if error:
        raise error

    result_adaptor.save_as_srt_file(input_file_path.with_suffix('.srt'), deduplicate=True)


async def transcribe_audio_files_concurrently(
    input_file_path: List[Path],
    source_language: str,
    max_workers: Optional[int] = None
) -> List[Tuple[Path, Optional[Exception]]]:
    """
    Transcribes multiple audio files concurrently using Azure AI Speech service.

    Args:
        audio_files (List[Path]): List of audio file paths to transcribe.
        source_language (str): The language of the audio files.
        max_workers (Optional[int]): Maximum number of concurrent workers. Defaults to 10 if None.

    Returns:
        List[Tuple[Path, Optional[Exception]]]: List of tuples containing the audio file path and any exception raised (None if successful).
    """
    async def transcribe_and_catch(audio_file: Path, semaphore: asyncio.Semaphore) -> Tuple[Path, Optional[Exception]]:
        async with semaphore:
            try:
                await transcribe_audio_file_async(audio_file, source_language)
                return (audio_file, None)
            except Exception as e:
                return (audio_file, e)

    concurrency_limit = max_workers if max_workers is not None else 10
    semaphore = asyncio.Semaphore(concurrency_limit)
    tasks = [transcribe_and_catch(f, semaphore) for f in input_file_path]
    results = await asyncio.gather(*tasks)
    return results


async def transcribe_audio_files_fire_and_forget(
    audio_files: List[Path],
    source_language: str,
    max_workers: Optional[int] = None
) -> None:
    """
    Starts transcription of multiple audio files concurrently and returns immediately.

    Args:
        audio_files (List[Path]): List of audio file paths to transcribe.
        source_language (str): The language of the audio files.
        max_workers (Optional[int]): Maximum number of concurrent workers. Defaults to 10 if None.
    """
    async def transcribe_and_ignore(audio_file: Path, semaphore: asyncio.Semaphore):
        async with semaphore:
            try:
                await transcribe_audio_file_async(audio_file, source_language)
            except Exception:
                pass  # Ignore all exceptions

    concurrency_limit = max_workers if max_workers is not None else 10
    semaphore = asyncio.Semaphore(concurrency_limit)

    for audio_file in audio_files:
        asyncio.create_task(transcribe_and_ignore(audio_file, semaphore))


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
