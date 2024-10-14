import argparse
import itertools
from pathlib import Path
from typing import Iterable

import more_itertools

from youtube_whisperer.downloaders import DEFAULT_LANG_CODES, download_videos_and_transcripts_with_default_titles
from youtube_whisperer.formatters.segment_to_srt_adaptor import convert_segments_file_to_srt
from youtube_whisperer.transcriber.waveform_transcriber import transcribe_file_with_default_model
from youtube_whisperer.utils import is_url, verify_language_code


def try_download_videos_and_transcripts(urls: Iterable[str], lang_codes: str | None) -> list[Path]:
    """
    Attempts to download videos and their transcripts from a list of URLs.

    Args:
        urls (Iterable[str]): An iterable of YouTube video or playlist URLs to download.
        lang_codes (str | None): Language codes to filter available transcripts with. If `None`, use `DEFAULT_LANG_CODES`.

    Returns:
        list[Path]: A list of Paths to video files that were downloaded but did not have transcripts.
    """
    lang_codes = lang_codes or DEFAULT_LANG_CODES
    video_files_without_transcripts: list[Path] = []
    for video_file_path, transcript_flag in download_videos_and_transcripts_with_default_titles(urls, lang_codes):
        if not transcript_flag:
            video_files_without_transcripts.append(video_file_path)
    return video_files_without_transcripts


def transcribe_to_srt_files(input_file_paths: Iterable[Path], language: str | None) -> None:
    """
    Transcribes a list of waveform files using the default model and converts the transcriptions to SRT format.

    Args:
        input_file_paths (Iterable[Path]): An iterable of waveform file paths to be transcribed.
        language (str | None): The language code for the transcription. If None, the language will be automatically detected.
    """
    for input_file_path in input_file_paths:
        segment_file_path = transcribe_file_with_default_model(input_file_path, language=language)
        print('Saved Segments file:', segment_file_path)
        srt_file_path = convert_segments_file_to_srt(segment_file_path)
        print('Saved SRT file:', srt_file_path)


def main() -> None:
    """
    CLI entry point to download videos with transcripts or transcribe waveform files to Segments and SRT files.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("sources", nargs='+', metavar='source', help="Waveform file paths to transcribe, or video/playlist URLs to download and transcribe.")
    parser.add_argument("-l", "--language", type=str, default=None, help="Language code for transcript download or waveform transcription.")
    args = parser.parse_args()
    file_paths, video_urls = tuple(map(list, more_itertools.partition(is_url, args.sources)))
    language = args.language
    verify_language_code(language)
    file_paths = itertools.chain(try_download_videos_and_transcripts(video_urls, language), (Path(x) for x in file_paths))
    transcribe_to_srt_files(file_paths, language)


if __name__ == "__main__":
    main()
