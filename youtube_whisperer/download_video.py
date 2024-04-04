from pathlib import Path

import yt_dlp

from utils import remove_os_reserved_chars


def get_video_title(url: str) -> str:
    """
    Retrieves the title of a YouTube video given its URL.

    Args:
        url (str): The URL of the YouTube video.

    Returns:
        str: The title of the YouTube video.
    """
    ydl_opts = {
        'simulate': True,
        'verbose': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)['title']


def download_video(url: str, title: str) -> Path:
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]',
        'outtmpl': f'{title}.%(ext)s',
        'verbose': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    return Path(f'{title}.mp4')


def download_video_with_default_title(url: str) -> Path:
    title = remove_os_reserved_chars(get_video_title(url))
    return download_video(url, title)
