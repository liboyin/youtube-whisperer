from enum import Enum
import re

import redis

from youtube_whisperer.config import Settings

_settings = Settings()
WHISPER_ASSETS_DIR = _settings.whisper_assets_dir
WHISPER_MODELS_DIR = _settings.whisper_models_dir

REDIS_POOL = redis.ConnectionPool(host='redis', socket_connect_timeout=5, health_check_interval=60)
REDIS_CLIENT = redis.StrictRedis(connection_pool=REDIS_POOL)


class TranscriberType(str, Enum):
    WHISPER = 'whisper'
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


def is_url(text: str) -> bool:
    """
    Checks if a string is a valid URL.

    Args:
        text (str): The input text.

    Returns:
        bool: True if the input text is a valid URL, False otherwise.
    """
    return bool(re.match(r"https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{2,256}\.[a-z]{2,6}\b([-a-zA-Z0-9@:%_\+.~#?&//=]*)", text))
