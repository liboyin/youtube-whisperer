import os
from pathlib import Path

import yt_dlp
from pathlib_extensions import (
    OverwritePolicy,
    StagedFile,
    prepare_output_file,
)

from youtube_whisperer.config import Settings
from youtube_whisperer.downloaders.utils import (
    build_youtube_dl_options,
    get_video_title_and_id,
    is_firefox_cookies_available,
    resolve_default_media_path,
)
from youtube_whisperer.overwrite import require_supported_policy, resolve_output_path


def download_video(url: str, target_path: Path, overwrite: OverwritePolicy) -> None:
    """
    Download into a `StagedFile` and atomically publish the literal target path.

    Failed downloads preserve previous output. NEVER also preserves competing
    files; ALWAYS replacements follow symlinks and retain mode bits. yt-dlp
    writes a fixed `video.mp4` inside the private stage directory, because a
    title in its output template would be expanded; the result is renamed to
    the staged name before publication. The stage directory, with any partial
    or auxiliary downloader files, is removed on every exit.

    Args:
        url (str): The URL of the video.
        target_path (Path): The path where the downloaded video will be saved.
        overwrite (OverwritePolicy): ALWAYS replaces an existing video; NEVER keeps it.

    Raises:
        ValueError: If `overwrite` is RENAME, or yt-dlp would expand environment variables in the stage path.
        FileNotFoundError: If the download leaves no regular staged video.
        OSError: If preparation, mode restoration, or atomic publication fails.
    """
    if resolve_output_path(target_path, overwrite) is None:
        return
    destination = prepare_output_file(target_path)
    # The generated stage directory name is safe, but its parent can contain expansions
    # that yt-dlp cannot escape. Check before the stage directory is created.
    template_parent = str(destination.resolve().parent / 'video.mp4')
    if os.path.expandvars(os.path.expanduser(template_parent)) != template_parent:
        raise ValueError('yt-dlp would expand the video stage directory path')
    with StagedFile(destination, overwrite) as staged:
        download = staged.path.parent / 'video.mp4'
        ydl_opts = build_youtube_dl_options(is_firefox_cookies_available())
        ydl_opts.update({
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]',
            'outtmpl': str(download).replace('%', '%%'),
        })
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        if not download.is_file():
            raise FileNotFoundError(f'Download did not produce a regular staged video: {download}')
        if download != staged.path:
            download.rename(staged.path)


def download_video_with_default_title(url: str, target_dir: Path | None = None, overwrite: OverwritePolicy = OverwritePolicy.NEVER) -> Path:
    """
    Download a video into the target directory under its default name, 'Title [videoID].mp4'.

    An existing title-only file from before video IDs were added is reused instead
    (see `resolve_default_media_path`).

    Args:
        url (str): The URL of the video to download.
        target_dir (Path, optional): The directory where the downloaded video will be saved. Defaults to settings resolved at invocation.
        overwrite (OverwritePolicy, optional): ALWAYS replaces an existing video; NEVER keeps it. Defaults to NEVER.

    Returns:
        Path: The path to the downloaded video file.

    Raises:
        ValueError: If `overwrite` is RENAME, before any other work.
    """
    require_supported_policy(overwrite)
    target_dir = target_dir if target_dir is not None else Settings().whisper_assets_dir
    title, video_id = get_video_title_and_id(url)
    target_path = resolve_default_media_path(target_dir, title, video_id, '.mp4')
    download_video(url, target_path, overwrite=overwrite)
    return target_path
