import os
import shutil
import stat
import tempfile
from pathlib import Path

import yt_dlp
from pathlib_extensions import (
    OverwriteMode,
    overwrite_existing_path,
    prepare_output_file,
    replace_os_reserved_chars,
    truncate_filename,
)

from youtube_whisperer.config import Settings
from youtube_whisperer.downloaders.utils import (
    build_youtube_dl_options,
    get_video_title,
    is_firefox_cookies_available,
)


def download_video(url: str, target_path: Path, overwrite: OverwriteMode) -> None:
    """
    Download to an owned stage and atomically publish the literal target path.

    Failed downloads preserve previous output. NEVER and RENAME also preserve
    competing files; approved replacements follow symlinks and retain mode bits.
    The stage directory is removed on normal return and exception unwinding.

    Args:
        url (str): The URL of the video.
        target_path (Path): The path where the downloaded video will be saved.
        overwrite (OverwriteMode): Whether to overwrite existing video files.

    Raises:
        ValueError: If yt-dlp would expand environment variables in the stage path.
        FileNotFoundError: If the download leaves no regular staged video.
        OSError: If preparation, mode restoration, or atomic publication fails.
    """
    if target_path.is_file() and not overwrite_existing_path(target_path, overwrite):
        return
    target = prepare_output_file(target_path).resolve()
    prepare_output_file(target)
    try:
        mode = stat.S_IMODE(target.stat().st_mode)
    except FileNotFoundError:
        mode = None
    # The generated stage name is safe, but its parent can contain expansions
    # that yt-dlp cannot escape. Check before acquiring the stage directory.
    template_parent = str(target.parent / 'video.mp4')
    if os.path.expandvars(os.path.expanduser(template_parent)) != template_parent:
        raise ValueError('yt-dlp would expand the video stage directory path')
    stage_dir = Path(tempfile.mkdtemp(prefix='.video-', dir=target.parent))
    stage = stage_dir / 'video.mp4'
    try:
        ydl_opts = build_youtube_dl_options(is_firefox_cookies_available())
        ydl_opts.update({
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]',
            'outtmpl': str(stage).replace('%', '%%'),
        })
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        if not stage.is_file():
            raise FileNotFoundError(f'Download did not produce a regular staged video: {stage}')
        if mode is not None:
            stage.chmod(mode)
        if overwrite in (OverwriteMode.NEVER, OverwriteMode.RENAME):
            try:
                os.link(stage, target)
            except FileExistsError:
                if target.is_file():
                    return
                raise
        else:
            os.replace(stage, target)
    finally:
        shutil.rmtree(stage_dir)


def download_video_with_default_title(url: str, target_dir: Path | None = None, overwrite: OverwriteMode = OverwriteMode.PROMPT) -> Path:
    """
    Downloads a video from the given URL and saves it with a default title in the target directory.

    Args:
        url (str): The URL of the video to download.
        target_dir (Path, optional): The directory where the downloaded video will be saved. Defaults to settings resolved at invocation.
        overwrite (OverwriteMode, optional): Whether to overwrite existing video files. Defaults to `prompt`.

    Returns:
        Path: The path to the downloaded video file.
    """
    target_dir = target_dir if target_dir is not None else Settings().whisper_assets_dir
    title = replace_os_reserved_chars(get_video_title(url))
    target_path = truncate_filename(target_dir / f'{title}.mp4', max_length=220)
    download_video(url, target_path, overwrite=overwrite)
    return target_path
