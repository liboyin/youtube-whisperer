import argparse
from pathlib import Path
from typing import Iterable

from youtube_whisperer.downloaders.playlist_downloader import yield_video_urls_from_playlist
from youtube_whisperer.downloaders.transcript_downloader import download_transcript_as_srt_file
from youtube_whisperer.downloaders.video_downloader import download_video_with_default_title
from youtube_whisperer.segment_to_srt_adaptor import convert_segments_file_to_srt
from youtube_whisperer.utils import is_url, get_verified_language
from youtube_whisperer.waveform_transcriber import transcribe_file_with_default_model


def get_urls_and_file_paths(sources: list[str]) -> tuple[list[str], list[Path]]:
    """
    Extract video URLs and waveform file paths from a list of sources.

    Args:
        sources (list[str]): A list containing video URLs, playlist URLs, or paths to waveform files.

    Returns:
        tuple[list[str], list[Path]]: A tuple containing a list of video URLs and a list of waveform file paths.
    """
    video_urls: list[str] = []
    file_paths: list[Path] = []
    for source in sources:
        if is_url(source):
            if 'playlist' in source:
                video_urls.extend(yield_video_urls_from_playlist(source))
            else:
                video_urls.append(source)
        else:
            file_paths.append(Path(source))
    return video_urls, file_paths


def download_video_and_transcript(url: str, lang_codes: Iterable[str] | None) -> tuple[Path, bool]:
    """
    Downloads a video and its transcript from a given URL.

    Args:
        url (str): The URL of the video to download.
        lang_codes (Iterable[str] | None): Language codes to filter available transcripts with. If None, use `DEFAULT_LANG_CODES`.

    Returns:
        tuple[Path, bool]: A tuple containing the path to the downloaded video file and a boolean indicating whether the transcript was successfully downloaded.
    """
    video_file_path = download_video_with_default_title(url)
    transcript_flag = download_transcript_as_srt_file(url, video_file_path.with_suffix('.srt'), lang_codes)
    return video_file_path, transcript_flag


def try_download_videos_and_transcripts(urls: Iterable[str], lang_codes: Iterable[str] | None) -> list[Path]:
    """
    Attempts to download videos and their transcripts from a list of URLs.

    Args:
        urls (Iterable[str]): A collection of video URLs to download.
        lang_codes (Iterable[str] | None): Language codes to filter available transcripts with. If None, use `DEFAULT_LANG_CODES`.

    Returns:
        list[Path]: A list of Paths to video files that were downloaded but did not have transcripts.
    """
    video_files_without_transcripts: list[Path] = []
    for url in urls:
        video_file_path, transcript_flag = download_video_and_transcript(url, lang_codes)
        if not transcript_flag:
            video_files_without_transcripts.append(video_file_path)
    return video_files_without_transcripts


def transcribe_to_srt_files(input_file_paths: Iterable[Path], language: str | None) -> None:
    """
    Transcribes a list of waveform files using the default model and converts the transcriptions to SRT format.

    Args:
        input_file_paths (Iterable[Path]): An iterable of file paths to the waveform files to be transcribed.
        language (str | None): The language code for the transcription. If None, the language will be automatically detected.
    """
    for input_file_path in input_file_paths:
        segment_file_path = transcribe_file_with_default_model(input_file_path, language=language)
        print('Saved Segments file:', segment_file_path)
        srt_file_path = convert_segments_file_to_srt(segment_file_path, deduplicate=True)
        print('Saved SRT file:', srt_file_path)


def main() -> None:
    """
    CLI entry point to transcribe waveform files and save each result to a Segment file and an SRT file.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("sources", nargs='+', metavar='source', help="Waveform file paths to transcribe, or video/playlist URLs to download and transcribe.")
    parser.add_argument("-l", "--language", type=str, default=None, help="Language for transcription")
    args = parser.parse_args()
    language = get_verified_language(args.language)
    video_urls, file_paths = get_urls_and_file_paths(args.sources)
    file_paths.extend(try_download_videos_and_transcripts(video_urls, [language] if language else None))
    transcribe_to_srt_files(file_paths, language)


if __name__ == "__main__":
    main()
