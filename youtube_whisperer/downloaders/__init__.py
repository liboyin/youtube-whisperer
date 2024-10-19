from pathlib import Path
from typing import Iterable

from pathlib_extensions import OverwriteMode

from youtube_whisperer.downloaders.playlist_downloader import yield_flattened_video_urls
from youtube_whisperer.downloaders.transcript_downloader import DEFAULT_LANG_CODES, download_transcript_as_srt_file
from youtube_whisperer.downloaders.video_downloader import download_video_with_default_title
from youtube_whisperer.utils import WHISPER_ASSETS_DIR


def download_video_and_transcript_with_default_title(url: str, lang_codes: str = DEFAULT_LANG_CODES, target_dir: Path = WHISPER_ASSETS_DIR, overwrite: OverwriteMode = OverwriteMode.PROMPT) -> tuple[Path, bool]:
    """
    Downloads a YouTube video and its transcript from the given URL and saves it with a default title in the target directory.

    Args:
        url (str): The URL of the video to download.
        lang_codes (str, optional): Language codes to filter available transcripts with. Defaults to `DEFAULT_LANG_CODES`.
        target_dir (Path, optional): The target directory where the videos and transcripts will be saved. Defaults to `WHISPER_ASSET_DIR`.
        overwrite (OverwriteMode, optional): Whether to overwrite existing video and SRT files. Defaults to `OverwriteMode.PROMPT`.

    Returns:
        tuple[Path, bool]: A tuple containing the path to the downloaded video file and a boolean indicating whether the transcript was successfully downloaded.
    """
    video_file_path = download_video_with_default_title(url, target_dir, overwrite)
    transcript_flag = download_transcript_as_srt_file(url, lang_codes, video_file_path.with_suffix('.srt'), overwrite)
    return video_file_path, transcript_flag


def download_videos_and_transcripts_with_default_titles(urls: Iterable[str], lang_codes: str = DEFAULT_LANG_CODES, target_dir: Path = WHISPER_ASSETS_DIR, overwrite: OverwriteMode = OverwriteMode.PROMPT) -> Iterable[tuple[Path, bool]]:
    """
    Downloads YouTube videos and their transcripts from the given URLs and saves them with their default titles in the target directory.

    Args:
        urls (Iterable[str]): An iterable of video URLs to download.
        lang_codes (str, optional): Language codes to filter available transcripts with. Defaults `DEFAULT_LANG_CODES`.
        target_dir (Path, optional): The directory where the videos and transcripts will be saved. Defaults to `WHISPER_ASSET_DIR`.
        overwrite (OverwriteMode, optional): Whether to overwrite existing video and SRT files. Defaults to `OverwriteMode.PROMPT`.

    Yields:
        Iterable[tuple[Path, bool]]: An iterable of tuples, each containing the path to the downloaded video and a boolean indicating whether the transcript was successfully downloaded.
    """
    for url in yield_flattened_video_urls(urls):
        yield download_video_and_transcript_with_default_title(url, lang_codes, target_dir, overwrite)
