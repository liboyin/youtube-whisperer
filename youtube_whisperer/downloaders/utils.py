import logging
from functools import cache
from pathlib import Path

import yt_dlp

logger = logging.getLogger(__name__)


def build_youtube_dl_options(cookies_available: bool) -> dict[str, object]:
    """Build independent baseline options without discovering browser profiles.

    Args:
        cookies_available: Whether the caller's cookie discovery found Firefox cookies.

    Returns:
        A fresh options dictionary with a fresh nested Deno runtime mapping.
    """
    options: dict[str, object] = {
        'verbose': True,
        'js_runtimes': {'deno': {}},
    }
    if cookies_available:
        options['cookiesfrombrowser'] = ('firefox',)
    return options


def get_video_title(url: str) -> str:
    """
    Retrieves the title of a video given its URL.

    Args:
        url (str): The URL of the video.

    Returns:
        str: The title of the video.
    """
    ydl_opts = build_youtube_dl_options(is_firefox_cookies_available())
    ydl_opts['simulate'] = True
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)['title']


@cache
def is_firefox_cookies_available() -> bool:
    """
    Returns whether the Firefox cookies file is available in the file system.
    """
    for search_dir_path in [
        '~/.mozilla/firefox',
        '~/snap/firefox/common/.mozilla/firefox',
        '~/.var/app/org.mozilla.firefox/.mozilla/firefox',
    ]:
        for cookies_file_path in Path(search_dir_path).expanduser().rglob('cookies.sqlite'):
            if cookies_file_path.is_file():
                logger.info("Found Firefox cookies: %s", cookies_file_path)
                return True
    logger.info("No Firefox cookies found")
    return False
