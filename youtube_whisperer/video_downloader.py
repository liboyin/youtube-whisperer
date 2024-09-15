import argparse
from pathlib import Path

from pathlib_extensions import prepare_output_file, replace_os_reserved_chars
import yt_dlp

from youtube_whisperer.utils import WHISPER_HOME_DIR, WHISPER_OVERWRITE, is_firefox_cookies_available


def get_video_title(url: str) -> str:
    """
    Retrieves the title of a video given its URL.

    Args:
        url (str): The URL of the video.

    Returns:
        str: The title of the video.
    """
    ydl_opts = {
        'simulate': True,
        'verbose': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)['title']


def download_video(url: str, target_path: Path, overwrite: bool = WHISPER_OVERWRITE) -> None:
    """
    Downloads a video from a given URL and saves it to the target path.

    Args:
        url (str): The URL of the video.
        target_path (Path): The path where the downloaded video will be saved.
        overwrite (bool, optional): Whether to overwrite the video file if it already exists. Defaults to WHISPER_OVERWRITE.
    """
    if not overwrite and target_path.is_file():
        print(f'Skipping download because the target video file already exists: {target_path}')
        return
    prepare_output_file(target_path)
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]',
        'outtmpl': str(target_path),
        'verbose': True,
    }
    if is_firefox_cookies_available():
        ydl_opts['cookiesfrombrowser'] = ('firefox',)
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])


def download_video_with_default_title(url: str, target_dir: Path = WHISPER_HOME_DIR, overwrite: bool = WHISPER_OVERWRITE) -> Path:
    """
    Downloads a video from the given URL and saves it with a default title in the target directory.

    Args:
        url (str): The URL of the video to download.
        target_dir (Path, optional): The directory where the downloaded video will be saved. Defaults to DEFAULT_HOME_DIR.
        overwrite (bool, optional): Whether to overwrite the video file if it already exists. Defaults to WHISPER_OVERWRITE.

    Returns:
        Path: The path to the downloaded video file.
    """
    title = replace_os_reserved_chars(get_video_title(url))
    target_path = target_dir / f'{title}.mp4'
    download_video(url, target_path, overwrite=overwrite)
    return target_path


def main() -> None:
    """
    CLI entry point to download videos from URLs.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("urls", nargs='+', metavar='url', help="URLs of videos to download.")
    parser.add_argument("-o", "--overwrite", action='store_true', default=WHISPER_OVERWRITE, help="Overwrite existing video files. Defaults to WHISPER_OVERWRITE.")
    args = parser.parse_args()
    for url in args.urls:
        download_video_with_default_title(url, overwrite=args.overwrite)

if __name__ == '__main__':
    main()
