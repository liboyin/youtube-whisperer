from dataclasses import dataclass

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
