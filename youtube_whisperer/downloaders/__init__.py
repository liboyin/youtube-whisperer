from pathlib import Path
from typing import Iterable

from youtube_whisperer.downloaders.transcript_downloader import download_transcript_as_srt_file
from youtube_whisperer.downloaders.utils import yield_flattened_video_urls
from youtube_whisperer.downloaders.video_downloader import download_video_with_default_title
from youtube_whisperer.utils import WHISPER_HOME_DIR, WHISPER_OVERWRITE


# TODO: make lang_codes default to DEFAULT_LANG_CODES
def download_video_and_transcript_with_default_title(url: str, lang_codes: Iterable[str] | None = None, target_dir: Path = WHISPER_HOME_DIR, overwrite: bool = WHISPER_OVERWRITE) -> tuple[Path, bool]:
    """
    Downloads a YouTube video and its transcript from the given URL and saves it with a default title in the target directory.

    Args:
        url (str): The URL of the video to download.
        lang_codes (Iterable[str] | None): Language codes to filter available transcripts with. If None, use `DEFAULT_LANG_CODES`. Defaults to None.
        target_dir (Path, optional): The target directory where the videos and transcripts will be saved. Defaults to `DEFAULT_HOME_DIR`.
        overwrite (bool, optional): Whether to overwrite existing files. Defaults to `WHISPER_OVERWRITE`.

    Returns:
        tuple[Path, bool]: A tuple containing the path to the downloaded video file and a boolean indicating whether the transcript was successfully downloaded.
    """
    video_file_path = download_video_with_default_title(url, target_dir, overwrite)
    transcript_flag = download_transcript_as_srt_file(url, video_file_path.with_suffix('.srt'), lang_codes, overwrite)
    return video_file_path, transcript_flag


def download_videos_and_transcripts_with_default_titles(urls: Iterable[str], lang_codes: Iterable[str] | None = None, target_dir: Path = WHISPER_HOME_DIR, overwrite: bool = WHISPER_OVERWRITE) -> Iterable[tuple[Path, bool]]:
    """
    Downloads YouTube videos and their transcripts from the given URLs and saves them with their default titles in the target directory.

    Args:
        urls (Iterable[str]): An iterable of video URLs to download.
        lang_codes (Iterable[str] | None, optional): Language codes to filter available transcripts with. If None, use `DEFAULT_LANG_CODES`. Defaults to None.
        target_dir (Path, optional): The directory where the videos and transcripts will be saved. Defaults to `WHISPER_HOME_DIR`.
        overwrite (bool, optional): Whether to overwrite existing files. Defaults to `WHISPER_OVERWRITE`.

    Yields:
        Iterable[tuple[Path, bool]]: An iterable of tuples, each containing the path to the downloaded video and a boolean indicating whether the transcript was successfully downloaded.
    """
    for url in yield_flattened_video_urls(urls):
        yield download_video_and_transcript_with_default_title(url, lang_codes, target_dir, overwrite)
