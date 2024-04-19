from pathlib import Path

AnyPath = str | Path


class NotAFileError(OSError):
    """Raised when expecting a file, but encountering a different type of path.

    This class serves as the logical counterpart of the built-in `NotADirectoryError`.
    """


class SuffixError(Exception):
    """Raised when the file suffix does not meet the expected criteria."""


def prepare_input_file(p: AnyPath, check_suffix: str | None = None, with_suffix: str | None = None) -> Path:
    """Prepare the target file path for reading.

    Args:
        p (AnyPath): The target file path.
        check_suffix (Union[str, None], optional): Expected suffix for the file. Defaults to None.
        with_suffix (Union[str, None], optional): Suffix to add if missing. Defaults to None.

    Returns:
        Path: The verified file path.

    Raises:
        FileNotFoundError: If the target path does not exist.
        NotAFileError: If the target path exists but is not a file.
        SuffixError: If the file suffix does not meet the expected criteria.
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
    if not p.is_file():
        if p.exists():
            raise NotAFileError(p)
        raise FileNotFoundError(p)
    return p


def prepare_output_dir(p: AnyPath, create: bool = True) -> Path:
    """Prepare the target directory path for writing.

    Args:
        p (AnyPath): The target directory path.
        create (bool, optional): Whether to create the directory if it doesn't exist. Defaults to False.

    Returns:
        Path: The verified or created directory path.

    Raises:
        NotADirectoryError: If the target path exists but is not a directory.
    """
    if isinstance(p, str):
        p = Path(p)
    if p.exists():
        if not p.is_dir():
            raise NotADirectoryError(p)
    elif create:
        # if checks failed, new dir is not created
        p.mkdir(parents=True, exist_ok=True)
    return p


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
