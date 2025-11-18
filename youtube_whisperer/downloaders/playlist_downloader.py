import argparse
from pathlib import Path
from typing import Any, Generator, Iterable

from pathlib_extensions import OverwriteMode
import yt_dlp

from youtube_whisperer.downloaders.utils import is_firefox_cookies_available
from youtube_whisperer.downloaders.video_downloader import download_video_with_default_title
from youtube_whisperer.utils import WHISPER_ASSETS_DIR


def yield_video_urls_from_playlist(url: str) -> Generator[str, None, None]:
    """
    Extracts individual video URLs from a YouTube playlist. Uses Firefox cookies if available.
    
    Args:
        url (str): The URL of the YouTube playlist.
    
    Yields:
        Iterable[str]: An iterable of video URLs from the playlist.
    """
    ydl_opts: dict[str, Any] = {
        'extract_flat': True,
        'verbose': True,
        'js_runtimes': {'node': {}},
    }
    if is_firefox_cookies_available():
        ydl_opts['cookiesfrombrowser'] = ('firefox',)
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        videos = ydl.extract_info(url, download=False)['entries']
        print(f'{len(videos)} videos found in the playlist')
        for v in videos:
            yield f"https://www.youtube.com/watch?v={v['id']}"


def yield_flattened_video_urls(urls: Iterable[str]) -> Generator[str, None, None]:
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


def main() -> None:
    """
    CLI entry point to download videos from playlist URLs.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("urls", nargs='+', metavar='url', help="URLs of playlists to download.")
    parser.add_argument("-o", "--overwrite", type=OverwriteMode, choices=OverwriteMode.values(), default=OverwriteMode.PROMPT, help='Whether to overwrite existing video files. Defaults to `prompt`.')
    args = parser.parse_args()
    overwrite = args.overwrite
    for url in args.urls:
        download_playlist_with_default_titles(url, overwrite=overwrite)


if __name__ == "__main__":
    main()
