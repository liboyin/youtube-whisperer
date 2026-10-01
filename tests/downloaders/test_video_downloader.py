import pytest
from pathlib_extensions import OverwriteMode

import youtube_whisperer.downloaders.video_downloader as testee


@pytest.mark.parametrize('cookies_available', [False, True])
def test_operation_retains_exact_options_and_discovers_cookies_at_invocation(cookies_available, youtube_dl_factory, mocker, monkeypatch, tmp_path):
    """Each operation retains exact defaults and uses lazy cached owned discovery."""
    monkeypatch.setenv('HOME', str(tmp_path))
    detector = testee.is_firefox_cookies_available
    detector.cache_clear()
    created = youtube_dl_factory(testee, cookies_available=cookies_available, extract_info_result=None)
    discovery = mocker.patch.object(testee, 'is_firefox_cookies_available', wraps=detector)
    cookies = tmp_path / '.mozilla' / 'firefox' / 'owned' / 'cookies.sqlite'
    if cookies_available:
        cookies.parent.mkdir(parents=True)
        cookies.write_text('owned')
    try:
        assert detector.cache_info().misses == 0
        discovery.assert_not_called()
        testee.download_video('url', tmp_path / 'video.mp4', OverwriteMode.ALWAYS)
        expected = {'verbose': True, 'js_runtimes': {'deno': {}}, 'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]', 'outtmpl': str(tmp_path / 'video.mp4')}
        if cookies_available:
            expected['cookiesfrombrowser'] = ('firefox',)
        assert created.instances[0].options == expected
        if cookies_available:
            cookies.unlink()
        else:
            cookies.parent.mkdir(parents=True)
            cookies.write_text('owned')
        testee.download_video('url', tmp_path / 'video.mp4', OverwriteMode.ALWAYS)
        assert created.instances[1].options == expected
        assert discovery.call_count == 2
        assert detector.cache_info().misses == 1
        assert detector.cache_info().hits == 1
        assert created.instances[0].options is not created.instances[1].options
        assert created.instances[0].options['js_runtimes'] is not created.instances[1].options['js_runtimes']
        assert [instance.download_calls for instance in created.instances] == [[['url']], [['url']]]
    finally:
        detector.cache_clear()


def test_download_video_returns_early_when_existing_file_should_not_be_overwritten(mocker, tmp_path):
    """Test that an existing file is not re-downloaded when overwrite is denied."""
    target_path = tmp_path / "video.mp4"
    target_path.write_text("existing")
    mock_overwrite = mocker.patch.object(testee, "overwrite_existing_path", return_value=False)
    mock_prepare = mocker.patch.object(testee, "prepare_output_file")
    mock_ydl = mocker.patch.object(testee.yt_dlp, "YoutubeDL")

    testee.download_video("https://example.com/watch?v=1", target_path, OverwriteMode.NEVER)

    mock_overwrite.assert_called_once_with(target_path, OverwriteMode.NEVER)
    mock_prepare.assert_not_called()
    mock_ydl.assert_not_called()


def test_download_video_downloads_with_cookies_when_available(mocker, tmp_path, youtube_dl_factory):
    """Test that available Firefox cookies are passed to yt-dlp for the download."""
    target_path = tmp_path / "video.mp4"
    created = youtube_dl_factory(testee, cookies_available=True)

    mocker.patch.object(testee, "prepare_output_file")

    testee.download_video("https://example.com/watch?v=2", target_path, OverwriteMode.ALWAYS)

    assert created.instances[0].options["outtmpl"] == str(target_path)
    assert created.instances[0].options["cookiesfrombrowser"] == ("firefox",)
    assert created.instances[0].download_calls == [["https://example.com/watch?v=2"]]


def test_download_video_omits_cookies_when_unavailable(mocker, tmp_path, youtube_dl_factory):
    """Test that the download omits Firefox cookies when no browser profile is available."""
    target_path = tmp_path / "video.mp4"
    created = youtube_dl_factory(testee, cookies_available=False)

    mocker.patch.object(testee, "prepare_output_file")

    testee.download_video("https://example.com/watch?v=4", target_path, OverwriteMode.ALWAYS)

    # Asking yt-dlp for browser cookies that do not exist makes it fail instead of downloading anonymously.
    assert "cookiesfrombrowser" not in created.instances[0].options
    assert created.instances[0].download_calls == [["https://example.com/watch?v=4"]]


def test_download_video_propagates_error_and_exits_context(tmp_path, youtube_dl_factory):
    """Download failure exits its session and preserves the exception identity."""
    error = RuntimeError('download failed')
    created = youtube_dl_factory(testee, cookies_available=False, error=error)
    with pytest.raises(RuntimeError) as caught:
        testee.download_video('url', tmp_path / 'video.mp4', OverwriteMode.ALWAYS)
    assert caught.value is error
    instance = created.instances[0]
    assert instance.download_calls == [['url']]
    assert len(instance.exit_calls) == 1
    assert instance.exit_calls[0][:2] == (RuntimeError, error)
    assert instance.exit_calls[0][2] is not None


def test_download_video_with_default_title_sanitizes_title_and_downloads(mocker, tmp_path):
    """Test that the video title is sanitized into the output filename before downloading."""
    mocker.patch.object(testee, "get_video_title", return_value="bad:/title")
    mocker.patch.object(testee, "replace_os_reserved_chars", return_value="bad_title")
    mocker.patch.object(
        testee,
        "truncate_filename",
        side_effect=lambda path, max_length: path,
    )
    mock_download = mocker.patch.object(testee, "download_video")

    result = testee.download_video_with_default_title(
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
