"""Overwrite policies this application supports, and the existing-output preflight (D48)."""
from pathlib import Path

from pathlib_extensions import OverwritePolicy

__all__ = ['require_supported_policy', 'resolve_output_path']


def require_supported_policy(policy: OverwritePolicy) -> OverwritePolicy:
    """
    Return `policy` if this application can publish under it.

    Only the ALWAYS and NEVER members are supported (D49). The library's RENAME writes a
    numbered copy, such as 'Title [id].1.mp4', and a numbered SRT beside its video would break
    the MP4/SRT pairing that asset cleanup relies on. The library also publishes every other
    value, such as a stale `OverwriteMode` member or a plain string, the way it publishes
    RENAME. Members are compared by identity because those values compare equal to the
    policies they resemble. Public functions call this before any other work.

    Args:
        policy (OverwritePolicy): The requested policy.

    Returns:
        OverwritePolicy: `policy`, unchanged.

    Raises:
        ValueError: If `policy` is anything other than ALWAYS or NEVER.
    """
    if policy is OverwritePolicy.ALWAYS or policy is OverwritePolicy.NEVER:
        return policy
    raise ValueError(f'Overwrite policy {policy!r} is not supported: use OverwritePolicy.ALWAYS or NEVER')


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
        ValueError: If `policy` is anything other than ALWAYS or NEVER.
        NotAFileError: If something other than a file exists at `path`, following symlinks.
    """
    return require_supported_policy(policy).resolve(path)
