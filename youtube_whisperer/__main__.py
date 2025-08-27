import argparse
import itertools
from pathlib import Path
from typing import Iterable

import more_itertools
from pathlib_extensions import OverwriteMode

from youtube_whisperer.downloaders import DEFAULT_LANG_CODES, download_videos_and_transcripts_with_default_titles
from youtube_whisperer.formatters.segment_to_srt_adaptor import convert_segments_file_to_srt
from youtube_whisperer.transcriber.waveform_transcriber import transcribe_file_with_default_model
from youtube_whisperer.utils import TranscriberMode, is_url, verify_language_code


# Note that lang_codes cannot default to DEFAULT_LANG_CODES because the value is shared with transcribe_to_srt_files(), and Whisper only accepts up to one language code.
def try_download_videos_and_transcripts(urls: Iterable[str], lang_codes: str | None = None, overwrite: OverwriteMode = OverwriteMode.PROMPT) -> list[Path]:
    """
    Attempts to download videos and their transcripts from a list of URLs.

    Args:
        urls (Iterable[str]): An iterable of YouTube video or playlist URLs to download.
        lang_codes (str | None, optional): Language codes to filter available transcripts with. If `None`, use `DEFAULT_LANG_CODES`. Defaults to `None`.
        overwrite (OverwriteMode, optional): Whether to overwrite existing video & SRT files. Defaults to `prompt`.

    Returns:
        list[Path]: A list of Paths to video files that were downloaded but did not have transcripts.
    """
    lang_codes = lang_codes or DEFAULT_LANG_CODES
    video_files_without_transcripts: list[Path] = []
    for video_file_path, transcript_flag in download_videos_and_transcripts_with_default_titles(urls, lang_codes, overwrite=overwrite):
        if not transcript_flag:
            video_files_without_transcripts.append(video_file_path)
    return video_files_without_transcripts


def transcribe_to_srt_files(input_file_paths: Iterable[Path], language: str | None = None, mode: TranscriberMode = TranscriberMode.TRANSCRIBE, overwrite: OverwriteMode = OverwriteMode.PROMPT) -> None:
    """
    Transcribes a list of waveform files using the default model and converts the transcriptions to SRT format.

    Args:
        input_file_paths (Iterable[Path]): An iterable of waveform file paths to be transcribed.
        language (str | None, optional): The language code for the transcription. If `None`, the language will be automatically detected. Defaults to `None`.
        mode (TranscriberMode, optional): Whether to run Whisper in transcribe mode or translate mode. Defaults to `transcribe`.
        overwrite (OverwriteMode, optional): Whether to overwrite existing Segment & SRT files. Defaults to `prompt`.
    """
    for input_file_path in input_file_paths:
        if segment_file_path := transcribe_file_with_default_model(input_file_path, language=language, mode=mode, overwrite=overwrite):
            print('Saved Segments file:', segment_file_path)
            srt_file_path = convert_segments_file_to_srt(segment_file_path, overwrite=overwrite)
            print('Saved SRT file:', srt_file_path)
        else:
            print('Failed to transcribe file:', input_file_path)


def main() -> None:
    """
    CLI entry point to download videos with transcripts or transcribe waveform files to Segments and SRT files.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("sources", nargs='+', metavar='source', help="Waveform file paths to transcribe, or video/playlist URLs to download and transcribe.")
    # Language cannot default to empty string because Whisper uses None for auto-detect language, whereas empty string is not a valid language code.
    parser.add_argument("-l", "--language", type=str, default=None, help="Language code for transcript download or waveform transcription.")
    parser.add_argument("-m", "--mode", type=TranscriberMode, choices=TranscriberMode.values(), default=TranscriberMode.TRANSCRIBE, help="Whether to run Whisper in transcribe mode or translate mode. Defaults to `transcribe`.")
    parser.add_argument("-o", "--overwrite", type=OverwriteMode, choices=OverwriteMode.values(), default=OverwriteMode.PROMPT, help="Whether to overwrite existing Segment files. Defaults to `prompt`.")
    args = parser.parse_args()
    file_paths: Iterable[Path]
    file_paths, video_urls = tuple(map(list, more_itertools.partition(is_url, args.sources)))
    language = args.language
    verify_language_code(language)
    overwrite = args.overwrite
    file_paths = itertools.chain(try_download_videos_and_transcripts(video_urls, language, overwrite), (Path(x) for x in file_paths))
    transcribe_to_srt_files(file_paths, language, TranscriberMode(args.mode), overwrite)


if __name__ == "__main__":
    main()
