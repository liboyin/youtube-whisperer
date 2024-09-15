import argparse
from pathlib import Path

from youtube_whisperer.playlist_downloader import get_video_urls_from_playlist
from youtube_whisperer.segment_to_srt_adaptor import convert_segments_file_to_srt
from youtube_whisperer.transcript_downloader import download_transcript_as_srt_file
from youtube_whisperer.utils import is_url, get_verified_language
from youtube_whisperer.video_downloader import download_video_with_default_title
from youtube_whisperer.waveform_transcriber import transcribe_file_with_default_model


def get_video_urls_and_file_paths(sources: list[str]) -> tuple[list[str], list[Path]]:
    """
    Extract video URLs and file paths from a list of sources.

    Args:
        sources (list[str]): A list containing video URLs, playlist URLs, or paths to video files.

    Returns:
        tuple[list[str], list[Path]]: A tuple containing a list of video URLs and a list of video file paths.
    """
    video_urls = []
    video_file_paths = []
    for source in sources:
        if is_url(source):
            if 'playlist' in source:
                video_urls.extend(get_video_urls_from_playlist(source))
            else:
                video_urls.append(source)
        else:
            video_file_paths.append(Path(source))
    return video_urls, video_file_paths


def main() -> None:
    """
    CLI entry point to transcribe waveform files and save each result to a Segment file and an SRT file.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("sources", nargs='+', metavar='source', help="Waveform file paths to transcribe, or video URLs to download and transcribe.")
    parser.add_argument("-l", "--language", type=str, default=None, help="Language for transcription")
    args = parser.parse_args()
    language = get_verified_language(args.language)
    lang_codes = [language] if language else None
    video_urls, video_file_paths = get_video_urls_and_file_paths(args.sources)
    for video_url in video_urls:
        # downloaders do not overwrite by default because they are almost transactional
        video_file_path = download_video_with_default_title(video_url)
        if not download_transcript_as_srt_file(video_url, video_file_path.with_suffix('.srt'), lang_codes):
            video_file_paths.append(video_file_path)
    for video_file_path in video_file_paths:
        # local operations overwrite by default because they may fail half way through
        segment_file_path = transcribe_file_with_default_model(video_file_path, language=language)
        print('Saved Segments file:', segment_file_path)
        srt_file_path = convert_segments_file_to_srt(segment_file_path, deduplicate=True)
        print('Saved SRT file:', srt_file_path)


if __name__ == "__main__":
    main()
