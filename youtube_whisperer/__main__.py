import argparse
from pathlib import Path

from youtube_whisperer.pathlib_extensions import prepare_output_file
from youtube_whisperer.segment_to_srt_adaptor import yield_deduplicated_srt_blocks, yield_srt_blocks_from_segments
from youtube_whisperer.srt_deduplicator import convert_srt_blocks_to_str
from youtube_whisperer.utils import is_url
from youtube_whisperer.video_downloader import download_video_with_default_title
from youtube_whisperer.waveform_loader import load_waveform_from_file
from youtube_whisperer.waveform_transcriber import duplicate_segments_to_file, transcribe_waveform_with_default_model


def main() -> None:
    """
    CLI entry point to transcribe waveform files and save each result to a Segment file and an SRT file.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("sources", nargs='+', metavar='N', help="Waveform file paths to transcribe, or video URLs to download and transcribe.")
    for source in parser.parse_args().sources:
        input_file_path = download_video_with_default_title(source) if is_url(source) else Path(source)
        segments_generator = transcribe_waveform_with_default_model(load_waveform_from_file(input_file_path))
        segments_generator = duplicate_segments_to_file(segments_generator, input_file_path.with_suffix('.seg'))
        srt_blocks_generator = yield_deduplicated_srt_blocks(yield_srt_blocks_from_segments(segments_generator))
        output_file_path = prepare_output_file(input_file_path.with_suffix('.srt'))
        output_file_path.write_text(convert_srt_blocks_to_str(srt_blocks_generator))


if __name__ == "__main__":
    main()
