import argparse
from pathlib import Path
from typing import Any

import yt_dlp

from youtube_whisperer.utils import WHISPER_HOME_DIR, is_firefox_cookies_available
from youtube_whisperer.video_downloader import download_video_with_default_title


def get_video_urls_from_playlist(url: str) -> list[str]:
    """
    Extract individual video URLs from a YouTube playlist.
    
    Args:
        url (str): The URL of the YouTube playlist.
    
    Returns:
        List[str]: A list of individual video URLs.
    """
    ydl_opts: dict[str, Any] = {
        'extract_flat': True,
        'verbose': True,
    }
    if is_firefox_cookies_available():
        ydl_opts['cookiesfrombrowser'] = ('firefox',)
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        videos = ydl.extract_info(url, download=False)['entries']
        print(f'{len(videos)} videos found in the playlist')
        return [f"https://www.youtube.com/watch?v={v['id']}" for v in videos]


def download_playlist_with_default_title(url: str, target_dir: Path = WHISPER_HOME_DIR, overwrite: bool = False) -> list[Path]:
    """
    Downloads all videos in a YouTube playlist and saves them with default titles in the target directory.
    
    Args:
        url (str): The URL of the YouTube playlist.
        target_dir (Path, optional): The directory where the downloaded videos will be saved. Defaults to DEFAULT_HOME_DIR.
        overwrite (bool, optional): Whether to overwrite the video files if they already exist. Defaults to False.
    
    Returns:
        List[Path]: A list of paths to downloaded video files.
    """
    return [download_video_with_default_title(v, target_dir, overwrite) for v in get_video_urls_from_playlist(url)]


def main() -> None:
    """
    CLI entry point to download videos from playlist URLs.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("urls", nargs='+', metavar='url', help="URLs of playlists to download.")
    parser.add_argument("-o", "--overwrite", action='store_true', default=False, help="Overwrite existing video files.")
    args = parser.parse_args()
    for url in args.urls:
        download_playlist_with_default_title(url, overwrite=args.overwrite)

if __name__ == "__main__":
    main()
