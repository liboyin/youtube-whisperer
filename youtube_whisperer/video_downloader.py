import argparse
from pathlib import Path

import yt_dlp

from youtube_whisperer.pathlib_extensions import prepare_output_dir, prepare_output_file
from youtube_whisperer.utils import DEFAULT_HOME_DIR, replace_os_reserved_chars


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


def download_video(url: str, target_path: Path) -> None:
    """
    Downloads a video from a given URL and saves it to the target path.

    Args:
        url (str): The URL of the video.
        target_path (Path): The path where the downloaded video will be saved.
    """
    prepare_output_file(target_path)
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]',
        'outtmpl': str(target_path),
        'verbose': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])


def download_video_with_default_title(url: str, target_dir: Path = DEFAULT_HOME_DIR) -> Path:
    """
    Downloads a video from the given URL and saves it with a default title in the target directory.

    Args:
        url (str): The URL of the video to download.
        target_dir (Path, optional): The directory where the downloaded video will be saved. Defaults to DEFAULT_HOME_DIR.

    Returns:
        Path: The path to the downloaded video file.
    """
    title = replace_os_reserved_chars(get_video_title(url))
    target_path = prepare_output_dir(target_dir) / f'{title}.mp4'
    download_video(url, target_path)
    return target_path


def main() -> None:
    """
    CLI entry point of the video downloader.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("url", help="The URL of the video to download.")
    download_video_with_default_title(parser.parse_args().url)

if __name__ == '__main__':
    main()
