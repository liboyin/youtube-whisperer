from pathlib import Path
import re

from faster_whisper.tokenizer import _LANGUAGE_CODES as WHISPER_LANG_CODES

DEFAULT_HOME_DIR = Path.home() / ".whisper"


def is_url(text: str) -> bool:
    """
    Check if a string is a valid URL.

    Args:
        text (str): The input text.

    Returns:
        bool: True if the input text is a valid URL, False otherwise.
    """
    return bool(re.match(r"https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{2,256}\.[a-z]{2,6}\b([-a-zA-Z0-9@:%_\+.~#?&//=]*)", text))


def get_verified_language(language: str | None) -> str | None:
    """
    Verifies if the given language is supported. Ignore None.
    """
    if language and language not in WHISPER_LANG_CODES:
        raise ValueError("Unsupported language:", language)
    return language


def replace_os_reserved_chars(text: str, replacement: str = '_') -> str:
    """
    Replace reserved characters in a string with a specified replacement character.

    Should work on Windows, Linux, and macOS.

    Args:
        text (str): The input text.
        replacement (str, optional): The replacement character. Defaults to '_'.

    Returns:
        str: The modified text with reserved characters replaced by underscores.
    """
    return re.sub(r'[\\/*?:"<>|]', replacement, text)


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
