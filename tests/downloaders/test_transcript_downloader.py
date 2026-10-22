from unittest.mock import MagicMock, patch

import pytest
import requests
from pathlib_extensions import OverwritePolicy

import youtube_whisperer.downloaders.transcript_downloader as testee
from youtube_whisperer.adaptors.lang_code_adaptor import LanguageCode


@pytest.mark.parametrize("timeout", [(2, 3), 4, None])
def test_caption_session_preserves_explicit_keyword_timeout(caption_http, timeout):
    """Explicit caller timeouts, including None, override the session default."""
    with testee.CaptionSession() as session:
        session.get('https://www.youtube.com/watch?v=n9xhJrPXop4', timeout=timeout)
    assert caption_http.calls == [('watch', timeout)]
    assert caption_http.closed


@pytest.mark.parametrize("scheme", ["http", "https"])
@pytest.mark.parametrize("host", ["youtube.com", "www.youtube.com", "m.youtube.com", "M.YouTube.COM:443"])
@pytest.mark.parametrize("path", [
    "/watch?v=n9xhJrPXop4",
    "/watch?extra=ignored&v=n9xhJrPXop4&list=ignored",
    "/live/n9xhJrPXop4",
    "/live/n9xhJrPXop4/?extra=ignored",
    "/shorts/n9xhJrPXop4",
    "/shorts/n9xhJrPXop4/?extra=ignored",
])
def test_get_video_id_accepts_supported_youtube_forms(scheme, host, path):
    """Supported hosts and watch/live/shorts paths resolve despite URL decorations."""
    assert testee.get_video_id(f"{scheme}://{host}{path}#ignored") == "n9xhJrPXop4"


@pytest.mark.parametrize(("url", "expected"), [
    ("https://youtu.be/n9xhJrPXop4?si=ignored&t=30", "n9xhJrPXop4"),
    ("http://YOUTU.BE:80/n9xhJrPXop4/?extra=ignored#fragment", "n9xhJrPXop4"),
    ("https://youtu.be/0aA_-123456", "0aA_-123456"),
    ("https://www.youtube.com/live/3TufaG29B7w?si=ignored", "3TufaG29B7w"),
])
def test_get_video_id_accepts_short_links_and_id_characters(url, expected):
    """Short links accept one trailing slash and the full valid ID alphabet."""
    assert testee.get_video_id(url) == expected


@pytest.mark.parametrize("url", [
    "https://example.com/watch?v=n9xhJrPXop4",
    "https://youtube.com.example.com/watch?v=n9xhJrPXop4",
    "https://music.youtube.com/watch?v=n9xhJrPXop4",
    "https://youtube-nocookie.com/watch?v=n9xhJrPXop4",
    "ftp://www.youtube.com/watch?v=n9xhJrPXop4",
    "www.youtube.com/watch?v=n9xhJrPXop4",
    "//youtu.be/n9xhJrPXop4",
    "",
    "https://[broken/watch?v=n9xhJrPXop4",
    "https://www.youtube.com/watch",
    "https://www.youtube.com/watch?extra=ignored",
    "https://www.youtube.com/watch?v=",
    "https://www.youtube.com/watch?v=short",
    "https://www.youtube.com/watch?v=n9xhJrPXop44",
    "https://www.youtube.com/watch?v=n9xhJrPXop!",
    "https://www.youtube.com/watch?v=n9xhJrPXopé",
    "https://youtu.be/",
    "https://youtu.be/n9xhJrPXop4/extra",
    "https://youtu.be/n9xhJrPXop4//",
    "https://youtu.be//n9xhJrPXop4",
    "https://www.youtube.com/live/",
    "https://www.youtube.com/live/short",
    "https://www.youtube.com/live/n9xhJrPXop4/extra",
    "https://www.youtube.com/shorts/",
    "https://www.youtube.com/shorts/n9xhJrPXop4//",
    "https://www.youtube.com/shorts/n9xhJrPXop4/extra",
    "https://www.youtube.com/playlist?v=n9xhJrPXop4",
    "https://www.youtube.com/embed/n9xhJrPXop4",
    "https://www.youtube.com/v/n9xhJrPXop4",
    "https://www.youtube.com/",
])
def test_get_video_id_rejects_malformed_or_unsupported_urls(url):
    """Malformed inputs uniformly raise ValueError rather than returning invalid IDs."""
    with pytest.raises(ValueError):
        testee.get_video_id(url)


