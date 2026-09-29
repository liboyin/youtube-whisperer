"""Pure domain values and source classification, without configured resources."""

import re
from enum import Enum


class TranscriberType(str, Enum):
    """Identify the transcription engine or download-only task policy.

    Declaration order is part of the public choices contract. ``none`` requests
    download only; it does not identify a transcription stream.
    """

    WHISPER = 'whisper'
    AZURE = 'azure'
    NONE = 'none'

    @classmethod
    def values(cls) -> tuple[str, ...]:
        """Return supported transcriber names in declaration order.

        Returns:
            The string value of each member, for example for argparse choices.
        """
        return tuple(transcriber.value for transcriber in cls)


def is_url(text: str) -> bool:
    """Classify a source using the existing HTTP(S) URL prefix pattern.

    This classifier preserves prefix matching and lowercase scheme/TLD behavior;
    it does not validate the entire string or contact the URL.

    Args:
        text: The input source string, without additional normalization.

    Returns:
        True when the source starts with a matching HTTP(S) URL.
    """
    return bool(re.match(r"https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{2,256}\.[a-z]{2,6}\b([-a-zA-Z0-9@:%_\+.~#?&//=]*)", text))
