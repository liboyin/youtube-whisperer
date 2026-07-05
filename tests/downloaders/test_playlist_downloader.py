import inspect
import logging
from pathlib import Path

import pytest

from pathlib_extensions import OverwriteMode

from youtube_whisperer.adaptors.lang_code_adaptor import LanguageCode
import youtube_whisperer.downloaders as downloaders_testee
import youtube_whisperer.downloaders.playlist_downloader as playlist_testee
import youtube_whisperer.downloaders.utils as utils_testee


LANGUAGE = LanguageCode("en")


@pytest.fixture(autouse=True)
def clear_firefox_cookies_cache():
    utils_testee.is_firefox_cookies_available.cache_clear()
    yield
    utils_testee.is_firefox_cookies_available.cache_clear()


class FakeYoutubeDL:
    def __init__(self, options, extract_info_result=None):
        self.options = options
        self.extract_info_result = extract_info_result or {}
        self.download_calls = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def extract_info(self, url, download=False):
        self.extract_info_call = (url, download)
        return self.extract_info_result

    def download(self, urls):
        self.download_calls.append(urls)


# utils.py


def test_get_video_title_uses_yt_dlp_and_optional_firefox_cookies(mocker):
    """Test that the title is extracted via yt-dlp using Firefox cookies when available."""
    created = {}

    def fake_factory(options):
        created["ydl"] = FakeYoutubeDL(options, {"title": "Expected Title"})
        return created["ydl"]

    mocker.patch.object(utils_testee, "is_firefox_cookies_available", return_value=True)
    mocker.patch.object(utils_testee.yt_dlp, "YoutubeDL", side_effect=fake_factory)

    result = utils_testee.get_video_title("https://example.com/watch?v=1")

    assert result == "Expected Title"
    assert created["ydl"].options["simulate"] is True
    assert created["ydl"].options["cookiesfrombrowser"] == ("firefox",)
    assert created["ydl"].extract_info_call == ("https://example.com/watch?v=1", False)


def test_is_firefox_cookies_available_detects_cookie_file(monkeypatch, tmp_path, caplog):
    """Test that a cookies.sqlite under the Firefox profile is detected."""
    monkeypatch.setenv("HOME", str(tmp_path))
    cookies = tmp_path / ".mozilla" / "firefox" / "profile" / "cookies.sqlite"
    cookies.parent.mkdir(parents=True)
    cookies.write_text("cookie")

    with caplog.at_level(logging.INFO):
        assert utils_testee.is_firefox_cookies_available() is True
    assert "Found Firefox cookies:" in caplog.text


def test_is_firefox_cookies_available_returns_false_when_missing(monkeypatch, tmp_path, caplog):
    """Test that a missing cookies file reports cookies as unavailable."""
    monkeypatch.setenv("HOME", str(tmp_path))

    with caplog.at_level(logging.INFO):
        assert utils_testee.is_firefox_cookies_available() is False
    assert "No Firefox cookies found" in caplog.text


# downloaders/__init__.py


def test_download_video_and_transcript_with_default_title_delegates(mocker):
    """Test that video and transcript downloads are delegated and their results combined."""
    video_path = Path("/tmp/video.mp4")
    mock_download_video = mocker.patch.object(
        downloaders_testee,
        "download_video_with_default_title",
        return_value=video_path,
    )
    downloader_instance = mocker.MagicMock()
    downloader_instance.download_as_srt_file.return_value = True
    mock_downloader = mocker.patch.object(
        downloaders_testee,
        "TranscriptDownloader",
        return_value=downloader_instance,
    )

    result = downloaders_testee.download_video_and_transcript_with_default_title(
        "https://example.com/watch?v=1",
        LANGUAGE,
        target_dir=Path("/tmp"),
        overwrite=OverwriteMode.ALWAYS,
    )

    assert result == (video_path, True)
    mock_download_video.assert_called_once_with(
        "https://example.com/watch?v=1",
        Path("/tmp"),
        OverwriteMode.ALWAYS,
    )
    mock_downloader.assert_called_once_with("https://example.com/watch?v=1", LANGUAGE)
    downloader_instance.download_as_srt_file.assert_called_once_with(
        Path("/tmp/video.srt"),
        OverwriteMode.ALWAYS,
    )


# playlist_downloader.py


