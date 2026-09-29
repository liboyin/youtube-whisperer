import pytest

import youtube_whisperer.adaptors.lang_code_adaptor as testee


@pytest.mark.parametrize('source', ['en', 'en-us', 'zh', 'zh-cn'])
def test_init_stores_registered_source(source):
    """Test that construction retains every registered source unchanged."""
    assert testee.LanguageCode(source=source).source == source


def test_init_rejects_removed_target_argument():
    """Test that retired target parameters cannot silently preserve translation calls."""
    with pytest.raises(TypeError):
        testee.LanguageCode('en', 'zh')
    with pytest.raises(TypeError):
        testee.LanguageCode('en', target='zh')


def test_removed_target_api_is_unavailable():
    """Test that the retired target state, helpers, and exception are absent."""
    language = testee.LanguageCode('en')
    for name in ['target', 'is_target_BCP', 'get_target_as_BCP', 'get_target_as_ISO']:
        assert not hasattr(language, name)
    assert not hasattr(testee, 'MissingTargetLanguageCode')


@pytest.mark.parametrize('source', ['', 'invalid', 'EN', ' en '])
def test_init_rejects_unregistered_or_unnormalized_source(source):
    """Test that direct construction retains strict whitelist validation."""
    with pytest.raises(testee.UnregisteredLanguageCode):
        testee.LanguageCode(source=source)


def test_str_renders_source():
    """Test that string rendering contains the source alone."""
    assert str(testee.LanguageCode(source='en')) == 'en'


@pytest.mark.parametrize('text, source', [('en', 'en'), ('  EN-US  ', 'en-us'), ('ZH', 'zh'), (' zh-cn ', 'zh-cn')])
def test_from_str_normalizes_single_source(text, source):
    """Test that parsing strips surrounding whitespace and normalizes letter case."""
    assert testee.LanguageCode.from_str(text) == testee.LanguageCode(source)


@pytest.mark.parametrize('text', ['en->zh', 'en->en', '  en-us  ->  zh-cn  ', 'en->xx', 'en<-zh', '', 'en_us'])
def test_from_str_rejects_arrows_and_malformed_input(text):
    """Test that parsing cannot silently turn a translation request into transcription."""
    with pytest.raises(ValueError, match='Unexpected input'):
        testee.LanguageCode.from_str(text)


def test_from_str_rejects_unregistered_source():
    """Test that well-formed unsupported source codes retain the whitelist exception."""
    with pytest.raises(testee.UnregisteredLanguageCode):
        testee.LanguageCode.from_str('fr')


def test_is_source_bcp():
    """Test that BCP-47 sources are distinguished from ISO 639-1 sources."""
    assert testee.LanguageCode('en-us').is_source_BCP() is True
    assert testee.LanguageCode('en').is_source_BCP() is False


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
