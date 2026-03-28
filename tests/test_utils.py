import pytest

import youtube_whisperer.utils as testee


def test_transcriber_type_values():
    """Test that the transcriber enum exposes the supported transcriber names."""
    assert testee.TranscriberType.values() == ('whisper', 'azure')


def test_transcriber_type_rejects_legacy_local_alias():
    """Test that the legacy local transcriber alias is rejected."""
    with pytest.raises(ValueError, match="'local' is not a valid TranscriberType"):
        testee.TranscriberType('local')


def test_transcriber_mode_values():
    """Test that the transcriber mode enum exposes the supported mode names."""
    assert testee.TranscriberMode.values() == ('transcribe', 'translate')


@pytest.mark.parametrize("input_text, expected", [
    ("y", True),
    ("yes", True),
    ("t", True),
    ("true", True),
    ("on", True),
    ("1", True),
])
def test_strtobool_true(input_text, expected):
    """Test that truthy string inputs are converted to True."""
    assert testee.strtobool(input_text) is expected


@pytest.mark.parametrize("input_text, expected", [
    ("n", False),
    ("no", False),
    ("f", False),
    ("false", False),
    ("off", False),
    ("0", False),
])
def test_strtobool_false(input_text, expected):
    """Test that falsy string inputs are converted to False."""
    assert testee.strtobool(input_text) is expected


@pytest.mark.parametrize("input_text", [
    "invalid",
    "maybe",
    "2",
    "yesno",
])
def test_strtobool_invalid(input_text):
    """Test that invalid boolean-like strings raise ValueError."""
    with pytest.raises(ValueError):
        testee.strtobool(input_text)


@pytest.mark.parametrize("input_text, expected", [
    ("http://example.com", True),
    ("https://example.com", True),
    ("http://www.example.com", True),
    ("https://www.example.com", True),
    ("http://example.com/path?query=1", True),
    ("https://example.com/path?query=1", True),
    ("ftp://example.com", False),
    ("example.com", False),
    ("http:/example.com", False),
    ("http://", False),
    ("", False),
    ("not a url", False),
])
def test_is_url(input_text, expected):
    """Test that URL detection distinguishes valid HTTP URLs from other strings."""
    assert testee.is_url(input_text) == expected
