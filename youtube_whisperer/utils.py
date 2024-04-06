import re

from pathlib import Path

AnyPath = str | Path


def remove_os_reserved_chars(text):
    """
    Removes OS reserved characters from the given text.

    Should work on Windows, Linux, and macOS.

    Args:
        text (str): The input text.

    Returns:
        str: The modified text with reserved characters replaced by underscores.
    """
    return re.sub(r'[\\/*?:"<>|]', "_", text)


def strtobool(val: str) -> bool:
    """
    Convert a string representation of truth (case insensitive) to boolean type.

    Replaces distutils.util.strtobool, which is no longer included in the standard library since Python 3.10.

    True values are 'y', 'yes', 't', 'true', 'on', and '1'.
    False values are 'n', 'no', 'f', 'false', 'off', and '0'.
    Raises ValueError if 'val' is anything else.
    """
    match val.lower():
        case 'y' | 'yes' | 't' | 'true' | 'on' | '1':
            return True
        case 'n' | 'no' | 'f' | 'false' | 'off' | '0':
            return False
        case _:
            raise ValueError(f"invalid truth value '{val}' of type {type(val)}")


# TODO: depend on pathlib-extensions instead

class NotAFileError(OSError):
    """Raised when expecting a file, but encountering a different type of path.

    This class serves as the logical counterpart of the built-in `NotADirectoryError`.
    """


class SuffixError(Exception):
    """Raised when the file suffix does not meet the expected criteria."""


def prepare_output_file(p: AnyPath, check_suffix: str | None = None, with_suffix: str | None = None, create: bool = True) -> Path:
    """Prepare the target file path for writing.

    Args:
        p (AnyPath): The target file path.
        check_suffix (Union[str, None], optional): Expected suffix for the file. Defaults to None.
        with_suffix (Union[str, None], optional): Suffix to add if missing. Defaults to None.
        create (bool, optional): Whether to create the directory if it doesn't exist. Defaults to False.

    Returns:
        Path: The verified or updated file path.

    Raises:
        NotAFileError: If the target path exists but is not a file.
        ValueError: If both `check_suffix` and `with_suffix` are specified.
    """
    if isinstance(p, str):
        p = Path(p)
    if check_suffix is not None:
        if with_suffix is not None:
            raise ValueError('At most one of check_suffix and with_suffix can be specified')
        if p.suffix != check_suffix:
            raise SuffixError(check_suffix, p)
    if with_suffix is not None:
        p = p.with_suffix(with_suffix)
    if p.exists():
        if not p.is_file():
            raise NotAFileError(p)
    elif create:
        # if checks failed, new dir is not created
        p.parent.mkdir(parents=True, exist_ok=True)
    return p
