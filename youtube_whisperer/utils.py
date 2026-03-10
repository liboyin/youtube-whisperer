from enum import Enum
import os
from pathlib import Path
import re

import redis

WHISPER_ASSETS_DIR = Path(os.getenv("WHISPER_ASSETS_DIR", Path(__file__).parents[1] / "assets"))
WHISPER_MODELS_DIR = Path(os.getenv("WHISPER_MODELS_DIR", Path.home() / ".whisper"))

REDIS_POOL = redis.ConnectionPool(host='redis', socket_connect_timeout=5, health_check_interval=60)
REDIS_CLIENT = redis.StrictRedis(connection_pool=REDIS_POOL)


class TranscriberType(str, Enum):
    LOCAL = 'local'
    AZURE = 'azure'

    @classmethod
    def values(cls) -> tuple[str, ...]:
        return tuple(transcriber.value for transcriber in cls)


class TranscriberMode(str, Enum):
    TRANSCRIBE = 'transcribe'
    TRANSLATE = 'translate'

    @classmethod
    def values(cls) -> tuple[str, ...]:
        return tuple(mode.value for mode in cls)


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


def is_url(text: str) -> bool:
    """
    Checks if a string is a valid URL.

    Args:
        text (str): The input text.

    Returns:
        bool: True if the input text is a valid URL, False otherwise.
    """
    return bool(re.match(r"https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{2,256}\.[a-z]{2,6}\b([-a-zA-Z0-9@:%_\+.~#?&//=]*)", text))
