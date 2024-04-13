from pathlib import Path

from youtube_whisperer.waveform_loader import load_waveform_from_file
from youtube_whisperer.waveform_transcriber import transcribe_waveform_with_default_model
from youtube_whisperer.srt_deduplicator import srt_blocks_to_str

if __name__ == '__main__':
    input_file = Path.home() / '.whisper/test.mp4'
    srt_blocks = transcribe_waveform_with_default_model(load_waveform_from_file(input_file))
    input_file.with_suffix('.srt').write_text(srt_blocks_to_str(srt_blocks))
