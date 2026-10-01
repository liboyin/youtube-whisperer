from pathlib_extensions import OverwriteMode

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
