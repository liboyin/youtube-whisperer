import logging
from pathlib import Path

from pathlib_extensions import OverwritePolicy
from requests import RequestException
from youtube_transcript_api import YouTubeTranscriptApiException

from youtube_whisperer.adaptors.lang_code_adaptor import LanguageCode
from youtube_whisperer.config import Settings
from youtube_whisperer.downloaders.transcript_downloader import TranscriptDownloader
from youtube_whisperer.downloaders.video_downloader import (
    download_video_with_default_title,
)
from youtube_whisperer.overwrite import require_supported_policy

logger = logging.getLogger(__name__)


def download_video_and_transcript_with_default_title(url: str, language: LanguageCode, target_dir: Path | None = None, overwrite: OverwritePolicy = OverwritePolicy.NEVER) -> tuple[Path, bool]:
    """
    Download media first, then attempt captions using the media file's default title.

    Caption-service failures are logged with the URL and traceback, and treated
    as missing captions so the caller can complete or request transcription.
    Media-download, local publication, parser and programming errors propagate.

    Args:
        url (str): The URL of the video to download.
        language (LanguageCode): Requested transcript language to download.
        target_dir (Path, optional): The target directory where the videos and transcripts will be saved. Defaults to settings resolved at invocation.
        overwrite (OverwritePolicy, optional): ALWAYS replaces existing video and SRT files; NEVER keeps them. Defaults to NEVER.

    Returns:
        tuple[Path, bool]: A tuple containing the path to the downloaded video file and a boolean indicating whether the transcript was successfully downloaded.

    Raises:
        ValueError: If `overwrite` is not ALWAYS or NEVER, before any other work.
    """
    require_supported_policy(overwrite)
    target_dir = target_dir if target_dir is not None else Settings().whisper_assets_dir
    video_file_path = download_video_with_default_title(url, target_dir, overwrite)
    try:
        transcript_flag = TranscriptDownloader(url, language).download_as_srt_file(video_file_path.with_suffix('.srt'), overwrite)
    except (YouTubeTranscriptApiException, RequestException):
        logger.warning("Caption service failed for %s; treating captions as missing", url, exc_info=True)
        transcript_flag = False
    return video_file_path, transcript_flag
