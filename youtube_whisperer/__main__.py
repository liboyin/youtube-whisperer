from pathlib import Path

from youtube_whisperer.pathlib_extensions import prepare_input_file, prepare_output_file
from youtube_whisperer.segment_to_srt_adaptor import yield_deduplicated_srt_blocks, yield_srt_blocks_from_segments
from youtube_whisperer.srt_deduplicator import convert_srt_blocks_to_str
from youtube_whisperer.waveform_loader import load_waveform_from_file
from youtube_whisperer.waveform_transcriber import transcribe_waveform_with_default_model


if __name__ == '__main__':
    input_file_path = prepare_input_file(Path.home() / '.whisper/MIT教授：如何终身学习？｜科学哲学玄学的关系｜Kevin教授_3_3.mp4')
    output_file_path = prepare_output_file(input_file_path.with_suffix('.srt'))
    segments_generator = transcribe_waveform_with_default_model(load_waveform_from_file(input_file_path))
    srt_blocks_generator = yield_deduplicated_srt_blocks(yield_srt_blocks_from_segments(segments_generator))
    output_file_path.write_text(convert_srt_blocks_to_str(srt_blocks_generator))