def test_extract_flat_info_includes_firefox_cookies_when_available(mocker):
    """Test that flat extraction requests Firefox cookies and flat mode when cookies are available."""
    created = {}

    def fake_factory(options):
        created["ydl"] = FakeYoutubeDL(options, {"entries": [{"id": "abc"}]})
        return created["ydl"]

    mocker.patch.object(playlist_testee, "is_firefox_cookies_available", return_value=True)
    mocker.patch.object(playlist_testee.yt_dlp, "YoutubeDL", side_effect=fake_factory)

    result = playlist_testee.extract_flat_info("https://example.com/playlist")

    assert result == {"entries": [{"id": "abc"}]}
    assert created["ydl"].options["extract_flat"] is True
    assert created["ydl"].options["cookiesfrombrowser"] == ("firefox",)
    assert created["ydl"].extract_info_call == ("https://example.com/playlist", False)


def test_extract_flat_info_omits_cookies_when_unavailable(mocker):
    """Test that flat extraction omits Firefox cookies when none are available."""
    created = {}

    def fake_factory(options):
        created["ydl"] = FakeYoutubeDL(options, {"id": "solo"})
        return created["ydl"]

    mocker.patch.object(playlist_testee, "is_firefox_cookies_available", return_value=False)
    mocker.patch.object(playlist_testee.yt_dlp, "YoutubeDL", side_effect=fake_factory)

    result = playlist_testee.extract_flat_info("https://example.com/watch?v=solo")

    assert result == {"id": "solo"}
    assert "cookiesfrombrowser" not in created["ydl"].options


def test_yield_video_urls_from_info_passes_through_single_video():
    """Test that a single-video info dict (no entries) yields the original URL unchanged."""
    result = list(playlist_testee.yield_video_urls_from_info({"id": "solo"}, "https://youtu.be/solo"))

    assert result == ["https://youtu.be/solo"]


def test_yield_video_urls_from_info_expands_entries_and_skips_unusable():
    """Test that playlist/channel entries expand to watch URLs, skipping deleted (None) and id-less videos."""
    info = {"entries": [{"id": "abc"}, None, {"title": "no id"}, {"id": "xyz"}]}

    result = list(playlist_testee.yield_video_urls_from_info(info, "https://example.com/channel"))

    assert result == [
        "https://www.youtube.com/watch?v=abc",
        "https://www.youtube.com/watch?v=xyz",
    ]


def test_yield_video_urls_from_info_raises_when_extraction_returns_nothing():
    """Test that a failed extraction (None info) raises a clear error instead of a TypeError."""
    with pytest.raises(ValueError, match="Failed to extract any video information from https://example.com/gone"):
        list(playlist_testee.yield_video_urls_from_info(None, "https://example.com/gone"))


def test_yield_video_urls_from_playlist_extracts_then_expands(mocker):
    """Test that playlist expansion flat-extracts the URL and branches the result into video URLs."""
    mocker.patch.object(playlist_testee, "extract_flat_info", return_value={"entries": [{"id": "abc"}, {"id": "xyz"}]})

    result = list(playlist_testee.yield_video_urls_from_playlist("https://example.com/playlist"))

    assert result == [
        "https://www.youtube.com/watch?v=abc",
        "https://www.youtube.com/watch?v=xyz",
    ]


def test_yield_flattened_video_urls_delegates_each_url(mocker):
    """Test that every input URL is expanded through yield_video_urls_from_playlist and concatenated."""
    mock_yield_playlist = mocker.patch.object(
        playlist_testee,
        'yield_video_urls_from_playlist',
        side_effect=[iter(['direct1']), iter(['video1', 'video2'])],
    )
    result = playlist_testee.yield_flattened_video_urls([
        'https://youtube.com/watch?v=direct1',
        'https://youtube.com/playlist?list=123',
    ])
    assert inspect.isgenerator(result)
    assert list(result) == ['direct1', 'video1', 'video2']
    assert mock_yield_playlist.call_args_list == [
        mocker.call('https://youtube.com/watch?v=direct1'),
        mocker.call('https://youtube.com/playlist?list=123'),
    ]


def test_download_playlist_with_default_titles_downloads_each_url(mocker):
    """Test that every expanded playlist URL is downloaded with default titles."""
    mocker.patch.object(
        playlist_testee,
        "yield_video_urls_from_playlist",
        return_value=iter(["url-1", "url-2"]),
    )
    mock_download = mocker.patch.object(
        playlist_testee,
        "download_video_with_default_title",
        side_effect=[Path("/tmp/one.mp4"), Path("/tmp/two.mp4")],
    )

    result = playlist_testee.download_playlist_with_default_titles(
        "https://example.com/playlist",
        target_dir=Path("/tmp"),
        overwrite=OverwriteMode.NEVER,
    )

    assert result == [Path("/tmp/one.mp4"), Path("/tmp/two.mp4")]
    assert mock_download.call_args_list == [
        mocker.call("url-1", Path("/tmp"), OverwriteMode.NEVER),
        mocker.call("url-2", Path("/tmp"), OverwriteMode.NEVER),
    ]
