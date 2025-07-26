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
    # Mock the API components
    mock_transcript_obj = MagicMock()
    mock_transcript_obj.language_code = 'en-US'
    
    # Mock the transcript_list object
    mock_transcript_list = MagicMock()
    mock_transcript_list.__iter__ = lambda self: iter([mock_transcript_obj])  # Make it iterable
    
    mock_transcript_fetch = MagicMock()
    mock_transcript_fetch.fetch.return_value = [
        {'text': 'Hello world', 'start': 0.0, 'end': 2.0},
        {'text': 'This is a test', 'start': 2.0, 'end': 4.0}
    ]
    mock_transcript_list.find_transcript.return_value = mock_transcript_fetch
    
    mock_transcript_api = mocker.patch.object(testee, 'YouTubeTranscriptApi')
    mock_transcript_api.list_transcripts.return_value = mock_transcript_list
    
    # Mock get_video_id
    mocker.patch.object(testee, 'get_video_id', return_value='test_id')
    
    result = download_transcript('https://youtube.com/watch?v=test', 'en')
    
    assert result is not None
    assert len(result) == 2
    assert result[0]['text'] == 'Hello world'
    assert result[0]['start'] == 0.0
    assert result[0]['end'] == 2.0
    
    mock_transcript_api.list_transcripts.assert_called_once_with('test_id')
    mock_transcript_list.find_transcript.assert_called_once_with(['en-US'])


def test_download_transcript_disabled(mocker):
    """Test when transcripts are disabled."""
    from youtube_transcript_api import TranscriptsDisabled
    
    mock_transcript_api = mocker.patch.object(testee, 'YouTubeTranscriptApi')
    mock_transcript_api.list_transcripts.side_effect = TranscriptsDisabled('test_id')
    mocker.patch.object(testee, 'get_video_id', return_value='test_id')
    result = download_transcript('https://youtube.com/watch?v=test', 'en')
    assert result is None


def test_download_transcript_no_matching_language(mocker):
    """Test when no matching language is found."""
    mock_transcript_obj = MagicMock()
    mock_transcript_obj.language_code = 'fr'
    mock_transcript_list = MagicMock()
    mock_transcript_list.__iter__ = lambda self: iter([mock_transcript_obj])
    mock_transcript_api = mocker.patch.object(testee, 'YouTubeTranscriptApi')
    mock_transcript_api.list_transcripts.return_value = mock_transcript_list
    mocker.patch.object(testee, 'get_video_id', return_value='test_id')
    result = download_transcript('https://youtube.com/watch?v=test', 'en;zh')
    assert result is None


def test_download_transcript_default_lang_codes(mocker):
    """Test using default language codes when None is passed."""
    mock_transcript_obj = MagicMock()
    mock_transcript_obj.language_code = 'en-US'
    mock_transcript_list = MagicMock()
    mock_transcript_list.__iter__ = lambda self: iter([mock_transcript_obj])
    mock_transcript_fetch = MagicMock()
    mock_transcript_body = {'text': 'test', 'start': 0.0, 'end': 1.0}
    mock_transcript_fetch.fetch.return_value = [mock_transcript_body]
    mock_transcript_list.find_transcript.return_value = mock_transcript_fetch
    mock_transcript_api = mocker.patch.object(testee, 'YouTubeTranscriptApi')
    mock_transcript_api.list_transcripts.return_value = mock_transcript_list
    mocker.patch.object(testee, 'get_video_id', return_value='test_id')
    result = download_transcript('https://youtube.com/watch?v=test', None)
    assert result is not None
    assert len(result) == 1
    assert result[0] == mock_transcript_body


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
