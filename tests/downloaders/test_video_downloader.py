from types import SimpleNamespace

from pathlib_extensions import OverwriteMode

import youtube_whisperer.downloaders.video_downloader as video_testee


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


def test_download_video_returns_early_when_existing_file_should_not_be_overwritten(mocker, tmp_path):
    """Test that an existing file is not re-downloaded when overwrite is denied."""
    target_path = tmp_path / "video.mp4"
    target_path.write_text("existing")
    mock_overwrite = mocker.patch.object(video_testee, "overwrite_existing_path", return_value=False)
    mock_prepare = mocker.patch.object(video_testee, "prepare_output_file")
    mock_ydl = mocker.patch.object(video_testee.yt_dlp, "YoutubeDL")

    video_testee.download_video("https://example.com/watch?v=1", target_path, OverwriteMode.NEVER)

    mock_overwrite.assert_called_once_with(target_path, OverwriteMode.NEVER)
    mock_prepare.assert_not_called()
    mock_ydl.assert_not_called()


def test_download_video_downloads_with_cookies_when_available(mocker, tmp_path):
    """Test that available Firefox cookies are passed to yt-dlp for the download."""
    target_path = tmp_path / "video.mp4"
    created = {}

    def fake_factory(options):
        created["ydl"] = FakeYoutubeDL(options)
        return created["ydl"]

    mocker.patch.object(video_testee, "prepare_output_file")
    mocker.patch.object(video_testee, "is_firefox_cookies_available", return_value=True)
    mocker.patch.object(video_testee.yt_dlp, "YoutubeDL", side_effect=fake_factory)

    video_testee.download_video("https://example.com/watch?v=2", target_path, OverwriteMode.ALWAYS)

    assert created["ydl"].options["outtmpl"] == str(target_path)
    assert created["ydl"].options["cookiesfrombrowser"] == ("firefox",)
    assert created["ydl"].download_calls == [["https://example.com/watch?v=2"]]


def test_download_video_with_default_title_sanitizes_title_and_downloads(mocker, tmp_path):
    """Test that the video title is sanitized into the output filename before downloading."""
    mocker.patch.object(video_testee, "get_video_title", return_value="bad:/title")
    mocker.patch.object(video_testee, "replace_os_reserved_chars", return_value="bad_title")
    mocker.patch.object(
        video_testee,
        "truncate_filename",
        side_effect=lambda path, max_length: path,
    )
    mock_download = mocker.patch.object(video_testee, "download_video")

    result = video_testee.download_video_with_default_title(
        "https://example.com/watch?v=3",
        target_dir=tmp_path,
        overwrite=OverwriteMode.NEVER,
    )

    expected_path = tmp_path / "bad_title.mp4"
    assert result == expected_path
    mock_download.assert_called_once_with(
        "https://example.com/watch?v=3",
        expected_path,
        overwrite=OverwriteMode.NEVER,
    )


def test_video_main_parses_urls_and_calls_download(mocker):
    """Test that the CLI downloads each provided URL with the parsed overwrite mode."""
    args = SimpleNamespace(
        urls=["video-1", "video-2"],
        overwrite=OverwriteMode.NEVER,
    )
    mocker.patch("argparse.ArgumentParser.parse_args", return_value=args)
    mock_download = mocker.patch.object(video_testee, "download_video_with_default_title")

    video_testee.main()

    assert mock_download.call_args_list == [
        mocker.call("video-1", overwrite=OverwriteMode.NEVER),
        mocker.call("video-2", overwrite=OverwriteMode.NEVER),
    ]