@pytest.mark.parametrize("base", [
    "https://youtu.be/n9xhJrPXop4",
    "https://www.youtube.com/live/n9xhJrPXop4",
    "https://m.youtube.com/shorts/n9xhJrPXop4",
    "https://www.youtube.com/watch",
])
@pytest.mark.parametrize("suffix", [";x", "/;extra"])
def test_get_video_id_rejects_path_parameters(base, suffix):
    """Path parameters must not disappear during parsing and expose a valid ID."""
    with pytest.raises(ValueError):
        testee.get_video_id(f"{base}{suffix}?v=n9xhJrPXop4")


@pytest.mark.parametrize("url", [
    "https://youtu.be:abc/n9xhJrPXop4",
    "https://youtube.com:65536/watch?v=n9xhJrPXop4",
    "https://www.youtube.com:-1/live/n9xhJrPXop4",
])
def test_get_video_id_rejects_invalid_ports(url):
    """Non-numeric, out-of-range and negative ports uniformly raise ValueError."""
    with pytest.raises(ValueError):
        testee.get_video_id(url)


def test_get_first_matching_lang_code():
    """Test that the first candidate matching the requested BCP/ISO code is chosen."""
    assert testee.get_first_matching_lang_code([], LanguageCode('en')) is None
    assert testee.get_first_matching_lang_code(['en-US', 'en'], LanguageCode('zh')) is None
    assert testee.get_first_matching_lang_code(['en-US', 'en'], LanguageCode('en')) == 'en-US'
    assert testee.get_first_matching_lang_code(['en-US', 'zh-cn', 'en'], LanguageCode('zh')) == 'zh-cn'


@pytest.fixture
def downloader():
    return testee.TranscriptDownloader('https://www.youtube.com/watch?v=test_video_id', LanguageCode('en'))


def test_list_video_transcripts_returns_transcripts(mocker):
    """Test that the transcript list is returned for a resolvable video."""
    http_client = MagicMock()
    mock_video_id = 'test_video_id'
    mock_transcript_list = MagicMock()
    mocker.patch.object(testee, 'get_video_id', return_value=mock_video_id)
    mock_yt_api_class = mocker.patch.object(testee, 'YouTubeTranscriptApi')
    mock_yt_api_instance = mock_yt_api_class.return_value
    mock_yt_api_instance.list.return_value = mock_transcript_list

    result = testee.list_video_transcripts('https://www.youtube.com/watch?v=test_video_id', http_client)

    assert result == mock_transcript_list
    testee.get_video_id.assert_called_once_with('https://www.youtube.com/watch?v=test_video_id')
    mock_yt_api_class.assert_called_once_with(http_client=http_client)
    mock_yt_api_instance.list.assert_called_once_with(mock_video_id)


def test_list_video_transcripts_returns_none_when_transcripts_are_disabled(mocker):
    """Test that disabled transcripts yield None instead of raising."""
    http_client = MagicMock()
    mock_video_id = 'test_video_id'
    mocker.patch.object(testee, 'get_video_id', return_value=mock_video_id)
    mock_yt_api_class = mocker.patch.object(testee, 'YouTubeTranscriptApi')
    mock_yt_api_instance = mock_yt_api_class.return_value
    mock_yt_api_instance.list.side_effect = testee.TranscriptsDisabled(mock_video_id)

    result = testee.list_video_transcripts('https://www.youtube.com/watch?v=test_video_id', http_client)

    assert result is None
    mock_yt_api_instance.list.assert_called_once_with(mock_video_id)


@pytest.mark.parametrize("omit_client", [True, False])
def test_list_video_transcripts_legacy_call_retains_timeout_session_for_later_fetch(caption_http, omit_client):
    """Legacy listing calls retain their default timeout session through later caption fetches."""
    url = 'https://youtu.be/n9xhJrPXop4'
    transcripts = testee.list_video_transcripts(url) if omit_client else testee.list_video_transcripts(url, None)
    assert transcripts is not None
    assert caption_http.calls == [('watch', (10, 30)), ('innertube', (10, 30))]
    assert not caption_http.closed
    fetched = transcripts.find_transcript(['en']).fetch()
    assert fetched[0].text == 'Owned captions'
    assert caption_http.calls[-1] == ('caption', (10, 30))
    assert not caption_http.closed


