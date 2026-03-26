import inspect
from pathlib import Path
from types import SimpleNamespace

from pathlib_extensions import OverwriteMode

from youtube_whisperer.adaptors.lang_code_adaptor import LanguageCode
import youtube_whisperer.downloaders as downloaders_testee
import youtube_whisperer.downloaders.playlist_downloader as playlist_testee
import youtube_whisperer.downloaders.utils as utils_testee


LANGUAGE = LanguageCode("en")


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


def test_is_firefox_cookies_available_detects_cookie_file(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    cookies = tmp_path / ".mozilla" / "firefox" / "profile" / "cookies.sqlite"
    cookies.parent.mkdir(parents=True)
    cookies.write_text("cookie")

    assert utils_testee.is_firefox_cookies_available() is True
    assert "Found Firefox cookies:" in capsys.readouterr().out


def test_is_firefox_cookies_available_returns_false_when_missing(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))

    assert utils_testee.is_firefox_cookies_available() is False
    assert "No Firefox cookies found" in capsys.readouterr().out


# downloaders/__init__.py


def test_download_video_and_transcript_with_default_title_delegates(mocker):
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


def test_yield_video_urls_from_playlist_includes_firefox_cookies_when_available(mocker):
    created = {}

    def fake_factory(options):
        created["ydl"] = FakeYoutubeDL(
            options,
            {"entries": [{"id": "abc"}, {"id": "xyz"}]},
        )
        return created["ydl"]

    mocker.patch.object(playlist_testee, "is_firefox_cookies_available", return_value=True)
    mocker.patch.object(playlist_testee.yt_dlp, "YoutubeDL", side_effect=fake_factory)

    result = list(playlist_testee.yield_video_urls_from_playlist("https://example.com/playlist"))

    assert result == [
        "https://www.youtube.com/watch?v=abc",
        "https://www.youtube.com/watch?v=xyz",
    ]
    assert created["ydl"].options["cookiesfrombrowser"] == ("firefox",)
    assert created["ydl"].extract_info_call == ("https://example.com/playlist", False)


def test_yield_flattened_video_urls(mocker):
    mock_yield_playlist = mocker.patch.object(
        playlist_testee,
        'yield_video_urls_from_playlist',
        return_value=iter(['video1', 'video2'])
    )
    result = playlist_testee.yield_flattened_video_urls([
        'https://youtube.com/watch?v=direct1',
        'https://youtube.com/playlist?list=123',
        'https://youtube.com/watch?v=direct2',
    ])
    assert inspect.isgenerator(result)
    assert list(result) == ['https://youtube.com/watch?v=direct1', 'video1', 'video2', 'https://youtube.com/watch?v=direct2']
    mock_yield_playlist.assert_called_once_with('https://youtube.com/playlist?list=123')


def test_download_playlist_with_default_titles_downloads_each_url(mocker):
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


def test_playlist_main_parses_urls_and_forwards_overwrite(mocker):
    args = SimpleNamespace(
        urls=["playlist-1", "playlist-2"],
        overwrite=OverwriteMode.ALWAYS,
    )
    mocker.patch("argparse.ArgumentParser.parse_args", return_value=args)
    mock_download = mocker.patch.object(playlist_testee, "download_playlist_with_default_titles")

    playlist_testee.main()

    assert mock_download.call_args_list == [
        mocker.call("playlist-1", overwrite=OverwriteMode.ALWAYS),
        mocker.call("playlist-2", overwrite=OverwriteMode.ALWAYS),
    ]
