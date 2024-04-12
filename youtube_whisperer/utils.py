import re


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
