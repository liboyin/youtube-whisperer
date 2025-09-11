BCP_LANG_CODES = {'en-us', 'zh-cn'}  # Azure uses BCP-47 language codes. They can be downcasted to ISO 639-1, but not vice versa.
ISO_LANG_CODES = set(x.split('-')[0] for x in BCP_LANG_CODES)  # Whisper uses ISO 639-1 language codes


class UnregisteredLanguageCode(Exception):
    pass


class UnableToConvertLanguageCode(Exception):
    pass


class MissingTargetLanguageCode(Exception):
    pass


class LanguageCode:
    __slots__ = ("source", "source_is_BCP", "target", "target_is_BCP")

    def __init__(self, source: str, target: str | None = None) -> None:
        """
        Args:
            source (str): The source language code (either BCP-47 or ISO 639-1).
            target (str | None, optional): The optional target language code for translation.

        Raises:
            UnregisteredLanguageCode: If the source or target language codes are not registered.
        """
        self.source: str = source
        self.source_is_BCP: bool = False
        if source in BCP_LANG_CODES:
            self.source_is_BCP = True
        elif source not in ISO_LANG_CODES:
            raise UnregisteredLanguageCode(source)
        self.target: str | None = target
        self.target_is_BCP: bool | None = None
        if target is not None:
            if target in BCP_LANG_CODES:
                self.target_is_BCP = True
            elif target in ISO_LANG_CODES:
                self.target_is_BCP = False
            else:
                raise UnregisteredLanguageCode(target)
            
    def __repr__(self) -> str:
        slots_vals = ", ".join(f"{x}={getattr(self, x)}" for x in self.__slots__)
        return f'{self.__class__.__name__}({slots_vals})'

    def __str__(self) -> str:
        return repr(self)

    def get_source_as_BCP(self) -> str:
        """
        Returns the source language as a BCP-47 code.

        Raises:
            UnableToConvertLanguageCode: If the source language is not a BCP-47 code.
        """
        if self.source_is_BCP:
            return self.source
        raise UnableToConvertLanguageCode(self.source)
    
    def get_source_as_ISO(self) -> str:
        """
        Returns the source language as an ISO 639-1 code.
        """
        if self.source_is_BCP:
            return self.source.split('-')[0]
        return self.source
    
    def get_source_as_BCP_and_ISO(self) -> list[str]:
        """
        Returns both the BCP-47 (if possible) and ISO 639-1 representations of the source language.
        """
        result = []
        if self.source_is_BCP:
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
        if self.target_is_BCP:
            return self.target
        raise UnableToConvertLanguageCode(self.target)
    
    def get_target_as_ISO(self) -> str:
        """Returns the target language as an ISO 639-1 code.
            
        Raises:
            MissingTargetLanguageCode: If no target language is set.
        """
        if not self.target:
            raise MissingTargetLanguageCode
        if self.target_is_BCP:
            return self.target.split('-')[0]
        return self.target
