import pytest

from youtube_whisperer.adaptors.lang_code_adaptor import (
    LanguageCode,
    MissingTargetLanguageCode,
    UnableToConvertLanguageCode,
    UnregisteredLanguageCode,
)


def test_init():
    assert LanguageCode(source='en') == LanguageCode(source='en', target=None)
    assert LanguageCode(source='en-us') == LanguageCode(source='en-us', target=None)
    assert LanguageCode(source='en', target='zh') is not None
    assert LanguageCode(source='en', target='zh-cn') is not None


def test_init_invalid():
    with pytest.raises(UnregisteredLanguageCode):
        LanguageCode(source='')
    with pytest.raises(UnregisteredLanguageCode):
        LanguageCode(source='invalid')
    with pytest.raises(UnregisteredLanguageCode):
        LanguageCode(source='en', target='')
    with pytest.raises(UnregisteredLanguageCode):
        LanguageCode(source='en', target='invalid')


def test_str():
    lang_code_source_only = LanguageCode(source='en')
    assert str(lang_code_source_only) == 'en'
    lang_code_with_target = LanguageCode(source='en', target='zh')
    assert str(lang_code_with_target) == 'en->zh'


def test_from_str():
    lang_code = LanguageCode.from_str('en')
    assert lang_code == LanguageCode('en')
    lang_code = LanguageCode.from_str('en->zh')
    assert lang_code == LanguageCode('en', 'zh')
    lang_code = LanguageCode.from_str('  en-us  ->  zh-cn  ')
    assert lang_code == LanguageCode('en-us', 'zh-cn')
    # Test invalid format
    with pytest.raises(ValueError):
        LanguageCode.from_str('en<-zh')
    # Test invalid language code
    with pytest.raises(UnregisteredLanguageCode):
        LanguageCode.from_str('en->xx')

def test_from_repr():
    """Tests the from_repr classmethod."""
    # Test with target
    repr_str = "LanguageCode(source='en', target='zh')"
    lang_code = LanguageCode.from_repr(repr_str)
    assert lang_code == LanguageCode('en', 'zh')
    # Test without target
    repr_str = "LanguageCode(source='en-us', target=None)"
    lang_code = LanguageCode.from_repr(repr_str)
    assert lang_code == LanguageCode('en-us')
    # Test with BCP codes
    repr_str = "LanguageCode(source='en-us', target='zh-cn')"
    lang_code = LanguageCode.from_repr(repr_str)
    assert lang_code == LanguageCode('en-us', 'zh-cn')
    # Test invalid format
    with pytest.raises(ValueError):
        LanguageCode.from_repr("Invalid(source='en')")
    with pytest.raises(ValueError):
        LanguageCode.from_repr("LanguageCode(source='en', target='zh', extra='oops')")
    # Test invalid language code
    with pytest.raises(UnregisteredLanguageCode):
        LanguageCode.from_repr("LanguageCode(source='xx', target='yy')")


def test_is_source_bcp():
    assert LanguageCode('en-us').is_source_BCP() is True
    assert LanguageCode('en').is_source_BCP() is False


def test_is_target_bcp():
    assert LanguageCode('en', 'zh-cn').is_target_BCP() is True
    assert LanguageCode('en', 'zh').is_target_BCP() is False
    assert LanguageCode('en').is_target_BCP() is None


def test_get_source_as_bcp():
    assert LanguageCode('en-us').get_source_as_BCP() == 'en-us'
    with pytest.raises(UnableToConvertLanguageCode):
        LanguageCode('en').get_source_as_BCP()


def test_get_source_as_iso():
    assert LanguageCode('en-us').get_source_as_ISO() == 'en'
    assert LanguageCode('zh').get_source_as_ISO() == 'zh'


def test_get_source_as_bcp_and_iso():
    assert LanguageCode('en-us').get_source_as_BCP_and_ISO() == ['en-us', 'en']
    assert LanguageCode('en').get_source_as_BCP_and_ISO() == ['en']


def test_get_target_as_bcp():
    # No target
    with pytest.raises(MissingTargetLanguageCode):
        LanguageCode('en').get_target_as_BCP()
    # BCP target
    assert LanguageCode('en', 'zh-cn').get_target_as_BCP() == 'zh-cn'
    # ISO target
    with pytest.raises(UnableToConvertLanguageCode):
        LanguageCode('en', 'zh').get_target_as_BCP()

def test_get_target_as_iso():
    # No target
    with pytest.raises(MissingTargetLanguageCode):
        LanguageCode('en').get_target_as_ISO()
    # BCP target
    assert LanguageCode('en', 'zh-cn').get_target_as_ISO() == 'zh'
    # ISO target
    assert LanguageCode('en', 'zh').get_target_as_ISO() == 'zh'
