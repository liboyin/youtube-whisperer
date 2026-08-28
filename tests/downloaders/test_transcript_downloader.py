from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pathlib_extensions import OverwriteMode

import youtube_whisperer.downloaders.transcript_downloader as testee
from youtube_whisperer.adaptors.lang_code_adaptor import LanguageCode


def test_get_video_id():
    """Test that video IDs are extracted from short, watch, and live URLs, rejecting others."""
    assert testee.get_video_id('https://youtu.be/n9xhJrPXop4?si=sXdajbZPk7Bn2OjD&t=30') == 'n9xhJrPXop4'
    assert testee.get_video_id('https://www.youtube.com/watch?v=n9xhJrPXop4&si=sXdajbZPk7Bn2OjD&t=30') == 'n9xhJrPXop4'
    assert testee.get_video_id('https://www.youtube.com/live/3TufaG29B7w?si=b5DQpvYgzcKJjJ0L') == '3TufaG29B7w'
    with pytest.raises(ValueError):
        testee.get_video_id('https://example.com')


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
    mock_video_id = 'test_video_id'
    mock_transcript_list = MagicMock()
    mocker.patch.object(testee, 'get_video_id', return_value=mock_video_id)
    mock_yt_api_class = mocker.patch.object(testee, 'YouTubeTranscriptApi')
    mock_yt_api_instance = mock_yt_api_class.return_value
    mock_yt_api_instance.list.return_value = mock_transcript_list

    result = testee.list_video_transcripts('https://www.youtube.com/watch?v=test_video_id')

    assert result == mock_transcript_list
    testee.get_video_id.assert_called_once_with('https://www.youtube.com/watch?v=test_video_id')
    mock_yt_api_class.assert_called_once_with()
    mock_yt_api_instance.list.assert_called_once_with(mock_video_id)


def test_list_video_transcripts_returns_none_when_transcripts_are_disabled(mocker):
    """Test that disabled transcripts yield None instead of raising."""
    mock_video_id = 'test_video_id'
    mocker.patch.object(testee, 'get_video_id', return_value=mock_video_id)
    mock_yt_api_class = mocker.patch.object(testee, 'YouTubeTranscriptApi')
    mock_yt_api_instance = mock_yt_api_class.return_value
    mock_yt_api_instance.list.side_effect = testee.TranscriptsDisabled(mock_video_id)

    result = testee.list_video_transcripts('https://www.youtube.com/watch?v=test_video_id')

    assert result is None
    mock_yt_api_instance.list.assert_called_once_with(mock_video_id)


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

    result = downloader.download()

    assert result == expected_transcript
    mock_list_video_transcripts.assert_called_once_with(downloader.url)
    mock_fetch_matching.assert_called_once_with(transcripts, downloader.language, downloader.url)


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
    """Test successful SRT file creation."""
    mock_srt_text = "1\n00:00:00,000 --> 00:00:02,000\nHello world\n\n"
    output_path = tmp_path / "output.srt"
    mocker.patch.object(downloader, 'download_as_srt_text', return_value=mock_srt_text)
    mocker.patch.object(testee, 'overwrite_existing_path', return_value=True)
    mock_path_instance = MagicMock()
    mock_prepare_output_file = mocker.patch.object(testee, 'prepare_output_file', return_value=mock_path_instance)
    mocker.patch.object(Path, 'is_file', return_value=False)
    result = downloader.download_as_srt_file(output_path, OverwriteMode.ALWAYS)
    assert result is True
    downloader.download_as_srt_text.assert_called_once_with()
    mock_prepare_output_file.assert_called_once_with(output_path)
    mock_path_instance.write_text.assert_called_once_with(mock_srt_text)


def test_download_as_srt_file_no_transcript(mocker, tmp_path, downloader):
    """Test when no transcript is available."""
    output_path = tmp_path / "output.srt"
    mocker.patch.object(Path, 'is_file', return_value=False)
    mocker.patch.object(downloader, 'download_as_srt_text', return_value=None)
    result = downloader.download_as_srt_file(output_path, OverwriteMode.ALWAYS)
    assert result is False
    downloader.download_as_srt_text.assert_called_once_with()


def test_download_as_srt_file_returns_true_when_file_exists_and_no_overwrite(tmp_path, downloader):
    """Test that an existing SRT is preserved and reported as success when overwrite is denied."""
    output_path = tmp_path / "output.srt"
    output_path.write_text("existing content")
    result = downloader.download_as_srt_file(output_path, OverwriteMode.NEVER)
    assert result is True
    assert output_path.read_text() == "existing content"


def test_download_as_srt_file_with_default_title_success(mocker, tmp_path, downloader):
    """Test with custom parameters."""
    mock_title = "Test Video"
    output_path = tmp_path / f"{mock_title}.srt"
    mocker.patch.object(testee, 'get_video_title', return_value=mock_title)
    mocker.patch.object(downloader, 'download_as_srt_file', return_value=True)
    result = downloader.download_as_srt_file_with_default_title(tmp_path, OverwriteMode.NEVER)
    assert result == output_path
    testee.get_video_title.assert_called_once_with(downloader.url)
    downloader.download_as_srt_file.assert_called_once_with(output_path, overwrite=OverwriteMode.NEVER)


def test_download_as_srt_file_with_default_title_failure(mocker, downloader):
    """Test failure case."""
    mocker.patch.object(testee, 'get_video_title', return_value="Test Video")
    mocker.patch.object(downloader, 'download_as_srt_file', return_value=False)
    result = downloader.download_as_srt_file_with_default_title(overwrite=OverwriteMode.NEVER)
    assert result is None
    downloader.download_as_srt_file.assert_called()


def test_download_as_srt_file_with_default_title_long_and_invalid_title(mocker, tmp_path, downloader):
    """Test with a long title containing invalid characters."""
    long_title = "a/b\\c?d*e:f|g<h>i\"j" * 20
    mocker.patch.object(testee, 'get_video_title', return_value=long_title)
    mocker.patch.object(downloader, 'download_as_srt_file', return_value=True)
    result = downloader.download_as_srt_file_with_default_title(tmp_path, OverwriteMode.NEVER)
    assert result is not None
    assert len(result.name) <= 220
    assert result.name.endswith('.srt')
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
