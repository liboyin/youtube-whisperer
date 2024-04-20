from pathlib import Path

from youtube_whisperer.waveform_loader import load_waveform_from_file
from youtube_whisperer.waveform_transcriber import transcribe_waveform_with_default_model
from youtube_whisperer.srt_deduplicator import convert_srt_blocks_to_str

if __name__ == '__main__':
    input_file_path = Path.home() / '.whisper/MIT教授：如何终身学习？｜科学哲学玄学的关系｜Kevin教授_3_3.mp4'
    srt_blocks = transcribe_waveform_with_default_model(load_waveform_from_file(input_file_path))
    input_file_path.with_suffix('.srt').write_text(convert_srt_blocks_to_str(srt_blocks))
