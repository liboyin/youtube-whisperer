from dataclasses import dataclass
import re
from typing import Any, Self

from pydantic import GetCoreSchemaHandler, GetJsonSchemaHandler
from pydantic_core.core_schema import CoreSchema, no_info_plain_validator_function, to_string_ser_schema

BCP_LANG_CODES = {'en-us', 'zh-cn'}  # Azure uses BCP-47 language codes. They can be downcasted to ISO 639-1, but not vice versa.
ISO_LANG_CODES = set(x.split('-')[0] for x in BCP_LANG_CODES)  # Whisper uses ISO 639-1 language codes


class UnregisteredLanguageCode(Exception):
    pass


class UnableToConvertLanguageCode(Exception):
    pass


class MissingTargetLanguageCode(Exception):
    pass


@dataclass(frozen=True)
class LanguageCode:
    source: str  # source language code (either BCP-47 or ISO 639-1)
    target: str | None = None  # target language code for translation

    def __post_init__(self) -> None:
        if self.source not in BCP_LANG_CODES and self.source not in ISO_LANG_CODES:
            raise UnregisteredLanguageCode(self.source)
        if self.target is not None:
            if self.target not in BCP_LANG_CODES and self.target not in ISO_LANG_CODES:
                raise UnregisteredLanguageCode(self.target)

    def __str__(self) -> str:
        if self.target:
            return f"{self.source}->{self.target}"
        return self.source

    @classmethod
    def from_str(cls, text: str) -> Self:
        """
        Creates an instance of the class from the output of `cls.__str__`.

        Raises:
            ValueError: If the input does not match the output format of `cls.__str__`.
        """
        pattern = r"([a-z\-]+)(?:\s*->\s*([a-z\-]+))?"
        match = re.fullmatch(pattern, text.strip().lower())
        if not match:
            raise ValueError(f"Unexpected input: {text}")
        source = match.group(1)
        target = match.group(2) if match.group(2) else None
        return cls(source=source, target=target)

    @classmethod
    def from_repr(cls, text: str) -> Self:
        """
        Creates an instance of the class from the output of `cls.__repr__`.

        Raises:
            ValueError: If the input does not match the output format of `cls.__repr__`.
        """
        pattern = cls.__name__ + r"\(source='([^']+)'(?:, target=(?:'([^']*)'|None))?\)"
        match = re.fullmatch(pattern, text.strip())
        if not match:
            raise ValueError(f"Unexpected input: {text}")
        source = match.group(1).lower()
        # target is None <==> group 2 does not exist
        target = match.group(2).lower() if match.group(2) else None
        return cls(source=source, target=target)

    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type: Any, _handler: GetCoreSchemaHandler) -> CoreSchema:
        """
        Returns a Pydantic CoreSchema that defines how to validate and serialize a LanguageCode.

        Raises:
            TypeError: If the input value is not a string or LanguageCode instance.
            ValueError: If the input string is not a registered language code.
        """
        def deserialize(x: str | LanguageCode) -> LanguageCode:
            if isinstance(x, cls):
                return x
            if isinstance(x, str):
                try:
                    if x.startswith(cls.__name__):
                        return cls.from_repr(x)
                    return cls.from_str(x)
                except UnregisteredLanguageCode as e:
                    raise ValueError(f"Unregistered language code: '{e.args[0]}'") from e
            raise TypeError(f"Unexpected language {x} of type {type(x)}")

        return no_info_plain_validator_function(deserialize, serialization=to_string_ser_schema())

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema: CoreSchema, handler: GetJsonSchemaHandler) -> dict[str, Any]:
        return {
            'type': 'string',
            'default': 'en-us',
            'examples': ['en', 'en-us', 'en-us->zh-cn'],  # FastAPI uses the first value here to generate examples in the documentation UI
        }

    def is_source_BCP(self) -> bool:
        return self.source in BCP_LANG_CODES

    def is_target_BCP(self) -> bool | None:
        if self.target is None:
            return None
        return self.target in BCP_LANG_CODES

    def get_source_as_BCP(self) -> str:
        """
        Returns the source language as a BCP-47 code.

        Raises:
            UnableToConvertLanguageCode: If the source language is not a BCP-47 code.
        """
        if self.is_source_BCP():
            return self.source
        raise UnableToConvertLanguageCode(self.source)
    
    def get_source_as_ISO(self) -> str:
        """
        Returns the source language as an ISO 639-1 code.
        """
        if self.is_source_BCP():
            return self.source.split('-')[0]
        return self.source
    
    def get_source_as_BCP_and_ISO(self) -> list[str]:
        """
        Returns both the BCP-47 (if possible) and ISO 639-1 representations of the source language.
        """
        result = []
        if self.is_source_BCP():
            result.append(self.get_source_as_BCP())
        result.append(self.get_source_as_ISO())
        return result
    
    def get_target_as_BCP(self) -> str:
        """
        Returns the target language as a BCP-47 code.

        Raises:
            MissingTargetLanguageCode: If no target language is set.
            UnableToConvertLanguageCode: If the target language is not a BCP-47 code.
        """
        if not self.target:
            raise MissingTargetLanguageCode
        if self.is_target_BCP():
            return self.target
        raise UnableToConvertLanguageCode(self.target)
    
    def get_target_as_ISO(self) -> str:
        """Returns the target language as an ISO 639-1 code.
            
        Raises:
            MissingTargetLanguageCode: If no target language is set.
        """
        if not self.target:
            raise MissingTargetLanguageCode
        if self.is_target_BCP():
            return self.target.split('-')[0]
        return self.target
