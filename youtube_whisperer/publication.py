"""Shared staged-file publication protocol for completed video, SRT and WAV output.

Callers own stage creation, ownership tracking and cleanup. These helpers own
the destination resolution, mode retention, create-if-absent and atomic
replacement rules of the completion contract described in DESIGN.md (D22).
"""
import os
import stat
from pathlib import Path

from pathlib_extensions import OverwriteMode, prepare_output_file


def resolve_publication_target(path: Path) -> tuple[Path, int | None]:
    """Resolve a prepared destination through symlinks and capture its mode bits.

    Args:
        path (Path): Literal destination already checked by `prepare_output_file`.

    Returns:
        tuple[Path, int | None]: The resolved target, prepared for output with
        parents created as needed, and its existing permission bits, or None
        when no file exists there yet.

    Raises:
        OSError: If the resolved target is not a writable file or cannot be inspected.
    """
    target = path.resolve()
    prepare_output_file(target)
    try:
        mode: int | None = stat.S_IMODE(target.stat().st_mode)
    except FileNotFoundError:
        mode = None
    return target, mode


def publish_staged_file(stage: Path, target: Path, mode: int | None, overwrite: OverwriteMode) -> None:
    """Publish a completed sibling stage to its resolved target.

    Applies captured mode bits to the stage first. NEVER and RENAME publish by
    same-filesystem hard-link create-if-absent, so a file created while staging,
    including a symlink to a file, is kept and the stage is not published; any
    other collision propagates. Other modes atomically replace the target inode.
    Replacement consumes the stage pathname; callers clean up any owned stage
    left behind.

    Args:
        stage (Path): Completed, caller-owned stage beside the target.
        target (Path): Destination from `resolve_publication_target`.
        mode (int | None): Permission bits to retain, or None to keep the stage's.
        overwrite (OverwriteMode): Policy deciding create-if-absent or replacement.

    Raises:
        FileExistsError: If create-if-absent collides with something other than a file.
        OSError: If mode restoration, linking (including unsupported hard links)
            or replacement fails, without falling back to another publication method.
    """
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
        stage.replace(target)
