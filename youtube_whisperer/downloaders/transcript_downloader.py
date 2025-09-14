import argparse
from pathlib import Path
from typing import Collection, TypedDict
from urllib.parse import urlparse, parse_qs

from pathlib_extensions import OverwriteMode, overwrite_existing_path, prepare_output_file, replace_os_reserved_chars, truncate_filename
from youtube_transcript_api import FetchedTranscript, NoTranscriptFound, TranscriptsDisabled, YouTubeTranscriptApi
from youtube_transcript_api.formatters import SRTFormatter

from youtube_whisperer.adaptors.lang_code_adaptor import LanguageCode
from youtube_whisperer.downloaders.utils import get_video_title
from youtube_whisperer.utils import WHISPER_ASSETS_DIR


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


def get_first_matching_lang_code(candidates: Collection[str], requested: LanguageCode) -> str | None:
    """
    Finds the first matching language code from candidate language codes based on the requested language code.

    Args:
        candidates (Collection[str]): Candidate language codes for a video.
        requested (LanguageCode): Requested language code.

    Returns:
        str | None: The first matching language code from `candidates`, or `None` if no match is found.
    """
    for r in requested.get_source_as_BCP_and_ISO():
        r = r.lower()
        for c in candidates:
            if c.lower().startswith(r):
                print("Matched language code:", c)
                return c
    print("No matching language code found")
    return None


class TranscriptDownloader:
    def __init__(self, url: str, language: LanguageCode) -> None:
        self.url = url
        self.language = language

    def download(self) -> FetchedTranscript | None:
        """
        Downloads the transcript of a YouTube video.

        Returns:
            FetchedTranscript | None: Downloaded transcript, or `None` if no transcript in the requested language is available.
        """
        try:
            transcripts = YouTubeTranscriptApi().list(get_video_id(self.url))
        except TranscriptsDisabled:
            print(f"Transcripts are disabled for {self.url}")
            return None
        lang_code = get_first_matching_lang_code([x.language_code for x in transcripts], self.language)
        if lang_code is None:
            return None
        try:
            result = transcripts.find_transcript([lang_code]).fetch()
            print(f"Successfully downloaded transcript with {len(result)} blocks for {self.url}")
            return result
        except NoTranscriptFound:
            return None
    
    def download_as_srt_text(self) -> str | None:
        """
        Downloads the transcript of a YouTube video and returns it as SRT text.

        Returns:
            str | None: The transcript as an SRT formatted text, or None if no transcript in the requested language is available.
        """
        transcript = self.download()
        if transcript is None:
            return None
        return SRTFormatter().format_transcript(transcript)
    
    def download_as_srt_file(self, output_file_path: Path, overwrite: OverwriteMode = OverwriteMode.PROMPT) -> bool:
        """
        Downloads the transcript of a YouTube video as an SRT file.

        Args:
            output_file_path (Path): The path where the SRT file will be saved.
            overwrite (OverwriteMode): Whether to overwrite existing SRT files. Defaults to `prompt`.

        Returns:
            bool: Whether the download is successful.
        """
        if output_file_path.is_file() and not overwrite_existing_path(output_file_path, overwrite):
            return True
        srt_text = self.download_as_srt_text()
        if srt_text is None:
            return False
        print("About to write to SRT file:", output_file_path)
        prepare_output_file(output_file_path).write_text(srt_text)
        return True
    
    def download_as_srt_file_with_default_title(self, target_dir: Path = WHISPER_ASSETS_DIR, overwrite: OverwriteMode = OverwriteMode.PROMPT) -> Path | None:
        """
        Downloads the transcript of a YouTube video as an SRT file named after the video title.

        Args:
            target_dir (Path, optional): The target directory where the SRT file will be saved. Defaults to `WHISPER_ASSET_DIR`.
            overwrite (OverwriteMode, optional): Whether to overwrite existing SRT files. Defaults to `prompt`.

        Returns:
            Path | None: The path to the downloaded SRT file if successful, otherwise 'None'.
        """
        title = replace_os_reserved_chars(get_video_title(self.url))
        output_file_path = truncate_filename(target_dir / f'{title}.srt', max_length=220)
        if self.download_as_srt_file(output_file_path, overwrite=overwrite):
            return output_file_path
        return None


def main() -> None:
    """
    CLI entry point to download video transcripts from URLs.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("urls", nargs='+', metavar='url', help="URLs of videos to download transcripts for.")
    parser.add_argument("-l", "--language", type=LanguageCode, help="Requested transcript language to download.")
    parser.add_argument("-o", "--overwrite", type=OverwriteMode, choices=OverwriteMode.values(), default=OverwriteMode.PROMPT, help="Whether to overwrite existing SRT files. Defaults to `prompt`.")
    args = parser.parse_args()
    for url in args.urls:
        TranscriptDownloader(url, args.language).download_as_srt_file_with_default_title(overwrite=args.overwrite)


if __name__ == '__main__':
    main()
