from unittest.mock import patch

import pytest
from pathlib_extensions import OverwriteMode

from youtube_whisperer.adaptors.lang_code_adaptor import LanguageCode


@pytest.mark.parametrize('explicit', [False, True])
def test_combined_download_resolves_one_current_asset_directory(mocker, monkeypatch, tmp_path, explicit):
    """Combined download observes current defaults once and preserves explicit positional paths."""
    import youtube_whisperer.downloaders as testee

    download = mocker.patch.object(testee, 'download_video_with_default_title', return_value=tmp_path / 'video.mp4')
    transcript = mocker.patch.object(testee, 'TranscriptDownloader').return_value
    for name in ['first', 'second']:
        target = tmp_path / name
        monkeypatch.setenv('WHISPER_ASSETS_DIR', str(target))
        if explicit:
            with patch.object(testee, 'Settings', side_effect=AssertionError('settings construction')):
                result = testee.download_video_and_transcript_with_default_title('owned-url', LanguageCode('en'), target, OverwriteMode.NEVER)
        else:
            result = testee.download_video_and_transcript_with_default_title('owned-url', LanguageCode('en'), overwrite=OverwriteMode.NEVER)
        download.assert_called_with('owned-url', target, OverwriteMode.NEVER)
        transcript.download_as_srt_file.assert_called_with(tmp_path / 'video.srt', OverwriteMode.NEVER)
        assert result[0] == tmp_path / 'video.mp4'


@pytest.mark.parametrize('explicit', [False, True])
def test_video_title_download_observes_current_asset_directory(mocker, monkeypatch, tmp_path, explicit):
    """Video default titles preserve explicit paths and resolve missing paths at invocation."""
    import youtube_whisperer.downloaders.video_downloader as testee

    mocker.patch.object(testee, 'get_video_title', return_value='owned-title')
    download = mocker.patch.object(testee, 'download_video')
    for name in ['first', 'second']:
        target = tmp_path / name
        monkeypatch.setenv('WHISPER_ASSETS_DIR', str(target))
        if explicit:
            with patch.object(testee, 'Settings', side_effect=AssertionError('settings construction')):
                result = testee.download_video_with_default_title('owned-url', target, OverwriteMode.NEVER)
        else:
            result = testee.download_video_with_default_title('owned-url', overwrite=OverwriteMode.NEVER)
        assert result == target / 'owned-title.mp4'
        download.assert_called_with('owned-url', result, overwrite=OverwriteMode.NEVER)


@pytest.mark.parametrize('explicit', [False, True])
def test_transcript_title_download_observes_current_asset_directory(mocker, monkeypatch, tmp_path, explicit):
    """Transcript default titles preserve explicit paths and resolve missing paths at invocation."""
    import youtube_whisperer.downloaders.transcript_downloader as testee

    mocker.patch.object(testee, 'get_video_title', return_value='owned-title')
    download = mocker.patch.object(testee.TranscriptDownloader, 'download_as_srt_file', return_value=True)
    downloader = testee.TranscriptDownloader('https://youtu.be/owned', LanguageCode('en'))
    for name in ['first', 'second']:
        target = tmp_path / name
        monkeypatch.setenv('WHISPER_ASSETS_DIR', str(target))
        if explicit:
            with patch.object(testee, 'Settings', side_effect=AssertionError('settings construction')):
                result = downloader.download_as_srt_file_with_default_title(target, OverwriteMode.NEVER)
        else:
            result = downloader.download_as_srt_file_with_default_title(overwrite=OverwriteMode.NEVER)
        assert result == target / 'owned-title.srt'
        download.assert_called_with(result, overwrite=OverwriteMode.NEVER)


@pytest.mark.parametrize('explicit', [False, True])
def test_playlist_title_download_resolves_one_directory_for_entire_invocation(mocker, monkeypatch, tmp_path, explicit):
    """Playlist downloads keep one resolved directory even when environment changes mid-expansion."""
    import youtube_whisperer.downloaders.playlist_downloader as testee

    download = mocker.patch.object(testee, 'download_video_with_default_title', return_value=tmp_path / 'video.mp4')
    for name in ['first', 'second']:
        target = tmp_path / name
        monkeypatch.setenv('WHISPER_ASSETS_DIR', str(target))

        def expand(_url):
            """Mutate owned environment between videos without changing this invocation's path."""
            yield 'one'
            monkeypatch.setenv('WHISPER_ASSETS_DIR', str(tmp_path / 'changed'))
            yield 'two'

        mocker.patch.object(testee, 'yield_video_urls_from_playlist', side_effect=expand)
        if explicit:
            with patch.object(testee, 'Settings', side_effect=AssertionError('settings construction')):
                result = testee.download_playlist_with_default_titles('owned-url', target, OverwriteMode.NEVER)
        else:
            result = testee.download_playlist_with_default_titles('owned-url', overwrite=OverwriteMode.NEVER)
        assert result == [tmp_path / 'video.mp4'] * 2
        assert download.call_args_list[-2:] == [
            mocker.call('one', target, OverwriteMode.NEVER), mocker.call('two', target, OverwriteMode.NEVER),
        ]
