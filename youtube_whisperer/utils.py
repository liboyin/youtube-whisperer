from contextlib import contextmanager
import os
from pathlib import Path
import re

import redis

from faster_whisper.tokenizer import _LANGUAGE_CODES as WHISPER_LANG_CODES

WHISPER_ASSETS_DIR = Path(os.getenv("WHISPER_ASSETS_DIR", Path(__file__).parents[1] / "assets"))
WHISPER_MODELS_DIR = Path(os.getenv("WHISPER_MODELS_DIR", Path.home() / ".whisper"))


def strtobool(val: str) -> bool:
    """
    Converts a string representation of truth (case insensitive) to boolean type.

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

WHISPER_OVERWRITE = strtobool(os.getenv("WHISPER_OVERWRITE", "false"))


def is_url(text: str) -> bool:
    """
    Checks if a string is a valid URL.

    Args:
        text (str): The input text.

    Returns:
        bool: True if the input text is a valid URL, False otherwise.
    """
    return bool(re.match(r"https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{2,256}\.[a-z]{2,6}\b([-a-zA-Z0-9@:%_\+.~#?&//=]*)", text))


def verify_language_code(language: str | None) -> None:
    """
    Verifies if the given language code is supported by Whisper. Ignore empty string or `None`.
    """
    if language and language not in WHISPER_LANG_CODES:
        raise ValueError("Unsupported language:", language)


@contextmanager
def redis_connection():
    """
    Context manager for establishing a Redis connection.

    Yields:
        redis.StrictRedis: A Redis client instance.

    Raises:
        redis.ConnectionError: If there is an issue connecting to the Redis server.
    """
    client = redis.StrictRedis(host='redis')
    try:
        client.ping()
        yield client
    except redis.ConnectionError:
        raise
    finally:
        client.close()
