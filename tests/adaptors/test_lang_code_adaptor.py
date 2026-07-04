import pytest

import youtube_whisperer.adaptors.lang_code_adaptor as testee


def test_init():
    """Test that a LanguageCode defaults target to None and stores explicit source/target codes."""
    assert testee.LanguageCode(source='en') == testee.LanguageCode(source='en', target=None)
    assert testee.LanguageCode(source='en-us') == testee.LanguageCode(source='en-us', target=None)
    assert testee.LanguageCode(source='en', target='zh').target == 'zh'
    assert testee.LanguageCode(source='en', target='zh-cn').target == 'zh-cn'


def test_init_invalid():
    """Test that unregistered or empty source/target codes are rejected."""
    with pytest.raises(testee.UnregisteredLanguageCode):
        testee.LanguageCode(source='')
    with pytest.raises(testee.UnregisteredLanguageCode):
        testee.LanguageCode(source='invalid')
    with pytest.raises(testee.UnregisteredLanguageCode):
        testee.LanguageCode(source='en', target='')
    with pytest.raises(testee.UnregisteredLanguageCode):
        testee.LanguageCode(source='en', target='invalid')


def test_str():
    """Test that str renders 'source' alone and 'source->target' with a target."""
    lang_code_source_only = testee.LanguageCode(source='en')
    assert str(lang_code_source_only) == 'en'
    lang_code_with_target = testee.LanguageCode(source='en', target='zh')
    assert str(lang_code_with_target) == 'en->zh'


def test_from_str():
    """Test that from_str parses 'source[->target]' and rejects malformed or unregistered input."""
    lang_code = testee.LanguageCode.from_str('en')
    assert lang_code == testee.LanguageCode('en')
    lang_code = testee.LanguageCode.from_str('en->zh')
    assert lang_code == testee.LanguageCode('en', 'zh')
    lang_code = testee.LanguageCode.from_str('  en-us  ->  zh-cn  ')
    assert lang_code == testee.LanguageCode('en-us', 'zh-cn')
    # Test invalid format
    with pytest.raises(ValueError):
        testee.LanguageCode.from_str('en<-zh')
    # Test invalid language code
    with pytest.raises(testee.UnregisteredLanguageCode):
        testee.LanguageCode.from_str('en->xx')


def test_is_source_bcp():
    """Test that BCP-47 sources are distinguished from ISO 639-1 sources."""
    assert testee.LanguageCode('en-us').is_source_BCP() is True
    assert testee.LanguageCode('en').is_source_BCP() is False


def test_is_target_bcp():
    """Test that target BCP detection returns None when no target is set."""
    assert testee.LanguageCode('en', 'zh-cn').is_target_BCP() is True
    assert testee.LanguageCode('en', 'zh').is_target_BCP() is False
    assert testee.LanguageCode('en').is_target_BCP() is None


def test_get_source_as_bcp():
    """Test that a BCP source is returned while an ISO-only source raises."""
    assert testee.LanguageCode('en-us').get_source_as_BCP() == 'en-us'
    with pytest.raises(testee.UnableToConvertLanguageCode):
        testee.LanguageCode('en').get_source_as_BCP()


def test_get_source_as_iso():
    """Test that a BCP source is downcast to ISO 639-1 and an ISO source is unchanged."""
    assert testee.LanguageCode('en-us').get_source_as_ISO() == 'en'
    assert testee.LanguageCode('zh').get_source_as_ISO() == 'zh'


def test_get_source_as_bcp_and_iso():
    """Test that both BCP and ISO forms are returned for a BCP source, ISO only otherwise."""
    assert testee.LanguageCode('en-us').get_source_as_BCP_and_ISO() == ['en-us', 'en']
    assert testee.LanguageCode('en').get_source_as_BCP_and_ISO() == ['en']


def test_get_target_as_bcp():
    """Test that a BCP target is returned while missing or ISO-only targets raise."""
    # No target
    with pytest.raises(testee.MissingTargetLanguageCode):
        testee.LanguageCode('en').get_target_as_BCP()
    # BCP target
    assert testee.LanguageCode('en', 'zh-cn').get_target_as_BCP() == 'zh-cn'
    # ISO target
    with pytest.raises(testee.UnableToConvertLanguageCode):
        testee.LanguageCode('en', 'zh').get_target_as_BCP()

def test_get_target_as_iso():
    """Test that a target is downcast to ISO 639-1 while a missing target raises."""
    # No target
    with pytest.raises(testee.MissingTargetLanguageCode):
        testee.LanguageCode('en').get_target_as_ISO()
    # BCP target
    assert testee.LanguageCode('en', 'zh-cn').get_target_as_ISO() == 'zh'
    # ISO target
    assert testee.LanguageCode('en', 'zh').get_target_as_ISO() == 'zh'
