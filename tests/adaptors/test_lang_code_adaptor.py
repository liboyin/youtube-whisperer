import pytest

from youtube_whisperer.adaptors.lang_code_adaptor import LanguageCode, MissingTargetLanguageCode, UnregisteredLanguageCode, UnableToConvertLanguageCode


def test_init_valid_codes():
    # ISO source
    lang_code = LanguageCode(source='en')
    assert lang_code.source == 'en'
    assert lang_code.source_is_BCP is False
    assert lang_code.target is None
    assert lang_code.target_is_BCP is None
    # BCP source
    lang_code = LanguageCode(source='en-us')
    assert lang_code.source == 'en-us'
    assert lang_code.source_is_BCP is True
    # ISO target
    lang_code = LanguageCode(source='en', target='zh')
    assert lang_code.target == 'zh'
    assert lang_code.target_is_BCP is False
    # BCP target
    lang_code = LanguageCode(source='en', target='zh-cn')
    assert lang_code.target == 'zh-cn'
    assert lang_code.target_is_BCP is True


def test_init_invalid_codes():
    with pytest.raises(UnregisteredLanguageCode):
        LanguageCode(source='')
    with pytest.raises(UnregisteredLanguageCode):
        LanguageCode(source='invalid')
    with pytest.raises(UnregisteredLanguageCode):
        LanguageCode(source='en', target='')
    with pytest.raises(UnregisteredLanguageCode):
        LanguageCode(source='en', target='invalid')


def test_get_source_as_bcp():
    # BCP source
    lang_code = LanguageCode(source='en-us')
    assert lang_code.get_source_as_BCP() == 'en-us'
    # ISO source
    lang_code = LanguageCode(source='en')
    with pytest.raises(UnableToConvertLanguageCode):
        lang_code.get_source_as_BCP()


def test_get_source_as_iso():
    # BCP source
    lang_code = LanguageCode(source='en-us')
    assert lang_code.get_source_as_ISO() == 'en'
    # ISO source
    lang_code = LanguageCode(source='zh')
    assert lang_code.get_source_as_ISO() == 'zh'


def test_get_source_as_bcp_and_iso():
    # BCP source
    lang_code = LanguageCode(source='en-us')
    assert lang_code.get_source_as_BCP_and_ISO() == ['en-us', 'en']
    # ISO source
    lang_code = LanguageCode(source='en')
    assert lang_code.get_source_as_BCP_and_ISO() == ['en']


def test_get_target_as_bcp():
    # BCP target
    lang_code = LanguageCode(source='en', target='zh-cn')
    assert lang_code.get_target_as_BCP() == 'zh-cn'
    # ISO target
    lang_code = LanguageCode(source='en', target='zh')
    with pytest.raises(UnableToConvertLanguageCode):
        lang_code.get_target_as_BCP()
    # No target
    lang_code = LanguageCode(source='en')
    with pytest.raises(MissingTargetLanguageCode):
        lang_code.get_target_as_BCP()


def test_get_target_as_iso():
    # No target
    lang_code = LanguageCode(source='en')
    with pytest.raises(MissingTargetLanguageCode):
        lang_code.get_target_as_ISO()
    # ISO target
    lang_code_iso = LanguageCode(source='en', target='zh')
    assert lang_code_iso.get_target_as_ISO() == 'zh'
    # BCP target
    lang_code_bcp = LanguageCode(source='en', target='zh-cn')
    assert lang_code_bcp.get_target_as_ISO() == 'zh'
