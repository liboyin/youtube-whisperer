import pytest

from youtube_whisperer.downloaders.transcript_downloader import get_video_id, get_first_matching_lang_code


def test_get_video_id():
    assert get_video_id('https://youtu.be/n9xhJrPXop4?si=sXdajbZPk7Bn2OjD&t=30') == 'n9xhJrPXop4'
    assert get_video_id('https://www.youtube.com/watch?v=n9xhJrPXop4&si=sXdajbZPk7Bn2OjD&t=30') == 'n9xhJrPXop4'
    assert get_video_id('https://www.youtube.com/live/3TufaG29B7w?si=b5DQpvYgzcKJjJ0L') == '3TufaG29B7w'
    with pytest.raises(ValueError):
        get_video_id('https://example.com')


def test_get_first_matching_lang_code():
    assert get_first_matching_lang_code([], '') is None
    assert get_first_matching_lang_code([], None) is None
    assert get_first_matching_lang_code(['en'], '') == 'en'
    assert get_first_matching_lang_code(['en'], None) == 'en'
    assert get_first_matching_lang_code([], 'en') is None
    assert get_first_matching_lang_code(['en-US', 'en'], 'zh') is None
    assert get_first_matching_lang_code(['en-US', 'en'], 'en') == 'en-US'
    assert get_first_matching_lang_code(['en-US', 'en'], 'zh;en') == 'en-US'
    assert get_first_matching_lang_code(['en-US', 'zh-Hans', 'en'], 'zh;en') == 'zh-Hans'
