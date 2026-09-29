import re
from dataclasses import dataclass
from typing import Any, Self

from pydantic import GetCoreSchemaHandler, GetJsonSchemaHandler
from pydantic_core.core_schema import (
    CoreSchema,
    no_info_plain_validator_function,
    to_string_ser_schema,
)

BCP_LANG_CODES = {'en-us', 'zh-cn'}  # Azure uses BCP-47 language codes. They can be downcasted to ISO 639-1, but not vice versa.
ISO_LANG_CODES = {x.split('-')[0] for x in BCP_LANG_CODES}  # Whisper uses ISO 639-1 language codes


class UnregisteredLanguageCode(Exception):
    pass


class UnableToConvertLanguageCode(Exception):
    pass


@dataclass(frozen=True)
class LanguageCode:
    """Represent one registered source language."""

    source: str  # source language code (either BCP-47 or ISO 639-1)

    def __post_init__(self) -> None:
        """Validate that the source is a registered language code.

        Raises:
            UnregisteredLanguageCode: If `source` is neither a BCP-47 nor an ISO 639-1 code.
        """
        if self.source not in BCP_LANG_CODES and self.source not in ISO_LANG_CODES:
            raise UnregisteredLanguageCode(self.source)

    def __str__(self) -> str:
        """Render the source language code.

        Returns:
            str: The registered source code.
        """
        return self.source

    @classmethod
    def from_str(cls, text: str) -> Self:
        """
        Creates an instance of the class from the output of `cls.__str__`.

        Args:
            text (str): A single source code, normalized by stripping whitespace and lowercasing.

        Returns:
            Self: The parsed language code.

        Raises:
            ValueError: If the input does not match the output format of `cls.__str__`.
        """
        pattern = r"([a-z\-]+)"
        match = re.fullmatch(pattern, text.strip().lower())
        if not match:
            raise ValueError(f"Unexpected input: {text}")
        source = match.group(1)
        return cls(source=source)

    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type: Any, _handler: GetCoreSchemaHandler) -> CoreSchema:
        """
        Returns a Pydantic CoreSchema that defines how to validate and serialize a LanguageCode.

        Args:
            _source_type (Any): The annotated source type (unused; required by the Pydantic hook).
            _handler (GetCoreSchemaHandler): The Pydantic schema handler (unused; required by the hook).

        Returns:
            CoreSchema: A schema that validates strings/instances into `LanguageCode` and serializes them via `str`.

        Raises:
            TypeError: If the input value is not a string or LanguageCode instance.
            ValueError: If the input string is not a registered language code.
        """
        def deserialize(x: str | LanguageCode) -> LanguageCode:
            """Validate an incoming value into a LanguageCode instance.

            Args:
                x (str | LanguageCode): An existing instance or a `__str__` form.

            Returns:
                LanguageCode: The validated language code.

            Raises:
                TypeError: If `x` is neither a string nor a LanguageCode.
                ValueError: If `x` is a string that is not a registered language code.
            """
            if isinstance(x, cls):
                return x
            if isinstance(x, str):
                try:
                    return cls.from_str(x)
                except UnregisteredLanguageCode as e:
                    raise ValueError(f"Unregistered language code: '{e.args[0]}'") from e
            raise TypeError(f"Unexpected language {x} of type {type(x)}")

        return no_info_plain_validator_function(deserialize, serialization=to_string_ser_schema())

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema: CoreSchema, handler: GetJsonSchemaHandler) -> dict[str, Any]:
        """Describe the JSON schema FastAPI uses to document this type.

        Args:
            core_schema (CoreSchema): The core schema (unused; required by the Pydantic hook).
            handler (GetJsonSchemaHandler): The JSON schema handler (unused; required by the hook).

        Returns:
            dict[str, Any]: A JSON schema marking the field as a string with examples.
        """
        return {
            'type': 'string',
            'default': 'en-us',
            'examples': ['en', 'en-us'],  # FastAPI uses the first value here to generate examples in the documentation UI
        }

    def is_source_BCP(self) -> bool:
        """Report whether the source language is a BCP-47 code.

        Returns:
            bool: True if the source is a BCP-47 code, False if it is ISO 639-1.
        """
        return self.source in BCP_LANG_CODES

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