def test_fetch_matching_transcript_returns_transcript_for_matching_language(mocker):
    """Test that a transcript in the matching language is fetched."""
    expected_transcript = [{'text': 'hello', 'start': 0.0, 'duration': 1.0}]
    mock_transcript_list = MagicMock()
    mock_transcript_metadata_en = MagicMock()
    mock_transcript_metadata_en.language_code = 'en'
    mock_transcript_metadata_fr = MagicMock()
    mock_transcript_metadata_fr.language_code = 'fr'
    mock_transcript_list.__iter__.return_value = iter([mock_transcript_metadata_en, mock_transcript_metadata_fr])
    mocker.patch.object(testee, 'get_first_matching_lang_code', return_value='en')
    mock_transcript_list.find_transcript.return_value.fetch.return_value = expected_transcript

    result = testee.fetch_matching_transcript(mock_transcript_list, LanguageCode('en'), 'https://www.youtube.com/watch?v=test_video_id')

    assert result == expected_transcript
    mock_transcript_list.find_transcript.assert_called_once_with(['en'])


def test_fetch_matching_transcript_returns_none_when_no_matching_language(mocker):
    """Test that no matching language yields None without attempting a fetch."""
    mock_transcript_list = MagicMock()
    mock_transcript_metadata_fr = MagicMock()
    mock_transcript_metadata_fr.language_code = 'fr'
    mock_transcript_list.__iter__.return_value = iter([mock_transcript_metadata_fr])
    mocker.patch.object(testee, 'get_first_matching_lang_code', return_value=None)

    result = testee.fetch_matching_transcript(mock_transcript_list, LanguageCode('en'), 'https://www.youtube.com/watch?v=test_video_id')

    assert result is None
    mock_transcript_list.find_transcript.assert_not_called()


def test_fetch_matching_transcript_returns_none_when_transcript_lookup_fails(mocker):
    """Test that a failed transcript lookup yields None."""
    mock_video_id = 'test_video_id'
    mock_transcript_list = MagicMock()
    mock_transcript_metadata_en = MagicMock()
    mock_transcript_metadata_en.language_code = 'en'
    mock_transcript_list.__iter__.return_value = iter([mock_transcript_metadata_en])
    mocker.patch.object(testee, 'get_first_matching_lang_code', return_value='en')
    mock_transcript_list.find_transcript.return_value.fetch.side_effect = testee.NoTranscriptFound(mock_video_id, ['en'], {})

    result = testee.fetch_matching_transcript(mock_transcript_list, LanguageCode('en'), 'https://www.youtube.com/watch?v=test_video_id')

    assert result is None
    mock_transcript_list.find_transcript.assert_called_once_with(['en'])


def test_download_delegates_to_listing_and_matching_helpers(mocker, downloader):
    """Test that download composes the listing and matching helpers."""
    transcripts = MagicMock()
    expected_transcript = [{'text': 'hello', 'start': 0.0, 'duration': 1.0}]
    mock_list_video_transcripts = mocker.patch.object(testee, 'list_video_transcripts', return_value=transcripts)
    mock_fetch_matching = mocker.patch.object(testee, 'fetch_matching_transcript', return_value=expected_transcript)

    with patch.object(testee, 'CaptionSession') as session:
        http_client = session.return_value.__enter__.return_value
        result = downloader.download()

    assert result == expected_transcript
    mock_list_video_transcripts.assert_called_once_with(downloader.url, http_client)
    mock_fetch_matching.assert_called_once_with(transcripts, downloader.language, downloader.url)


def test_download_short_url_lists_correct_video_and_fetches_matching_transcript():
    """A shorts URL reaches the faked caption client with its parsed video ID."""
    transcripts = MagicMock()
    metadata = MagicMock(language_code='en')
    transcripts.__iter__.return_value = iter([metadata])
    expected = MagicMock()
    transcripts.find_transcript.return_value.fetch.return_value = expected
    downloader = testee.TranscriptDownloader('https://m.youtube.com/shorts/n9xhJrPXop4/', LanguageCode('en'))
    with patch.object(testee, 'YouTubeTranscriptApi') as api:
        api.return_value.list.return_value = transcripts
        assert downloader.download() is expected
    api.return_value.list.assert_called_once_with('n9xhJrPXop4')
    transcripts.find_transcript.assert_called_once_with(['en'])
    transcripts.find_transcript.return_value.fetch.assert_called_once_with()


