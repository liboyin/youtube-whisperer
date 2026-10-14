import logging
from xml.etree.ElementTree import ParseError

import pytest
import requests
from pathlib_extensions import OverwriteMode
from youtube_transcript_api import RequestBlocked, VideoUnavailable

import youtube_whisperer.downloaders as testee
from youtube_whisperer.adaptors.lang_code_adaptor import LanguageCode

LANGUAGE = LanguageCode("en")


def test_download_video_and_transcript_with_default_title_delegates(mocker, tmp_path):
    """Test that video and transcript downloads are delegated and their results combined."""
    video_path = tmp_path / "video.mp4"
    mock_download_video = mocker.patch.object(
        testee,
        "download_video_with_default_title",
        return_value=video_path,
    )
    downloader_instance = mocker.MagicMock()
    downloader_instance.download_as_srt_file.return_value = True
    mock_downloader = mocker.patch.object(
        testee,
        "TranscriptDownloader",
        return_value=downloader_instance,
    )

    result = testee.download_video_and_transcript_with_default_title(
        "https://example.com/watch?v=1",
        LANGUAGE,
        target_dir=tmp_path,
        overwrite=OverwriteMode.ALWAYS,
    )

    assert result == (video_path, True)
    mock_download_video.assert_called_once_with(
        "https://example.com/watch?v=1",
        tmp_path,
        OverwriteMode.ALWAYS,
    )
    mock_downloader.assert_called_once_with("https://example.com/watch?v=1", LANGUAGE)
    downloader_instance.download_as_srt_file.assert_called_once_with(
        tmp_path / "video.srt",
        OverwriteMode.ALWAYS,
    )



def test_combined_download_keeps_videos_apart_when_title_ends_in_another_id(mocker, tmp_path):
    """Video B titled like video A's tagged name gets its own media and SRT, not A's."""
    import youtube_whisperer.downloaders.video_downloader as video_testee

    metadata = {'url-a': ('Title', 'aaaaaaaaaaa'), 'url-b': ('Title [aaaaaaaaaaa]', 'bbbbbbbbbbb')}
    mocker.patch.object(video_testee, 'get_video_title_and_id', side_effect=metadata.__getitem__)
    mocker.patch.object(video_testee, 'download_video', side_effect=lambda url, path, overwrite: path.write_text(url))
    captions = mocker.patch.object(testee, 'TranscriptDownloader').return_value
    captions.download_as_srt_file.side_effect = lambda path, overwrite: path.write_text('captions') or True

    first, _ = testee.download_video_and_transcript_with_default_title('url-a', LANGUAGE, tmp_path, OverwriteMode.NEVER)
    second, _ = testee.download_video_and_transcript_with_default_title('url-b', LANGUAGE, tmp_path, OverwriteMode.NEVER)

    assert first == tmp_path / 'Title [aaaaaaaaaaa].mp4'
    assert second == tmp_path / 'Title [aaaaaaaaaaa] [bbbbbbbbbbb].mp4'
    assert (first.read_text(), second.read_text()) == ('url-a', 'url-b')
    assert [call.args[0] for call in captions.download_as_srt_file.call_args_list] == [first.with_suffix('.srt'), second.with_suffix('.srt')]

@pytest.mark.parametrize("phase", ['watch', 'caption'])
@pytest.mark.parametrize("error_type", [RequestBlocked, VideoUnavailable, requests.ReadTimeout, requests.ConnectionError])
def test_caption_service_failure_preserves_media_returns_missing_and_warns(mocker, tmp_path, caption_http, caplog, phase, error_type):
    """Listing/fetch service failures retain downloaded media and report URL plus traceback."""
    url = 'https://youtu.be/n9xhJrPXop4'
    media = tmp_path / 'media.mp4'
    error = error_type('n9xhJrPXop4')
    caption_http.failure_at = phase
    caption_http.failure = error

    def download_media(*args):
        """Publish an owned media file before the real synthetic caption operation."""
        media.write_bytes(b'owned media')
        return media

    mocker.patch.object(testee, 'download_video_with_default_title', side_effect=download_media)
    with caplog.at_level(logging.WARNING, logger=testee.__name__):
        assert testee.download_video_and_transcript_with_default_title(url, LANGUAGE, tmp_path, OverwriteMode.NEVER) == (media, False)
    assert media.read_bytes() == b'owned media'
    assert not media.with_suffix('.srt').exists()
    assert caption_http.calls[-1][0] == phase
    assert caption_http.closed
    records = [record for record in caplog.records if record.name == testee.__name__]
    assert len(records) == 1
    assert records[0].levelno == logging.WARNING
    assert url in records[0].getMessage()
    assert records[0].exc_info is not None
    assert records[0].exc_info[1] is error


@pytest.mark.parametrize("error_type", [ValueError, OSError, RuntimeError, ParseError, KeyError, KeyboardInterrupt])
def test_caption_local_parser_and_programming_failures_propagate(mocker, tmp_path, error_type):
    """Only classified caption-service errors can be converted into missing captions."""
    media = tmp_path / 'media.mp4'
    media.write_bytes(b'owned media')
    error = error_type('owned caption failure')
    mocker.patch.object(testee, 'download_video_with_default_title', return_value=media)
    downloader = mocker.patch.object(testee, 'TranscriptDownloader').return_value
    downloader.download_as_srt_file.side_effect = error
    with pytest.raises(error_type) as caught:
        testee.download_video_and_transcript_with_default_title('https://youtu.be/n9xhJrPXop4', LANGUAGE, tmp_path)
    assert caught.value is error
    assert media.read_bytes() == b'owned media'


@pytest.mark.parametrize("error_type", [OSError, requests.ConnectionError])
def test_media_failure_propagates_before_any_caption_attempt(mocker, tmp_path, error_type):
    """Even a requests-family media failure propagates and never attempts captions."""
    error = error_type('owned media failure')
    mocker.patch.object(testee, 'download_video_with_default_title', side_effect=error)
    downloader = mocker.patch.object(testee, 'TranscriptDownloader')
    with pytest.raises(error_type) as caught:
        testee.download_video_and_transcript_with_default_title('https://youtu.be/n9xhJrPXop4', LANGUAGE, tmp_path)
    assert caught.value is error
    downloader.assert_not_called()


def test_srt_publication_failure_propagates_and_preserves_existing_output(mocker, tmp_path, caption_http):
    """A real caption fetch followed by local publication failure preserves media and SRT."""
    import youtube_whisperer.downloaders.transcript_downloader as caption_testee

    media = tmp_path / 'media.mp4'
    media.write_bytes(b'owned media')
    srt = media.with_suffix('.srt')
    srt.write_text('original subtitles')
    mocker.patch.object(testee, 'download_video_with_default_title', return_value=media)
    mocker.patch.object(caption_testee.Path, 'replace', side_effect=OSError('owned publication failure'))
    with pytest.raises(OSError, match='owned publication failure'):
        testee.download_video_and_transcript_with_default_title('https://youtu.be/n9xhJrPXop4', LANGUAGE, tmp_path, OverwriteMode.ALWAYS)
    assert media.read_bytes() == b'owned media'
    assert srt.read_text() == 'original subtitles'
    assert sorted(tmp_path.iterdir()) == sorted([media, srt])
    assert caption_http.closed
