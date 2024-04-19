from pathlib import Path

import yt_dlp

from youtube_whisperer.pathlib_extensions import prepare_output_dir, prepare_output_file
from youtube_whisperer.utils import replace_os_reserved_chars


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


def download_video(url: str, target_path: Path) -> None:
    prepare_output_file(target_path)
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]',
        'outtmpl': str(target_path),
        'verbose': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])


def download_video_with_default_title(url: str, target_dir: Path | None = None) -> Path:
    target_dir = prepare_output_dir(target_dir or Path.cwd())
    title = replace_os_reserved_chars(get_video_title(url))
    target_path = target_dir / f'{title}.mp4'
    download_video(url, target_path)
    return target_path


if __name__ == '__main__':
    url = 'https://www.youtube.com/watch?v=8g18jFHCLXk'
    download_video_with_default_title(url, Path.home() / '.whisperer')
