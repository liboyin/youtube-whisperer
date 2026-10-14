import logging
import re
from functools import cache
from pathlib import Path

import yt_dlp
from pathlib_extensions import (
    build_filename,
    replace_os_reserved_chars,
    truncate_filename,
)

logger = logging.getLogger(__name__)

# Default media names stay below common 255-byte filename limits with room to spare.
DEFAULT_FILENAME_MAX_BYTES = 220
# A trailing ' [id]' shaped like a YouTube video ID, as default_media_filename appends it.
TRAILING_VIDEO_ID_TAG = re.compile(r' \[([0-9A-Za-z_-]{11})\]\Z')


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


def _extract_video_info(url: str) -> dict[str, object]:
    """
    Fetch a video's metadata through yt-dlp without downloading it.

    Args:
        url (str): The URL of the video.

    Returns:
        dict[str, object]: yt-dlp's information dictionary for the video.
    """
    ydl_opts = build_youtube_dl_options(is_firefox_cookies_available())
    ydl_opts['simulate'] = True
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)


def get_video_title(url: str) -> str:
    """
    Retrieves the title of a video given its URL.

    Args:
        url (str): The URL of the video.

    Returns:
        str: The title of the video.
    """
    return str(_extract_video_info(url)['title'])


def get_video_title_and_id(url: str) -> tuple[str, str]:
    """
    Retrieve the title and the extractor's ID of a video with one metadata request.

    Args:
        url (str): The URL of the video.

    Returns:
        tuple[str, str]: The video title and ID, such as the 11-character YouTube ID.
    """
    info = _extract_video_info(url)
    return str(info['title']), str(info['id'])


def default_media_filename(title: str, video_id: str, suffix: str) -> str:
    """
    Name a downloaded file after its video title and ID, such as 'Title [n9xhJrPXop4].mp4'.

    The ID keeps videos with equal titles apart (D47). Reserved characters are replaced, and
    only the title is truncated, so the ID and suffix always survive the byte limit.

    Args:
        title (str): The video title.
        video_id (str): The video ID; reserved characters in it are replaced as well.
        suffix (str): The file extension, such as '.mp4' or '.srt'.

    Returns:
        str: A filename of at most DEFAULT_FILENAME_MAX_BYTES bytes.

    Raises:
        ValueError: If no character of the title fits, for example an empty title.
    """
    tag = f' [{replace_os_reserved_chars(video_id)}]'
    return build_filename(title, suffix, tag=tag, max_length=DEFAULT_FILENAME_MAX_BYTES)


def legacy_media_filename(title: str, suffix: str) -> str | None:
    """
    Return the title-only name that downloads used before video IDs were added to names.

    Args:
        title (str): The video title.
        suffix (str): The file extension, such as '.mp4' or '.srt'.

    Returns:
        str | None: The legacy filename, or None when no legacy name could have existed.
    """
    try:
        path = truncate_filename(Path(replace_os_reserved_chars(title) + suffix), max_length=DEFAULT_FILENAME_MAX_BYTES)
    except ValueError:
        return None
    return path.name


def resolve_default_media_path(target_dir: Path, title: str, video_id: str, suffix: str) -> Path:
    """
    Choose where a video's default-named file lives in `target_dir`.

    The ID-tagged name is used unless only a legacy title-only file exists, which is then
    reused so earlier downloads are not repeated. That legacy match is by title alone, so
    it can still alias a different video with the same title (accepted in D47). A legacy
    name ending in another video's ID tag is never reused: it can be that video's tagged
    file, for example when this video's title is 'Title [aaaaaaaaaaa]'.

    Args:
        target_dir (Path): Directory holding the media library.
        title (str): The video title.
        video_id (str): The video ID.
        suffix (str): The file extension, such as '.mp4' or '.srt'.

    Returns:
        Path: The existing legacy file, or the ID-tagged path.

    Raises:
        ValueError: If no character of the title fits in the ID-tagged name.
    """
    path = target_dir / default_media_filename(title, video_id, suffix)
    if path.exists():
        return path
    legacy_name = legacy_media_filename(title, suffix)
    if legacy_name is None:
        return path
    tag = TRAILING_VIDEO_ID_TAG.search(Path(legacy_name).stem)
    if tag is not None and tag.group(1) != replace_os_reserved_chars(video_id):
        return path
    if (target_dir / legacy_name).is_file():
        return target_dir / legacy_name
    return path


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
