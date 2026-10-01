import inspect

import pytest
from pathlib_extensions import OverwriteMode

import youtube_whisperer.downloaders.playlist_downloader as testee


def test_extract_flat_info_includes_firefox_cookies_when_available(youtube_dl_factory):
    """Test that flat extraction requests Firefox cookies and flat mode when cookies are available."""
    created = youtube_dl_factory(testee, cookies_available=True, extract_info_result={"entries": [{"id": "abc"}]})

    result = testee.extract_flat_info("https://example.com/playlist")

    assert result == {"entries": [{"id": "abc"}]}
    assert created.instances[0].options["extract_flat"] is True
    assert created.instances[0].options["cookiesfrombrowser"] == ("firefox",)
    assert created.instances[0].extract_info_calls == [("https://example.com/playlist", False)]


def test_extract_flat_info_omits_cookies_when_unavailable(youtube_dl_factory):
    """Test that flat extraction omits Firefox cookies when none are available."""
    created = youtube_dl_factory(testee, cookies_available=False, extract_info_result={"id": "solo"})

    result = testee.extract_flat_info("https://example.com/watch?v=solo")

    assert result == {"id": "solo"}
    assert "cookiesfrombrowser" not in created.instances[0].options


@pytest.mark.parametrize('metadata', [None, {}])
def test_extract_flat_info_preserves_empty_metadata_and_fresh_sessions(metadata, youtube_dl_factory):
    """Repeated extraction preserves metadata identity and owns independent records."""
    created = youtube_dl_factory(testee, cookies_available=False, extract_info_result=metadata)
    assert created.instances == []
    assert testee.extract_flat_info('first') is metadata
    assert testee.extract_flat_info('second') is metadata
    first, second = created.instances
    assert first is not second
    assert first.extract_info_calls == [('first', False)]
    assert second.extract_info_calls == [('second', False)]
    assert first.download_calls is not second.download_calls
    assert first.exit_calls is not second.exit_calls
    assert first.exit_calls == [(None, None, None)]
    assert second.exit_calls == [(None, None, None)]


def test_extract_flat_info_propagates_error_and_exits_context(youtube_dl_factory):
    """Extraction failure exits its session and preserves the exception identity."""
    error = RuntimeError('extraction failed')
    created = youtube_dl_factory(testee, cookies_available=False, error=error)
    with pytest.raises(RuntimeError) as caught:
        testee.extract_flat_info('url')
    assert caught.value is error
    instance = created.instances[0]
    assert instance.extract_info_calls == [('url', False)]
    assert len(instance.exit_calls) == 1
    assert instance.exit_calls[0][:2] == (RuntimeError, error)
    assert instance.exit_calls[0][2] is not None


def test_yield_video_urls_from_info_passes_through_single_video():
    """Test that a single-video info dict (no entries) yields the original URL unchanged."""
    result = list(testee.yield_video_urls_from_info({"id": "solo"}, "https://youtu.be/solo"))

    assert result == ["https://youtu.be/solo"]


def test_yield_video_urls_from_info_expands_entries_and_skips_unusable():
    """Test that playlist/channel entries expand to watch URLs, skipping deleted (None) and id-less videos."""
    info = {"entries": [{"id": "abc"}, None, {"title": "no id"}, {"id": "xyz"}]}

    result = list(testee.yield_video_urls_from_info(info, "https://example.com/channel"))

    assert result == [
        "https://www.youtube.com/watch?v=abc",
        "https://www.youtube.com/watch?v=xyz",
    ]


def test_yield_video_urls_from_info_raises_when_extraction_returns_nothing():
    """Test that a failed extraction (None info) raises a clear error instead of a TypeError."""
    with pytest.raises(ValueError, match="Failed to extract any video information from https://example.com/gone"):
        list(testee.yield_video_urls_from_info(None, "https://example.com/gone"))


def test_yield_video_urls_from_playlist_extracts_then_expands(mocker):
    """Test that playlist expansion flat-extracts the URL and branches the result into video URLs."""
    mocker.patch.object(testee, "extract_flat_info", return_value={"entries": [{"id": "abc"}, {"id": "xyz"}]})

    result = list(testee.yield_video_urls_from_playlist("https://example.com/playlist"))

    assert result == [
        "https://www.youtube.com/watch?v=abc",
        "https://www.youtube.com/watch?v=xyz",
    ]


def test_yield_flattened_video_urls_delegates_each_url(mocker):
    """Test that every input URL is expanded through yield_video_urls_from_playlist and concatenated."""
    mock_yield_playlist = mocker.patch.object(
        testee,
        'yield_video_urls_from_playlist',
        side_effect=[iter(['direct1']), iter(['video1', 'video2'])],
    )
    result = testee.yield_flattened_video_urls([
        'https://youtube.com/watch?v=direct1',
        'https://youtube.com/playlist?list=123',
    ])
    assert inspect.isgenerator(result)
    assert list(result) == ['direct1', 'video1', 'video2']
    assert mock_yield_playlist.call_args_list == [
        mocker.call('https://youtube.com/watch?v=direct1'),
        mocker.call('https://youtube.com/playlist?list=123'),
    ]


def test_download_playlist_with_default_titles_downloads_each_url(mocker, tmp_path):
    """Test that every expanded playlist URL is downloaded with default titles."""
    mocker.patch.object(
        testee,
        "yield_video_urls_from_playlist",
        return_value=iter(["url-1", "url-2"]),
    )
    mock_download = mocker.patch.object(
        testee,
        "download_video_with_default_title",
        side_effect=[tmp_path / "one.mp4", tmp_path / "two.mp4"],
    )

    result = testee.download_playlist_with_default_titles(
        "https://example.com/playlist",
        target_dir=tmp_path,
        overwrite=OverwriteMode.NEVER,
    )

    assert result == [tmp_path / "one.mp4", tmp_path / "two.mp4"]
    assert mock_download.call_args_list == [
        mocker.call("url-1", tmp_path, OverwriteMode.NEVER),
        mocker.call("url-2", tmp_path, OverwriteMode.NEVER),
    ]
