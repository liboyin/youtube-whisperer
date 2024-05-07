import argparse
from pathlib import Path
from typing import Collection, Iterable, TypedDict
from urllib.parse import urlparse, parse_qs

from youtube_transcript_api import TranscriptsDisabled, YouTubeTranscriptApi
from youtube_transcript_api.formatters import SRTFormatter

from youtube_whisperer.pathlib_extensions import prepare_output_file
from youtube_whisperer.utils import DEFAULT_HOME_DIR, replace_os_reserved_chars
from youtube_whisperer.video_downloader import get_video_title

DEFAULT_LANG_CODES = ('en', 'zh')


class TranscriptBlock(TypedDict):
    text: str
    start: float
    end: float


def get_video_id(url: str) -> str:
    """
    Extract the video ID from a YouTube video URL.
    
    Support URLs in the following formats:

        https://youtu.be/n9xhJrPXop4?si=sXdajbZPk7Bn2OjD&t=30
        https://www.youtube.com/watch?v=n9xhJrPXop4&si=sXdajbZPk7Bn2OjD&t=30
    
    Parameters:
        url (str): The YouTube video URL.
    
    Returns:
        str: The extracted video ID.
    
    Raises:
        ValueError: If the URL cannot be parsed.
    """
    parsed = urlparse(url)
    if parsed.netloc == 'youtu.be':
        return parsed.path.strip('/')
    if parsed.netloc == 'www.youtube.com':
        return parse_qs(parsed.query)['v'][0]
    raise ValueError(url)


def get_first_matching_lang_code(candidate_lang_codes: Collection[str], requested_lang_codes: Iterable[str]) -> str | None:
    """
    Finds the first matching language code from the candidate language codes based on the requested language codes.

    Args:
        candidate_lang_codes (Collection[str]): A collection of candidate language codes.
        requested_lang_codes (Iterable[str]): An iterable of requested language codes.

    Returns:
        str | None: The first matching language code from the candidate language codes, or None if no match is found.
    """
    print(f"Candidate language codes: {candidate_lang_codes}; requested language codes: {requested_lang_codes}")
    for request in requested_lang_codes:
        for candidate in candidate_lang_codes:
            if candidate.startswith(request):  # match dialects, e.g. en-US, zh-Hans
                print("Matched language code:", candidate)
                return candidate
    print("No matching language code found")
    return None


def download_transcript(url: str, lang_codes: Iterable[str] = DEFAULT_LANG_CODES) -> list[TranscriptBlock] | None:
    """
    Downloads the transcript of a YouTube video.

    Args:
        url (str): The URL of the YouTube video.
        lang_codes (Iterable[str], optional): A list of language codes to filter available transcripts. Defaults to DEFAULT_LANG_CODES.

    Returns:
        list[TranscriptBlock] | None: Downloaded transcript as a list of TranscriptBlock dicts, or None if no transcript in the requested language is available.
    """
    try:
        transcripts = YouTubeTranscriptApi.list_transcripts(get_video_id(url))
    except TranscriptsDisabled:
        print(f"Transcripts are disabled for {url}")
        return None
    lang_code = get_first_matching_lang_code([x.language_code for x in transcripts], lang_codes)
    if lang_code is None:
        return None
    result = transcripts.find_transcript([lang_code]).fetch()
    print(f"Successfully downloaded transcript with {len(result)} blocks for {url}")
    return result


def download_transcript_as_srt_text(url: str, lang_codes: Iterable[str] = DEFAULT_LANG_CODES) -> str | None:
    """
    Downloads the transcript for a YouTube video and returns it as an SRT formatted text.

    Args:
        url (str): The URL of the YouTube video.
        lang_codes (Iterable[str], optional): A list of language codes to filter available transcripts. Defaults to DEFAULT_LANG_CODES.

    Returns:
        str | None: The transcript as an SRT formatted text, or None if no transcript in the requested language is available.
    """
    transcript = download_transcript(url, lang_codes)
    if transcript is None:
        return None
    return SRTFormatter().format_transcript(transcript)


def download_transcript_as_srt_file(url: str, output_file_path: Path, lang_codes: Iterable[str] = DEFAULT_LANG_CODES) -> bool:
    """
    Downloads the transcript of a YouTube video as an SRT file.

    Args:
        url (str): The URL of the YouTube video.
        output_file_path (Path): The path where the SRT file will be saved.
        lang_codes (Iterable[str], optional): A list of language codes to filter available transcripts. Defaults to DEFAULT_LANG_CODES.

    Returns:
        bool: Whether the download is successful.
    """
    srt_text = download_transcript_as_srt_text(url, lang_codes)
    if srt_text is None:
        return False
    print("Writing SRT file:", output_file_path)
    prepare_output_file(output_file_path).write_text(srt_text)
    return True


def download_transcript_as_srt_file_with_default_title(url: str, target_dir: Path = DEFAULT_HOME_DIR, lang_codes: Iterable[str] = DEFAULT_LANG_CODES) -> Path | None:
    """
    Downloads the transcript of a YouTube video as an SRT file named after the video title.

    Args:
        url (str): The URL of the YouTube video.
        target_dir (Path, optional): The target directory where the SRT file will be saved. Defaults to DEFAULT_HOME_DIR.
        lang_codes (Iterable[str], optional): The language codes of the desired transcript. Defaults to DEFAULT_LANG_CODES.

    Returns:
        Path | None: The path to the downloaded SRT file if successful, or None otherwise.
    """
    title = replace_os_reserved_chars(get_video_title(url))
    output_file_path = target_dir / f'{title}.srt'
    if download_transcript_as_srt_file(url, output_file_path, lang_codes):
        return output_file_path
    return None


def main() -> None:
    """
    CLI entry point to download video transcripts from URLs.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("urls", nargs='+', metavar='N', help="URLs of videos to download transcripts for.")
    for url in parser.parse_args().urls:
        download_transcript_as_srt_file_with_default_title(url)

if __name__ == '__main__':
    main()
