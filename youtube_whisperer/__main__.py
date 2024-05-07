import argparse
from pathlib import Path

from youtube_whisperer.segment_to_srt_adaptor import convert_segments_file_to_srt
from youtube_whisperer.transcript_downloader import download_transcript_as_srt_file
from youtube_whisperer.utils import is_url
from youtube_whisperer.video_downloader import download_video_with_default_title
from youtube_whisperer.waveform_transcriber import transcribe_file_with_default_model


def main() -> None:
    """
    CLI entry point to transcribe waveform files and save each result to a Segment file and an SRT file.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("sources", nargs='+', metavar='N', help="Waveform file paths to transcribe, or video URLs to download and transcribe.")
    for source in parser.parse_args().sources:
        if is_url(source):
            waveform_file_path = download_video_with_default_title(source)
            if download_transcript_as_srt_file(source, waveform_file_path.with_suffix('.srt')):
                continue
        else:
            waveform_file_path = Path(source)
        segment_file_path = transcribe_file_with_default_model(waveform_file_path)
        print('Saved Segments file:', segment_file_path)
        srt_file_path = convert_segments_file_to_srt(segment_file_path, deduplicate=True)
        print('Saved SRT file:', srt_file_path)


if __name__ == "__main__":
    main()