def test_download_applies_timeout_to_watch_innertube_and_caption_requests(caption_http):
    """The real caption library uses the finite timeout on all three request kinds."""
    downloader = testee.TranscriptDownloader('https://youtu.be/n9xhJrPXop4', LanguageCode('en'))
    result = downloader.download()
    assert result.video_id == 'n9xhJrPXop4'
    assert result[0].text == 'Owned captions'
    assert caption_http.calls == [('watch', (10, 30)), ('innertube', (10, 30)), ('caption', (10, 30))]
    assert caption_http.closed


@pytest.mark.parametrize("phase", ['watch', 'innertube', 'caption'])
def test_download_timeout_propagates_and_closes_owned_session(caption_http, phase):
    """A synthetic stall with a finite timeout fails synchronously and closes the session."""
    error = requests.ReadTimeout('owned stalled request')
    caption_http.failure_at = phase
    caption_http.failure = error
    downloader = testee.TranscriptDownloader('https://youtu.be/n9xhJrPXop4', LanguageCode('en'))
    with pytest.raises(requests.ReadTimeout) as caught:
        downloader.download()
    assert caught.value is error
    assert caption_http.calls[-1] == (phase, (10, 30))
    assert caption_http.closed


@pytest.mark.parametrize("missing", ['disabled', 'language'])
def test_download_missing_captions_closes_owned_session(caption_http, missing):
    """Disabled captions or an unmatched language return None and release the session."""
    caption_http.disabled = missing == 'disabled'
    caption_http.language = 'fr'
    downloader = testee.TranscriptDownloader('https://youtu.be/n9xhJrPXop4', LanguageCode('en'))
    assert downloader.download() is None
    assert caption_http.calls == [('watch', (10, 30)), ('innertube', (10, 30))]
    assert caption_http.closed


def test_download_as_srt_text_success(mocker, downloader):
    """Test successful SRT text generation."""
    mock_transcript_body = [
        {'text': 'Hello world', 'start': 0.0, 'end': 2.0},
        {'text': 'This is a test', 'start': 2.0, 'end': 4.0}
    ]
    mocker.patch.object(downloader, 'download', return_value=mock_transcript_body)
    mock_formatter = mocker.patch.object(testee, 'SRTFormatter')
    mock_formatter_instance = mock_formatter.return_value
    mock_formatter_instance.format_transcript.return_value = "1\n00:00:00,000 --> 00:00:02,000\nHello world\n\n2\n00:00:02,000 --> 00:00:04,000\nThis is a test\n\n"
    result = downloader.download_as_srt_text()
    assert result == "1\n00:00:00,000 --> 00:00:02,000\nHello world\n\n2\n00:00:02,000 --> 00:00:04,000\nThis is a test\n\n"
    downloader.download.assert_called_once_with()
    mock_formatter_instance.format_transcript.assert_called_once_with(mock_transcript_body)


def test_download_as_srt_text_no_transcript(mocker, downloader):
    """Test when no transcript is available."""
    mocker.patch.object(downloader, 'download', return_value=None)
    result = downloader.download_as_srt_text()
    assert result is None
    downloader.download.assert_called_once_with()


def test_download_as_srt_file_success(mocker, tmp_path, downloader):
    """Caption saving writes exact text to the real owned output path."""
    srt_text = "1\n00:00:00,000 --> 00:00:02,000\n字幕\n\n"
    output = tmp_path / "nested" / "output.srt"
    download = mocker.patch.object(downloader, 'download_as_srt_text', return_value=srt_text)
    original_open = testee.Path.open

    def checked_open(path, mode='r', *args, **kwargs):
        """Verify owned parent preparation before delegating real exclusive stage creation."""
        if mode == 'x':
            assert path.parent.is_dir(), "SRT parent must exist before staging"
        return original_open(path, mode, *args, **kwargs)

    with patch.object(testee.Path, 'open', checked_open):
        assert downloader.download_as_srt_file(output, OverwritePolicy.ALWAYS) is True
    assert output.read_text() == srt_text
    assert list(output.parent.iterdir()) == [output]
    download.assert_called_once_with()


