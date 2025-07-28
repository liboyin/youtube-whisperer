import pytest
from pathlib import Path
from unittest.mock import MagicMock
from pathlib_extensions import OverwriteMode

import youtube_whisperer.downloaders.transcript_downloader as testee
from youtube_whisperer.downloaders.transcript_downloader import (
    get_video_id, 
    get_first_matching_lang_code,
    download_transcript,
    download_transcript_as_srt_text,
    download_transcript_as_srt_file,
    download_transcript_as_srt_file_with_default_title,
)


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


def test_download_transcript_success(mocker):
    """Test successful transcript download."""
    mock_video_id = 'test_video_id'
    mock_url = f'https://www.youtube.com/watch?v={mock_video_id}'
    mock_lang_codes = 'en'
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
    mock_transcript_list.__iter__.return_value = [mock_transcript_metadata_en, mock_transcript_metadata_fr]
    mock_transcript_list.find_transcript.return_value.fetch.return_value = expected_transcript
    result = download_transcript(mock_url, mock_lang_codes)
    assert result == expected_transcript
    testee.get_video_id.assert_called_once_with(mock_url)
    mock_yt_api_class.assert_called_once_with()
    mock_yt_api_instance.list.assert_called_once_with(mock_video_id)
    mock_transcript_list.find_transcript.assert_called_once_with(['en'])


def test_download_transcript_disabled(mocker):
    """Test when transcripts are disabled."""
    mock_video_id = 'test_video_id'
    mock_url = f'https://www.youtube.com/watch?v={mock_video_id}'
    mocker.patch.object(testee, 'get_video_id', return_value=mock_video_id)
    mock_yt_api_class = mocker.patch.object(testee, 'YouTubeTranscriptApi')
    mock_yt_api_instance = mock_yt_api_class.return_value
    mock_yt_api_instance.list.side_effect = testee.TranscriptsDisabled(mock_video_id)
    result = download_transcript(mock_url, 'en')
    assert result is None
    testee.get_video_id.assert_called_once_with(mock_url)
    mock_yt_api_instance.list.assert_called_once_with(mock_video_id)


def test_download_transcript_no_matching_language(mocker):
    """Test when no matching language is found."""
    mock_video_id = 'test_video_id'
    mock_url = f'https://www.youtube.com/watch?v={mock_video_id}'
    mocker.patch.object(testee, 'get_video_id', return_value=mock_video_id)
    mock_yt_api_class = mocker.patch.object(testee, 'YouTubeTranscriptApi')
    mock_yt_api_instance = mock_yt_api_class.return_value
    mock_transcript_list = MagicMock()
    mock_yt_api_instance.list.return_value = mock_transcript_list
    mock_transcript_metadata_fr = MagicMock()
    mock_transcript_metadata_fr.language_code = 'fr'
    mock_transcript_list.__iter__.return_value = [mock_transcript_metadata_fr]
    result = download_transcript(mock_url, 'en')
    assert result is None
    testee.get_video_id.assert_called_once_with(mock_url)
    mock_yt_api_instance.list.assert_called_once_with(mock_video_id)
    mock_transcript_list.find_transcript.assert_not_called()


def test_download_transcript_default_lang_codes(mocker):
    """Test using default language codes when None is passed."""
    mock_video_id = 'test_video_id'
    mock_url = f'https://www.youtube.com/watch?v={mock_video_id}'
    expected_transcript = [{'text': 'hello', 'start': 0.0, 'duration': 1.0}]
    mocker.patch.object(testee, 'get_video_id', return_value=mock_video_id)
    mock_yt_api_class = mocker.patch.object(testee, 'YouTubeTranscriptApi')
    mock_yt_api_instance = mock_yt_api_class.return_value
    mock_transcript_list = MagicMock()
    mock_yt_api_instance.list.return_value = mock_transcript_list
    mock_transcript_metadata_en = MagicMock()
    mock_transcript_metadata_en.language_code = 'en'
    mock_transcript_metadata_zh = MagicMock()
    mock_transcript_metadata_zh.language_code = 'zh'
    mock_transcript_list.__iter__.return_value = [mock_transcript_metadata_en, mock_transcript_metadata_zh]
    mock_transcript_list.find_transcript.return_value.fetch.return_value = expected_transcript
    result = download_transcript(mock_url, None)
    assert result == expected_transcript
    testee.get_video_id.assert_called_once_with(mock_url)
    mock_yt_api_instance.list.assert_called_once_with(mock_video_id)
    mock_transcript_list.find_transcript.assert_called_once_with(['en'])


