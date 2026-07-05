from pathlib import Path

from pathlib_extensions import OverwriteMode, overwrite_existing_path, prepare_output_file, replace_os_reserved_chars, truncate_filename
import yt_dlp

from youtube_whisperer.downloaders.utils import get_video_title, is_firefox_cookies_available
from youtube_whisperer.utils import WHISPER_ASSETS_DIR


def download_video(url: str, target_path: Path, overwrite: OverwriteMode) -> None:
    """
    Downloads a video from a given URL and saves it to the target path.

    Args:
        url (str): The URL of the video.
        target_path (Path): The path where the downloaded video will be saved.
        overwrite (OverwriteMode): Whether to overwrite existing video files.
    """
    if target_path.is_file() and not overwrite_existing_path(target_path, overwrite):
        return
    prepare_output_file(target_path)
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]',
        'outtmpl': str(target_path),
        'verbose': True,
        'js_runtimes': {'deno': {}},
    }
    if is_firefox_cookies_available():
        ydl_opts['cookiesfrombrowser'] = ('firefox',)
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])


def download_video_with_default_title(url: str, target_dir: Path = WHISPER_ASSETS_DIR, overwrite: OverwriteMode = OverwriteMode.PROMPT) -> Path:
    """
    Downloads a video from the given URL and saves it with a default title in the target directory.

    Args:
        url (str): The URL of the video to download.
        target_dir (Path, optional): The directory where the downloaded video will be saved. Defaults to `WHISPER_ASSET_DIR`.
        overwrite (OverwriteMode, optional): Whether to overwrite existing video files. Defaults to `prompt`.

    Returns:
        Path: The path to the downloaded video file.
    """
    title = replace_os_reserved_chars(get_video_title(url))
    target_path = truncate_filename(target_dir / f'{title}.mp4', max_length=220)
    download_video(url, target_path, overwrite=overwrite)
    return target_path