@pytest.mark.parametrize("existing", [False, True])
def test_download_as_srt_file_preserves_final_on_publication_failure_and_retry(mocker, tmp_path, downloader, existing):
    """Caption publication failure leaves final output unchanged and retry saves complete text."""
    output = tmp_path / "output.srt"
    if existing:
        output.write_text("original")
    mocker.patch.object(downloader, 'download_as_srt_text', return_value="complete\n\n")
    with patch.object(testee.Path, 'replace', side_effect=OSError("injected publication failure")), pytest.raises(OSError, match="injected publication failure"):
        downloader.download_as_srt_file(output, OverwritePolicy.ALWAYS)
    assert output.read_text() == "original" if existing else not output.exists()
    assert list(tmp_path.iterdir()) == ([output] if existing else [])
    assert downloader.download_as_srt_file(output, OverwritePolicy.NEVER if not existing else OverwritePolicy.ALWAYS) is True
    assert output.read_text() == "complete\n\n"


@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize("overwrite", [OverwritePolicy.NEVER])
def test_download_as_srt_file_never_preserves_competitor_and_avoids_denied_download(mocker, tmp_path, downloader, existing, overwrite):
    """Denied captions avoid network work and a competitor appearing during download wins."""
    output = tmp_path / "output.srt"
    if existing:
        output.write_text("original")

    def competing_download():
        """Create competing output while a synthetic caption fetch is in progress."""
        output.write_text("competing")
        return "candidate"

    download = mocker.patch.object(downloader, 'download_as_srt_text', side_effect=competing_download)
    assert downloader.download_as_srt_file(output, overwrite) is True
    assert output.read_text() == ("original" if existing else "competing")
    assert download.call_count == (0 if existing else 1)
    assert list(tmp_path.iterdir()) == [output]


def test_download_as_srt_file_no_transcript(mocker, tmp_path, downloader):
    """Test when no transcript is available."""
    output_path = tmp_path / "output.srt"
    mocker.patch.object(downloader, 'download_as_srt_text', return_value=None)
    result = downloader.download_as_srt_file(output_path, OverwritePolicy.ALWAYS)
    assert result is False
    downloader.download_as_srt_text.assert_called_once_with()


def test_download_as_srt_file_returns_true_when_file_exists_and_no_overwrite(tmp_path, downloader):
    """Test that an existing SRT is preserved and reported as success when overwrite is denied."""
    output_path = tmp_path / "output.srt"
    output_path.write_text("existing content")
    result = downloader.download_as_srt_file(output_path, OverwritePolicy.NEVER)
    assert result is True
    assert output_path.read_text() == "existing content"


def test_download_as_srt_file_rejects_rename_before_caption_request(mocker, tmp_path, downloader):
    """RENAME is refused before captions are requested or any SRT is written."""
    request = mocker.patch.object(downloader, "download_as_srt_text", side_effect=AssertionError("caption request"))
    with pytest.raises(ValueError, match="RENAME is not supported"):
        downloader.download_as_srt_file(tmp_path / "output.srt", OverwritePolicy.RENAME)
    request.assert_not_called()
    assert list(tmp_path.iterdir()) == []


def test_download_as_srt_file_with_default_title_success(mocker, tmp_path, downloader):
    """The SRT is named after the video title tagged with its ID."""
    output_path = tmp_path / "Test Video [n9xhJrPXop4].srt"
    mocker.patch.object(testee, 'get_video_title_and_id', return_value=("Test Video", "n9xhJrPXop4"))
    mocker.patch.object(downloader, 'download_as_srt_file', return_value=True)
    result = downloader.download_as_srt_file_with_default_title(tmp_path, OverwritePolicy.NEVER)
    assert result == output_path
    testee.get_video_title_and_id.assert_called_once_with(downloader.url)
    downloader.download_as_srt_file.assert_called_once_with(output_path, overwrite=OverwritePolicy.NEVER)


def test_download_as_srt_file_with_default_title_rejects_rename_before_metadata_or_settings(mocker, downloader):
    """RENAME fails before the asset directory is resolved or video metadata is requested."""
    metadata = mocker.patch.object(testee, 'get_video_title_and_id', side_effect=AssertionError('metadata requested'))
    settings = mocker.patch.object(testee, 'Settings', side_effect=AssertionError('settings resolved'))
    with pytest.raises(ValueError, match='RENAME is not supported'):
        downloader.download_as_srt_file_with_default_title(overwrite=OverwritePolicy.RENAME)
    metadata.assert_not_called()
    settings.assert_not_called()


