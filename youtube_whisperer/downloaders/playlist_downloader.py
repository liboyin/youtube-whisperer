from pathlib import Path
from typing import Any, Generator, Iterable

from pathlib_extensions import OverwriteMode
import yt_dlp

from youtube_whisperer.downloaders.utils import is_firefox_cookies_available
from youtube_whisperer.downloaders.video_downloader import download_video_with_default_title
from youtube_whisperer.utils import WHISPER_ASSETS_DIR


def extract_flat_info(url: str) -> dict[str, Any] | None:
    """Flat-extract a YouTube URL's metadata without downloading. Uses Firefox cookies if available.

    Flat extraction resolves a playlist, channel, or tab into a shallow list of entries and a
    single video into a bare info dict, without fetching each video's full metadata.

    Args:
        url (str): The YouTube URL to inspect (a single video, playlist, channel, or tab).

    Returns:
        dict[str, Any] | None: The yt-dlp info dict, or ``None`` if extraction yielded nothing.
    """
    ydl_opts: dict[str, Any] = {
        'extract_flat': True,
        'verbose': True,
        'js_runtimes': {'deno': {}},
    }
    if is_firefox_cookies_available():
        ydl_opts['cookiesfrombrowser'] = ('firefox',)
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)


def yield_video_urls_from_info(info: dict[str, Any] | None, url: str) -> Generator[str, None, None]:
    """Yield the concrete video URLs described by a flat-extracted info dict.

    A single video (a bare info dict without an ``entries`` key) yields the original URL. A
    playlist, channel, or tab (an info dict with an ``entries`` list) yields one watch URL per
    contained video, skipping ``None`` entries and entries without an ``id`` (deleted or private
    videos).

    Args:
        info (dict[str, Any] | None): The dict returned by ``extract_flat_info``, or ``None``.
        url (str): The original URL, used both as the single-video result and in the error message.

    Yields:
        str: One video URL per contained (or single) video.

    Raises:
        ValueError: If ``info`` is ``None`` because extraction resolved to nothing.
    """
    if info is None:
        raise ValueError(f"Failed to extract any video information from {url}")
    entries = info.get('entries')
    if entries is None:
        # A single video: yt-dlp returns a bare info dict with no 'entries'.
        yield url
        return
    for entry in entries:
        if entry is None:  # deleted or private video inside the playlist/channel
            continue
        if video_id := entry.get('id'):
            yield f"https://www.youtube.com/watch?v={video_id}"


def yield_video_urls_from_playlist(url: str) -> Generator[str, None, None]:
    """Expand a playlist, channel, or tab URL into its individual video URLs.

    A single-video URL passes through as itself; a multi-video URL is flattened into one watch
    URL per contained video. Uses Firefox cookies if available.

    Args:
        url (str): The URL of the YouTube playlist, channel, tab, or single video.

    Yields:
        str: An individual video URL for each contained (or single) video.
    """
    yield from yield_video_urls_from_info(extract_flat_info(url), url)


def yield_flattened_video_urls(urls: Iterable[str]) -> Generator[str, None, None]:
    """
    Yields individual YouTube video URLs from an iterable of URLs, flattening any playlist, channel, or tab URLs.

    Each URL is flat-extracted and branched on whether it resolves to multiple videos (a playlist,
    channel, or tab) or a single video, so channel and tab URLs are handled correctly.

    Args:
        urls (Iterable[str]): An iterable of YouTube URLs, which may include individual video URLs or playlist/channel URLs.

    Yields:
        Iterable[str]: An iterable of individual YouTube video URLs.
    """
    for url in urls:
        yield from yield_video_urls_from_playlist(url)


def download_playlist_with_default_titles(url: str, target_dir: Path = WHISPER_ASSETS_DIR, overwrite: OverwriteMode = OverwriteMode.PROMPT) -> list[Path]:
    """
    Downloads all videos in a YouTube playlist and saves them with default titles in the target directory.
    
    Args:
        url (str): The URL of the YouTube playlist.
        target_dir (Path, optional): The directory where the downloaded videos will be saved. Defaults to `WHISPER_ASSET_DIR`.
        overwrite (OverwriteMode, optional): Whether to overwrite existing video files. Defaults to `prompt`.
    
    Returns:
        list[Path]: A list of paths to downloaded video files.
    """
    return [download_video_with_default_title(v, target_dir, overwrite) for v in yield_video_urls_from_playlist(url)]
