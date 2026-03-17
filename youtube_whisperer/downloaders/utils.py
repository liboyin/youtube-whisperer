from pathlib import Path

import yt_dlp


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
        'js_runtimes': {'deno': {}},
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)['title']


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
                print('Found Firefox cookies:', cookies_file_path)
                return True
    print('No Firefox cookies found')
    return False