def test_download_as_srt_file_with_default_title_failure(mocker, downloader):
    """Test failure case."""
    mocker.patch.object(testee, 'get_video_title_and_id', return_value=("Test Video", "n9xhJrPXop4"))
    mocker.patch.object(downloader, 'download_as_srt_file', return_value=False)
    result = downloader.download_as_srt_file_with_default_title(overwrite=OverwritePolicy.NEVER)
    assert result is None
    downloader.download_as_srt_file.assert_called()


def test_download_as_srt_file_with_default_title_reuses_existing_title_only_srt(mocker, tmp_path, downloader):
    """An SRT downloaded before IDs were added to names is reused under its old name."""
    legacy = tmp_path / "Test Video.srt"
    legacy.write_text("legacy captions")
    mocker.patch.object(testee, 'get_video_title_and_id', return_value=("Test Video", "n9xhJrPXop4"))
    mocker.patch.object(downloader, 'download_as_srt_file', return_value=True)
    assert downloader.download_as_srt_file_with_default_title(tmp_path, OverwritePolicy.NEVER) == legacy
    downloader.download_as_srt_file.assert_called_once_with(legacy, overwrite=OverwritePolicy.NEVER)


def test_download_as_srt_file_with_default_title_long_and_invalid_title(mocker, tmp_path, downloader):
    """Test with a long title containing invalid characters."""
    long_title = "a/b\\c?d*e:f|g<h>i\"j" * 20
    mocker.patch.object(testee, 'get_video_title_and_id', return_value=(long_title, "n9xhJrPXop4"))
    mocker.patch.object(downloader, 'download_as_srt_file', return_value=True)
    result = downloader.download_as_srt_file_with_default_title(tmp_path, OverwritePolicy.NEVER)
    assert result is not None
    assert len(result.name.encode('utf-8')) <= 220
    assert result.name.endswith(' [n9xhJrPXop4].srt')
    # Check that invalid characters are replaced
    assert '/' not in result.name
    assert '\\' not in result.name
    assert '?' not in result.name
    assert '*' not in result.name
    assert ':' not in result.name
    assert '|' not in result.name
    assert '<' not in result.name
    assert '>' not in result.name
    assert '"' not in result.name


def test_download_as_srt_file_with_default_title_truncates_long_dotted_title_keeping_srt_suffix(mocker, tmp_path, downloader):
    """A long title containing dots is truncated to 220 bytes and keeps its ID tag and .srt suffix."""
    title = 'Mr. Smith Goes to Washington ' + 'x' * 300
    mocker.patch.object(testee, 'get_video_title_and_id', return_value=(title, 'n9xhJrPXop4'))
    mocker.patch.object(downloader, 'download_as_srt_file', return_value=True)
    result = downloader.download_as_srt_file_with_default_title(tmp_path, OverwritePolicy.NEVER)
    assert result == tmp_path / (title[:220 - len(' [n9xhJrPXop4].srt')] + ' [n9xhJrPXop4].srt')
    downloader.download_as_srt_file.assert_called_once_with(result, overwrite=OverwritePolicy.NEVER)


def test_download_as_srt_file_with_default_title_never_reuses_another_videos_tagged_srt(mocker, tmp_path, downloader):
    """Captions for a title ending in another video's ID tag get their own file."""
    other = tmp_path / 'Title [aaaaaaaaaaa].srt'
    other.write_text('captions of video a')
    mocker.patch.object(testee, 'get_video_title_and_id', return_value=('Title [aaaaaaaaaaa]', 'bbbbbbbbbbb'))
    mocker.patch.object(downloader, 'download_as_srt_file', return_value=True)
    result = downloader.download_as_srt_file_with_default_title(tmp_path, OverwritePolicy.NEVER)
    assert result == tmp_path / 'Title [aaaaaaaaaaa] [bbbbbbbbbbb].srt'
    downloader.download_as_srt_file.assert_called_once_with(result, overwrite=OverwritePolicy.NEVER)
    assert other.read_text() == 'captions of video a'
