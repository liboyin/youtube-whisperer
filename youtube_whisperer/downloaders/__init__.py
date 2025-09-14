from pathlib import Path

from pathlib_extensions import OverwriteMode

from youtube_whisperer.adaptors.lang_code_adaptor import LanguageCode
from youtube_whisperer.downloaders.transcript_downloader import TranscriptDownloader
from youtube_whisperer.downloaders.video_downloader import download_video_with_default_title
from youtube_whisperer.utils import WHISPER_ASSETS_DIR


def download_video_and_transcript_with_default_title(url: str, language: LanguageCode, target_dir: Path = WHISPER_ASSETS_DIR, overwrite: OverwriteMode = OverwriteMode.PROMPT) -> tuple[Path, bool]:
    """
    Downloads a YouTube video and its transcript from the given URL and saves it with a default title in the target directory.

    Args:
        url (str): The URL of the video to download.
        language (LanguageCode): Requested transcript language to download.
        target_dir (Path, optional): The target directory where the videos and transcripts will be saved. Defaults to `WHISPER_ASSET_DIR`.
        overwrite (OverwriteMode, optional): Whether to overwrite existing video and SRT files. Defaults to `prompt`.

    Returns:
        tuple[Path, bool]: A tuple containing the path to the downloaded video file and a boolean indicating whether the transcript was successfully downloaded.
    """
    video_file_path = download_video_with_default_title(url, target_dir, overwrite)
    transcript_flag = TranscriptDownloader(url, language).download_as_srt_file(video_file_path.with_suffix('.srt'), overwrite)
    return video_file_path, transcript_flag
