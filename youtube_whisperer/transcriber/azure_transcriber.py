import asyncio
import time
from pathlib import Path
from typing import List, Tuple, Optional

import azure.cognitiveservices.speech as speechsdk
import soundfile as sf

from youtube_whisperer.adaptors.azure_adaptor import AzureRecognitionResultAdaptor
from youtube_whisperer.utils import load_and_get_env_vars

AZURE_SPEECH_API_KEY, AZURE_SERVICE_REGION = load_and_get_env_vars("AZURE_SPEECH_API_KEY", "AZURE_SERVICE_REGION")


def get_audio_duration(audio_file: Path) -> float:
    """Get the duration of an audio file in seconds."""
    return sf.info(str(audio_file)).duration


def transcribe_audio_file(audio_file: Path, source_language: str) -> None:
    """
    Transcribes an audio file using Azure AI Speech service.

    Args:
        audio_file (Path): The path to the audio file to transcribe.
        source_language (str): The language of the audio file.

    Returns:
        str: The transcription of the audio file.

    Raises:
        Exception: If there is an error during transcription.
    """
    speech_config = speechsdk.SpeechConfig(subscription=AZURE_SPEECH_API_KEY, region=AZURE_SERVICE_REGION)
    speech_config.speech_recognition_language = source_language
    audio_config = speechsdk.audio.AudioConfig(filename=str(audio_file))
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

    speech_recognizer.start_continuous_recognition()

    start_time = time.time()
    timeout = get_audio_duration(audio_file)
    while not done:
        if time.time() - start_time > timeout:
            speech_recognizer.stop_continuous_recognition()
            raise Exception(f"Transcription timed out after {timeout} seconds")
        time.sleep(1)

    speech_recognizer.stop_continuous_recognition()
    result_adaptor.save_as_srt_file(audio_file.with_suffix('.srt'), deduplicate=True)


async def transcribe_audio_file_async(audio_file: Path, source_language: str) -> None:
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
    audio_config = speechsdk.audio.AudioConfig(filename=str(audio_file))
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
    
    timeout = get_audio_duration(audio_file) + 10 # Add a 10s buffer
    try:
        await asyncio.wait_for(done.wait(), timeout=timeout)
    except asyncio.TimeoutError:
        speech_recognizer.stop_continuous_recognition()
        raise Exception(f"Transcription timed out after {timeout} seconds")

    speech_recognizer.stop_continuous_recognition()

    if error:
        raise error

    result_adaptor.save_as_srt_file(audio_file.with_suffix('.srt'), deduplicate=True)


async def transcribe_audio_files_concurrently(
    audio_files: List[Path],
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
    tasks = [transcribe_and_catch(f, semaphore) for f in audio_files]
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
        audio_file=args.audio_file,
        source_language=args.source_language
    )
