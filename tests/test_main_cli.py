from pathlib import Path
from types import SimpleNamespace

import pytest
from pathlib_extensions import OverwriteMode

from youtube_whisperer.adaptors.lang_code_adaptor import LanguageCode
import youtube_whisperer.__main__ as testee
from youtube_whisperer.utils import TranscriberMode, TranscriberType


LANGUAGE = LanguageCode("en")


def test_try_download_videos_and_transcripts_collects_only_missing_transcripts(mocker):
    mocker.patch.object(
        testee,
        "yield_flattened_video_urls",
        return_value=iter(["url-1", "url-2"]),
    )
    mock_download = mocker.patch.object(
        testee,
        "download_video_and_transcript_with_default_title",
        side_effect=[
            (Path("/tmp/one.mp4"), True),
            (Path("/tmp/two.mp4"), False),
        ],
    )

    result = testee.try_download_videos_and_transcripts(
        ["playlist-url"],
        LANGUAGE,
        overwrite=OverwriteMode.NEVER,
    )

    assert result == [Path("/tmp/two.mp4")]
    assert mock_download.call_args_list == [
        mocker.call("url-1", LANGUAGE, overwrite=OverwriteMode.NEVER),
        mocker.call("url-2", LANGUAGE, overwrite=OverwriteMode.NEVER),
    ]


def test_transcribe_to_srt_files_routes_to_azure_and_local_and_prints(mocker, capsys):
    azure = mocker.patch.object(testee, "transcribe_audio_file", return_value=Path("/tmp/azure.srt"))
    local = mocker.patch.object(
        testee,
        "transcribe_file_with_default_model",
        side_effect=[Path("/tmp/local.srt"), None],
    )

    testee.transcribe_to_srt_files(
        [Path("/tmp/azure.wav")],
        LANGUAGE,
        transcriber=TranscriberType.AZURE,
        overwrite=OverwriteMode.ALWAYS,
    )
    testee.transcribe_to_srt_files(
        [Path("/tmp/local-1.wav"), Path("/tmp/local-2.wav")],
        LANGUAGE,
        transcriber=TranscriberType.LOCAL,
        mode=TranscriberMode.TRANSLATE,
        overwrite=OverwriteMode.NEVER,
    )

    assert azure.call_args_list == [
        mocker.call(Path("/tmp/azure.wav"), LANGUAGE, overwrite=OverwriteMode.ALWAYS),
    ]
    assert local.call_args_list == [
        mocker.call(
            Path("/tmp/local-1.wav"),
            language=LANGUAGE,
            mode=TranscriberMode.TRANSLATE,
            overwrite=OverwriteMode.NEVER,
        ),
        mocker.call(
            Path("/tmp/local-2.wav"),
            language=LANGUAGE,
            mode=TranscriberMode.TRANSLATE,
            overwrite=OverwriteMode.NEVER,
        ),
    ]
    output = capsys.readouterr().out
    assert "Saved SRT file: /tmp/azure.srt" in output
    assert "Saved SRT file: /tmp/local.srt" in output
    assert "Failed to transcribe file: /tmp/local-2.wav" in output


def test_transcribe_to_srt_files_rejects_unsupported_transcriber():
    with pytest.raises(ValueError, match="Unsupported transcriber type"):
        testee.transcribe_to_srt_files(
            [Path("/tmp/input.wav")],
            LANGUAGE,
            transcriber="remote",
        )


def test_main_partitions_sources_and_passes_arguments(mocker):
    args = SimpleNamespace(
        sources=["https://example.com/video", "local.wav"],
        language=LANGUAGE,
        transcriber=TranscriberType.AZURE,
        mode=TranscriberMode.TRANSLATE,
        overwrite=OverwriteMode.NEVER,
    )
    mocker.patch("argparse.ArgumentParser.parse_args", return_value=args)
    mock_downloads = mocker.patch.object(
        testee,
        "try_download_videos_and_transcripts",
        return_value=[Path("/tmp/downloaded.wav")],
    )
    mock_transcribe = mocker.patch.object(testee, "transcribe_to_srt_files")

    testee.main()

    mock_downloads.assert_called_once_with(
        ["https://example.com/video"],
        LANGUAGE,
        OverwriteMode.NEVER,
    )
    transcribe_args = mock_transcribe.call_args.args
    assert list(transcribe_args[0]) == [Path("/tmp/downloaded.wav"), Path("local.wav")]
    assert transcribe_args[1:] == (
        LANGUAGE,
        TranscriberType.AZURE,
        TranscriberMode.TRANSLATE,
        OverwriteMode.NEVER,
    )
