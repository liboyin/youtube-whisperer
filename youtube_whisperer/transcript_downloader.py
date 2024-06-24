import argparse
from pathlib import Path
from typing import Collection, Iterable, TypedDict
from urllib.parse import urlparse, parse_qs

from pathlib_extensions import prepare_output_file
from youtube_transcript_api import TranscriptsDisabled, YouTubeTranscriptApi
from youtube_transcript_api.formatters import SRTFormatter

from youtube_whisperer.utils import DEFAULT_HOME_DIR, get_verified_language, replace_os_reserved_chars
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
        https://www.youtube.com/live/3TufaG29B7w?si=b5DQpvYgzcKJjJ0L
    
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
        if parsed.path == '/watch':
            return parse_qs(parsed.query)['v'][0]
        if parsed.path.startswith('/live/'):
            return parsed.path[6:]
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


def download_transcript(url: str, lang_codes: Iterable[str] | None = None) -> list[TranscriptBlock] | None:
    """
    Downloads the transcript of a YouTube video.

    Args:
        url (str): The URL of the YouTube video.
        lang_codes (Iterable[str] | None, optional): Language codes to filter available transcripts with.
            If None, use `DEFAULT_LANG_CODES`. Defaults to None.

    Returns:
        list[TranscriptBlock] | None: Downloaded transcript as a list of TranscriptBlock dicts.
            If no transcript in the requested language is available, return None.
    """
    if not lang_codes:  # note that the boolean value of an iterator is always True
        lang_codes = DEFAULT_LANG_CODES
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


def download_transcript_as_srt_text(url: str, lang_codes: Iterable[str] | None = None) -> str | None:
    """
    Downloads the transcript for a YouTube video and returns it as an SRT formatted text.

    Args:
        url (str): The URL of the YouTube video.
        lang_codes (Iterable[str] | None, optional): Language codes to filter available transcripts with.
            If None, fall back to `DEFAULT_LANG_CODES`. Defaults to None.

    Returns:
        str | None: The transcript as an SRT formatted text, or None if no transcript in the requested language is available.
    """
    transcript = download_transcript(url, lang_codes)
    if transcript is None:
        return None
    return SRTFormatter().format_transcript(transcript)


def download_transcript_as_srt_file(url: str, output_file_path: Path, lang_codes: Iterable[str] | None = None, overwrite: bool = False) -> bool:
    """
    Downloads the transcript of a YouTube video as an SRT file.

    Args:
        url (str): The URL of the YouTube video.
        output_file_path (Path): The path where the SRT file will be saved.
        lang_codes (Iterable[str] | None, optional): Language codes to filter available transcripts with.
            If None, use `DEFAULT_LANG_CODES`. Defaults to None.
        overwrite (bool, optional): Whether to overwrite the transcript file if it already exists. Defaults to False.

    Returns:
        bool: Whether the download is successful.
    """
    if not overwrite and output_file_path.is_file():
        print(f'Skipping download because the target transcript file already exists: {output_file_path}')
        return True
    srt_text = download_transcript_as_srt_text(url, lang_codes)
    if srt_text is None:
        return False
    print("About to write to SRT file:", output_file_path)
    prepare_output_file(output_file_path).write_text(srt_text)
    return True


def download_transcript_as_srt_file_with_default_title(url: str, target_dir: Path = DEFAULT_HOME_DIR, lang_codes: Iterable[str] | None = None, overwrite: bool = False) -> Path | None:
    """
    Downloads the transcript of a YouTube video as an SRT file named after the video title.

    Args:
        url (str): The URL of the YouTube video.
        target_dir (Path, optional): The target directory where the SRT file will be saved. Defaults to DEFAULT_HOME_DIR.
        lang_codes (Iterable[str] | None, optional): Language codes to filter available transcripts with.
            If None, use `DEFAULT_LANG_CODES`. Defaults to None.
        overwrite (bool, optional): Whether to overwrite the transcript file if it already exists. Defaults to False.

    Returns:
        Path | None: The path to the downloaded SRT file if successful, or None otherwise.
    """
    title = replace_os_reserved_chars(get_video_title(url))
    output_file_path = target_dir / f'{title}.srt'
    if download_transcript_as_srt_file(url, output_file_path, lang_codes, overwrite=overwrite):
        return output_file_path
    return None


def main() -> None:
    """
    CLI entry point to download video transcripts from URLs.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("urls", nargs='+', metavar='url', help="URLs of videos to download transcripts for.")
    parser.add_argument("-l", "--language", type=str, default=None, help="Language to download transcripts in. Defaults to DEFAULT_LANG_CODES.")
    lang_codes = None
    if language := get_verified_language(parser.parse_args().language):
        lang_codes = [language]
    for url in parser.parse_args().urls:
        download_transcript_as_srt_file_with_default_title(url, lang_codes=lang_codes)

if __name__ == '__main__':
    main()
