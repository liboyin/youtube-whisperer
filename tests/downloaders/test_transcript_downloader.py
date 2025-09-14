import pytest
from pathlib import Path
from unittest.mock import MagicMock
from pathlib_extensions import OverwriteMode

from youtube_whisperer.adaptors.lang_code_adaptor import LanguageCode
import youtube_whisperer.downloaders.transcript_downloader as testee
from youtube_whisperer.downloaders.transcript_downloader import TranscriptDownloader, get_video_id, get_first_matching_lang_code


def test_get_video_id():
    assert get_video_id('https://youtu.be/n9xhJrPXop4?si=sXdajbZPk7Bn2OjD&t=30') == 'n9xhJrPXop4'
    assert get_video_id('https://www.youtube.com/watch?v=n9xhJrPXop4&si=sXdajbZPk7Bn2OjD&t=30') == 'n9xhJrPXop4'
    assert get_video_id('https://www.youtube.com/live/3TufaG29B7w?si=b5DQpvYgzcKJjJ0L') == '3TufaG29B7w'
    with pytest.raises(ValueError):
        get_video_id('https://example.com')


def test_get_first_matching_lang_code():
    assert get_first_matching_lang_code([], LanguageCode('en')) is None
    assert get_first_matching_lang_code(['en-US', 'en'], LanguageCode('zh')) is None
    assert get_first_matching_lang_code(['en-US', 'en'], LanguageCode('en')) == 'en-US'
    assert get_first_matching_lang_code(['en-US', 'zh-cn', 'en'], LanguageCode('zh')) == 'zh-cn'


@pytest.fixture
def downloader():
    return TranscriptDownloader('https://www.youtube.com/watch?v=test_video_id', LanguageCode('en'))


def test_download_success(mocker, downloader):
    """Test successful transcript download."""
    mock_video_id = 'test_video_id'
    expected_transcript = [{'text': 'hello', 'start': 0.0, 'duration': 1.0}]
    mocker.patch.object(testee, 'get_video_id', return_value=mock_video_id)
    mock_yt_api_class = mocker.patch.object(testee, 'YouTubeTranscriptApi')
    mock_yt_api_instance = mock_yt_api_class.return_value
    mock_transcript_list = MagicMock()
    mock_yt_api_instance.list.return_value = mock_transcript_list
    mock_transcript_metadata_en = MagicMock()
    mock_transcript_metadata_en.language_code = 'en'
    mock_transcript_metadata_fr = MagicMock()
    mock_transcript_metadata_fr.language_code = 'fr'
    mock_transcript_list.__iter__.return_value = iter([mock_transcript_metadata_en, mock_transcript_metadata_fr])
    mocker.patch.object(testee, 'get_first_matching_lang_code', return_value='en')
    mock_transcript_list.find_transcript.return_value.fetch.return_value = expected_transcript
    result = downloader.download()
    assert result == expected_transcript
    testee.get_video_id.assert_called_once_with(downloader.url)
    mock_yt_api_class.assert_called_once_with()
    mock_yt_api_instance.list.assert_called_once_with(mock_video_id)
    mock_transcript_list.find_transcript.assert_called_once_with(['en'])


def test_download_disabled(mocker, downloader):
    """Test when transcripts are disabled."""
    mock_video_id = 'test_video_id'
    mocker.patch.object(testee, 'get_video_id', return_value=mock_video_id)
    mock_yt_api_class = mocker.patch.object(testee, 'YouTubeTranscriptApi')
    mock_yt_api_instance = mock_yt_api_class.return_value
    mock_yt_api_instance.list.side_effect = testee.TranscriptsDisabled(mock_video_id)
    result = downloader.download()
    assert result is None
    testee.get_video_id.assert_called_once_with(downloader.url)
    mock_yt_api_instance.list.assert_called_once_with(mock_video_id)


def test_download_no_matching_language(mocker, downloader):
    """Test when no matching language is found."""
    mock_video_id = 'test_video_id'
    mocker.patch.object(testee, 'get_video_id', return_value=mock_video_id)
    mock_yt_api_class = mocker.patch.object(testee, 'YouTubeTranscriptApi')
    mock_yt_api_instance = mock_yt_api_class.return_value
    mock_transcript_list = MagicMock()
    mock_yt_api_instance.list.return_value = mock_transcript_list
    mock_transcript_metadata_fr = MagicMock()
    mock_transcript_metadata_fr.language_code = 'fr'
    mock_transcript_list.__iter__.return_value = iter([mock_transcript_metadata_fr])
    mocker.patch.object(testee, 'get_first_matching_lang_code', return_value=None)
    result = downloader.download()
    assert result is None
    testee.get_video_id.assert_called_once_with(downloader.url)
    mock_yt_api_instance.list.assert_called_once_with(mock_video_id)
    mock_transcript_list.find_transcript.assert_not_called()


def test_download_no_transcript_found(mocker, downloader):
    """Test when transcript is listed but not found."""
    mock_video_id = 'test_video_id'
    mocker.patch.object(testee, 'get_video_id', return_value=mock_video_id)
    mock_yt_api_class = mocker.patch.object(testee, 'YouTubeTranscriptApi')
    mock_yt_api_instance = mock_yt_api_class.return_value
    mock_transcript_list = MagicMock()
    mock_yt_api_instance.list.return_value = mock_transcript_list
    mock_transcript_metadata_en = MagicMock()
    mock_transcript_metadata_en.language_code = 'en'
    mock_transcript_list.__iter__.return_value = iter([mock_transcript_metadata_en])
    mocker.patch.object(testee, 'get_first_matching_lang_code', return_value='en')
    mock_transcript_list.find_transcript.return_value.fetch.side_effect = testee.NoTranscriptFound(mock_video_id, ['en'], {})
    result = downloader.download()
    assert result is None
    mock_transcript_list.find_transcript.assert_called_once_with(['en'])


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
