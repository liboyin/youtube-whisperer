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
