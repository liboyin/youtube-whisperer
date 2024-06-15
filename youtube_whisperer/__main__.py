import argparse
from pathlib import Path

from youtube_whisperer.segment_to_srt_adaptor import convert_segments_file_to_srt
from youtube_whisperer.transcript_downloader import download_transcript_as_srt_file
from youtube_whisperer.utils import is_url, get_verified_language
from youtube_whisperer.video_downloader import download_video_with_default_title
from youtube_whisperer.waveform_transcriber import transcribe_file_with_default_model


def main() -> None:
    """
    CLI entry point to transcribe waveform files and save each result to a Segment file and an SRT file.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("sources", nargs='+', metavar='N', help="Waveform file paths to transcribe, or video URLs to download and transcribe.")
    parser.add_argument("-l", "--language", type=str, default=None, help="Language for transcription")
    language = get_verified_language(parser.parse_args().language)
    lang_codes = [language] if language else None
    for source in parser.parse_args().sources:
        # downloaders do not overwrite by default because they are almost transactional
        if is_url(source):
            waveform_file_path = download_video_with_default_title(source)
            if download_transcript_as_srt_file(source, waveform_file_path.with_suffix('.srt'), lang_codes):
                continue
        else:
            waveform_file_path = Path(source)
        # local operations overwrite by default because they may fail half way through
        segment_file_path = transcribe_file_with_default_model(waveform_file_path)
        print('Saved Segments file:', segment_file_path)
        srt_file_path = convert_segments_file_to_srt(segment_file_path, deduplicate=True)
        print('Saved SRT file:', srt_file_path)


if __name__ == "__main__":
    main()
