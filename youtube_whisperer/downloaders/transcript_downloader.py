import argparse
from pathlib import Path
from typing import Collection, TypedDict
from urllib.parse import urlparse, parse_qs

from pathlib_extensions import prepare_output_file, replace_os_reserved_chars
from youtube_transcript_api import TranscriptsDisabled, YouTubeTranscriptApi
from youtube_transcript_api.formatters import SRTFormatter

from youtube_whisperer.downloaders.utils import get_video_title
from youtube_whisperer.utils import WHISPER_ASSETS_DIR, WHISPER_OVERWRITE

DEFAULT_LANG_CODES = 'en;zh'


class TranscriptBlock(TypedDict):
    text: str
    start: float
    end: float


def get_video_id(url: str) -> str:
    """
    Extracts the video ID from a YouTube video URL.
    
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


def get_first_matching_lang_code(candidate_lang_codes: Collection[str], requested_lang_codes: str) -> str | None:
    """
    Finds the first matching language code from the candidate language codes based on the requested language codes.

    Args:
        candidate_lang_codes (Collection[str]): Candidate language codes for a video.
        requested_lang_codes (str): Requested language codes separated by semicolons.

    Returns:
        str | None: The first matching language code from the candidate language codes, or None if no match is found.
    """
    print(f"Candidate language codes: {candidate_lang_codes}; requested language codes: {requested_lang_codes}")
    for request in requested_lang_codes.split(';'):
        if request:  # ignore empty language codes
            for candidate in candidate_lang_codes:
                if candidate.startswith(request):  # match dialects, e.g. en-US, zh-Hans
                    print("Matched language code:", candidate)
                    return candidate
    print("No matching language code found")
    return None


def download_transcript(url: str, lang_codes: str) -> list[TranscriptBlock] | None:
    """
    Downloads the transcript of a YouTube video.

    Args:
        url (str): The URL of the YouTube video.
        lang_codes (str): Language codes to filter available transcripts with.

    Returns:
        list[TranscriptBlock] | None: Downloaded transcript as a list of TranscriptBlock dicts.
            If no transcript in the requested language is available, return None.
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


def download_transcript_as_srt_text(url: str, lang_codes: str) -> str | None:
    """
    Downloads the transcript for a YouTube video and returns it as an SRT formatted text.

    Args:
        url (str): The URL of the YouTube video.
        lang_codes (str): Language codes to filter available transcripts with.

    Returns:
        str | None: The transcript as an SRT formatted text, or None if no transcript in the requested language is available.
    """
    transcript = download_transcript(url, lang_codes)
    if transcript is None:
        return None
    return SRTFormatter().format_transcript(transcript)


# TODO: is it possible to assign a default value to lang_codes here?
def download_transcript_as_srt_file(url: str, lang_codes: str, output_file_path: Path, overwrite: bool = WHISPER_OVERWRITE) -> bool:
    """
    Downloads the transcript of a YouTube video as an SRT file.

    Args:
        url (str): The URL of the YouTube video.
        lang_codes (str): Language codes to filter available transcripts with.
        output_file_path (Path): The path where the SRT file will be saved.
        overwrite (bool, optional): Whether to overwrite the transcript file if it already exists. Defaults to `WHISPER_OVERWRITE`.

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


def download_transcript_as_srt_file_with_default_title(url: str, lang_codes: str = DEFAULT_LANG_CODES, target_dir: Path = WHISPER_ASSETS_DIR, overwrite: bool = WHISPER_OVERWRITE) -> Path | None:
    """
    Downloads the transcript of a YouTube video as an SRT file named after the video title.

    Args:
        url (str): The URL of the YouTube video.
        lang_codes (str, optional): Language codes to filter available transcripts with. Defaults to `DEFAULT_LANG_CODES`.
        target_dir (Path, optional): The target directory where the SRT file will be saved. Defaults to `WHISPER_ASSET_DIR`.
        overwrite (bool, optional): Whether to overwrite the transcript file if it already exists. Defaults to `WHISPER_OVERWRITE`.

    Returns:
        Path | None: The path to the downloaded SRT file if successful, or None otherwise.
    """
    title = replace_os_reserved_chars(get_video_title(url))
    output_file_path = target_dir / f'{title}.srt'
    if download_transcript_as_srt_file(url, lang_codes, output_file_path, overwrite=overwrite):
        return output_file_path
    return None


def main() -> None:
    """
    CLI entry point to download video transcripts from URLs.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("urls", nargs='+', metavar='url', help="URLs of videos to download transcripts for.")
    parser.add_argument("-l", "--languages", type=str, default=DEFAULT_LANG_CODES, help="Candidate languages to download transcripts in. Defaults to DEFAULT_LANG_CODES.")
    parser.add_argument("-o", "--overwrite", action='store_true', default=WHISPER_OVERWRITE, help="Whether to overwrite existing SRT files. Defaults to WHISPER_OVERWRITE.")
    args = parser.parse_args()
    for url in args.urls:
        # do not verify language codes here because YouTube's language codes are not the same as Whisper's
        download_transcript_as_srt_file_with_default_title(url, args.languages, overwrite=args.overwrite)


if __name__ == '__main__':
    main()
