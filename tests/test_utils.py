import pytest

from youtube_whisperer.utils import strtobool


def test_strtobool_true():
    assert strtobool("y") is True
    assert strtobool("yes") is True
    assert strtobool("t") is True
    assert strtobool("true") is True
    assert strtobool("on") is True
    assert strtobool("1") is True


def test_strtobool_false():
    assert strtobool("n") is False
    assert strtobool("no") is False
    assert strtobool("f") is False
    assert strtobool("false") is False
    assert strtobool("off") is False
    assert strtobool("0") is False


def test_strtobool_invalid():
    with pytest.raises(ValueError):
        strtobool("invalid")
