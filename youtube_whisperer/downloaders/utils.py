from pathlib import Path
from typing import Iterable

import yt_dlp

from youtube_whisperer.downloaders.playlist_downloader import yield_video_urls_from_playlist


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


def yield_flattened_video_urls(urls: Iterable[str]) -> Iterable[str]:
    """
    Yields individual YouTube video URLs from an iterable of URLs, flattening any playlist URLs.

    Args:
        urls (Iterable[str]): An iterable of YouTube URLs, which may include individual video URLs or playlist URLs.

    Yields:
        Iterable[str]: An iterable of individual YouTube video URLs.
    """
    for url in urls:
        if 'playlist' in url:
            yield from yield_video_urls_from_playlist(url)
        else:
            yield url


def is_firefox_cookies_available() -> bool:
    """
    Return whether the Firefox cookies file is available in the file system.
    """
    for search_dir_path in [
        '~/.mozilla/firefox',
        '~/snap/firefox/common/.mozilla/firefox',
        '~/.var/app/org.mozilla.firefox/.mozilla/firefox',
    ]:
        for cookies_file_path in Path(search_dir_path).expanduser().rglob('cookies.sqlite'):
            if cookies_file_path.is_file():
                print('Found Firefox cookies:', cookies_file_path)
                return True
    print('No Firefox cookies found')
    return False
