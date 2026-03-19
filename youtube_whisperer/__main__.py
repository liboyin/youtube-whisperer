import argparse
import itertools
from pathlib import Path
from typing import Iterable

import more_itertools
from pathlib_extensions import OverwriteMode

from youtube_whisperer.adaptors.lang_code_adaptor import LanguageCode
from youtube_whisperer.downloaders import download_video_and_transcript_with_default_title
from youtube_whisperer.downloaders.playlist_downloader import yield_flattened_video_urls
from youtube_whisperer.transcriber.azure_transcriber import transcribe_audio_file
from youtube_whisperer.transcriber.whisper_transcriber import transcribe_file_with_default_model
from youtube_whisperer.utils import TranscriberMode, TranscriberType, is_url


def try_download_videos_and_transcripts(urls: Iterable[str], language: LanguageCode, overwrite: OverwriteMode = OverwriteMode.PROMPT) -> list[Path]:
    """
    Attempts to download videos and their transcripts from a list of URLs.

    Args:
        urls (Iterable[str]): An iterable of YouTube video or playlist URLs to download.
        language (LanguageCode): Requested transcript language to download.
        overwrite (OverwriteMode, optional): Whether to overwrite existing video & SRT files. Defaults to `prompt`.

    Returns:
        list[Path]: A list of Paths to video files that were downloaded but did not have transcripts.
    """
    video_files_without_transcripts: list[Path] = []
    for url in yield_flattened_video_urls(urls):
        video_file_path, transcript_flag = download_video_and_transcript_with_default_title(url, language, overwrite=overwrite)
        if not transcript_flag:
            video_files_without_transcripts.append(video_file_path)
    return video_files_without_transcripts


def transcribe_to_srt_files(input_file_paths: Iterable[Path], language: LanguageCode, transcriber: TranscriberType = TranscriberType.LOCAL, mode: TranscriberMode = TranscriberMode.TRANSCRIBE, overwrite: OverwriteMode = OverwriteMode.PROMPT) -> None:
    """
    Transcribes a list of waveform files using the default model and converts the transcriptions to SRT format.

    Args:
        input_file_paths (Iterable[Path]): An iterable of waveform file paths to be transcribed.
        language (LanguageCode): Whisper's output language.
        transcriber (TranscriberType, optional): The transcriber to use. Defaults to `local`.
        mode (TranscriberMode, optional): Whether to run Whisper in transcribe mode or translate mode. Defaults to `transcribe`.
        overwrite (OverwriteMode, optional): Whether to overwrite existing Segment & SRT files. Defaults to `prompt`.
    """
    for input_file_path in input_file_paths:
        match transcriber:
            case TranscriberType.AZURE:
                srt_file_path = transcribe_audio_file(input_file_path, language, overwrite=overwrite)
            case TranscriberType.LOCAL:
                srt_file_path = transcribe_file_with_default_model(input_file_path, language=language, mode=mode, overwrite=overwrite)
            case _:
                raise ValueError(f'Unsupported transcriber type: {transcriber}')
        if srt_file_path:
            print('Saved SRT file:', srt_file_path)
        else:
            print('Failed to transcribe file:', input_file_path)


def main() -> None:
    """
    CLI entry point to download videos with transcripts or transcribe/translate waveform files to SRT files.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("sources", nargs='+', metavar='source', help="Waveform file paths to transcribe/translate, or video/playlist URLs to download and transcribe/translate.")
    parser.add_argument("-l", "--language", type=LanguageCode.from_str, help="Language code for transcript download and transcription/translation.")
    parser.add_argument("-t", "--transcriber", type=TranscriberType, choices=TranscriberType.values(), default=TranscriberType.LOCAL, help="Transcriber to use for transcription. Defaults to `local`.")
    parser.add_argument("-m", "--mode", type=TranscriberMode, choices=TranscriberMode.values(), default=TranscriberMode.TRANSCRIBE, help="Whether to run Whisper in transcribe mode or translate mode. Defaults to `transcribe`.")
    parser.add_argument("-o", "--overwrite", type=OverwriteMode, choices=OverwriteMode.values(), default=OverwriteMode.PROMPT, help="Whether to overwrite existing SRT files. Defaults to `prompt`.")
    args = parser.parse_args()
    file_paths: Iterable[Path]
    file_paths, video_urls = tuple(map(list, more_itertools.partition(is_url, args.sources)))
    file_paths = itertools.chain(try_download_videos_and_transcripts(video_urls, args.language, args.overwrite), (Path(x) for x in file_paths))
    transcribe_to_srt_files(file_paths, args.language, args.transcriber, args.mode, args.overwrite)


if __name__ == "__main__":
    main()