def test_download_transcript_as_srt_text_success(mocker):
    """Test successful SRT text generation."""
    mock_transcript_body = [
        {'text': 'Hello world', 'start': 0.0, 'end': 2.0},
        {'text': 'This is a test', 'start': 2.0, 'end': 4.0}
    ]
    mocker.patch.object(testee, 'download_transcript', return_value=mock_transcript_body)
    mock_formatter = mocker.patch.object(testee, 'SRTFormatter')
    mock_formatter_instance = mock_formatter.return_value
    mock_formatter_instance.format_transcript.return_value = "1\n00:00:00,000 --> 00:00:02,000\nHello world\n\n2\n00:00:02,000 --> 00:00:04,000\nThis is a test\n\n"
    result = download_transcript_as_srt_text('https://youtube.com/watch?v=test', 'en')
    assert result == "1\n00:00:00,000 --> 00:00:02,000\nHello world\n\n2\n00:00:02,000 --> 00:00:04,000\nThis is a test\n\n"
    mock_formatter_instance.format_transcript.assert_called_once_with(mock_transcript_body)


def test_download_transcript_as_srt_text_no_transcript(mocker):
    """Test when no transcript is available."""
    mocker.patch.object(testee, 'download_transcript', return_value=None)
    result = download_transcript_as_srt_text('https://youtube.com/watch?v=test', 'en')
    assert result is None


def test_download_transcript_as_srt_file_success(mocker, tmp_path):
    """Test successful SRT file creation."""
    mock_srt_text = "1\n00:00:00,000 --> 00:00:02,000\nHello world\n\n"
    output_path = tmp_path / "output.srt"
    mocker.patch.object(testee, 'download_transcript_as_srt_text', return_value=mock_srt_text)
    mocker.patch.object(testee, 'overwrite_existing_path', return_value=True)
    mock_Path = MagicMock()
    mock_prepare_output_file = mocker.patch.object(testee, 'prepare_output_file', return_value=mock_Path)
    mocker.patch.object(Path, 'is_file', return_value=False)
    result = download_transcript_as_srt_file('https://youtube.com/watch?v=test', 'en', output_path, OverwriteMode.ALWAYS)
    assert result is True
    mock_prepare_output_file.assert_called_once_with(output_path)
    mock_Path.write_text.assert_called_once_with(mock_srt_text)


def test_download_transcript_as_srt_file_exists_no_overwrite(mocker, tmp_path):
    """Test when file exists and overwrite is not allowed."""
    output_path = tmp_path / "output.srt"
    mocker.patch.object(Path, 'is_file', return_value=True)
    mocker.patch.object(testee, 'overwrite_existing_path', return_value=False)
    result = download_transcript_as_srt_file('https://youtube.com/watch?v=test', 'en', output_path, OverwriteMode.NEVER)
    assert result is True


def test_download_transcript_as_srt_file_no_transcript(mocker, tmp_path):
    """Test when no transcript is available."""
    output_path = tmp_path / "output.srt"
    mocker.patch.object(Path, 'is_file', return_value=False)
    mocker.patch.object(testee, 'download_transcript_as_srt_text', return_value=None)
    result = download_transcript_as_srt_file('https://youtube.com/watch?v=test', 'en', output_path, OverwriteMode.ALWAYS)
    assert result is False


def test_download_transcript_as_srt_file_with_default_title_success(mocker, tmp_path):
    """Test with custom parameters."""
    mock_title = "Test Video"
    output_path = tmp_path / f"{mock_title}.srt"
    mocker.patch.object(testee, 'get_video_title', return_value=mock_title)
    mocker.patch.object(testee, 'download_transcript_as_srt_file', return_value=True)
    result = download_transcript_as_srt_file_with_default_title(
        'https://youtube.com/watch?v=test',
        target_dir=tmp_path,
        overwrite=OverwriteMode.NEVER,
    )
    assert result == output_path


def test_download_transcript_as_srt_file_with_default_title_failure(mocker):
    """Test failure case."""
    mocker.patch.object(testee, 'get_video_title', return_value="Test Video")
    mocker.patch.object(testee, 'download_transcript_as_srt_file', return_value=False)
    result = download_transcript_as_srt_file_with_default_title(
        'https://youtube.com/watch?v=test',
        overwrite=OverwriteMode.NEVER,
    )
    assert result is None
