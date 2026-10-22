"""Overwrite policies this application supports, and the existing-output preflight (D48)."""
from pathlib import Path

from pathlib_extensions import OverwritePolicy

__all__ = ['require_supported_policy', 'resolve_output_path']


def require_supported_policy(policy: OverwritePolicy) -> OverwritePolicy:
    """
    Return `policy` if this application can publish under it.

    Only ALWAYS and NEVER are supported. The library's RENAME writes a numbered copy, such as
    'Title [id].1.mp4', and a numbered SRT beside its video would break the MP4/SRT pairing
    that asset cleanup relies on. Public functions call this before any other work.

    Args:
        policy (OverwritePolicy): The requested policy.

    Returns:
        OverwritePolicy: `policy`, unchanged.

    Raises:
        ValueError: If `policy` is RENAME.
    """
    if policy is OverwritePolicy.RENAME:
        raise ValueError('OverwritePolicy.RENAME is not supported: use ALWAYS or NEVER')
    return policy


def resolve_output_path(path: Path, policy: OverwritePolicy) -> Path | None:
    """
    Decide before any expensive work whether output may be written at `path`.

    Delegates to `OverwritePolicy.resolve` after `require_supported_policy`, so a rejected
    policy fails before anything is downloaded, converted or transcribed.

    Args:
        path (Path): Destination of the planned write.
        policy (OverwritePolicy): ALWAYS or NEVER.

    Returns:
        Path | None: `path`, or None when NEVER finds an existing file, or a symlink to one,
        that must be kept.

    Raises:
        ValueError: If `policy` is RENAME.
        NotAFileError: If something other than a file exists at `path`, following symlinks.
    """
    return require_supported_policy(policy).resolve(path)
