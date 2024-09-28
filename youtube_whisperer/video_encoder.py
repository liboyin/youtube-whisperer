from pathlib import Path

import ffmpeg
from pathlib_extensions import prepare_input_file, prepare_output_file

from youtube_whisperer.utils import WHISPER_HOME_DIR, WHISPER_OVERWRITE


def encode_video_from_file(input_file_path: Path, output_file_path: Path | None = None) -> Path:
    """
    Encodes a video file to MP4 with H.264 video codec and AAC audio codec. Equivalent to the following command:

    cmd = [
        'ffmpeg',
        '-i', input_file_path,
        '-c:v', 'libx264',  # sets video codec to H.264
        '-c:a', 'aac',  # sets audio codec to AAC
        '-b:a', '160k',  # sets audio bitrate to 160 kbps
        '-ac', '2',  # sets audio channel to stereo
        '-f', 'mp4',  # saves output in an MP4 container
        output_file_path
    ]

    Args:
        input_file_path (Path): The path to the input video file.
        output_file_path (Path, optional): The path to the output MP4 file. If not provided, a path with the same name as the input file and .mp4 extension will be used.

    Returns:
        Path: The path to the encoded MP4 file.
    """
    prepare_input_file(input_file_path)
    output_file_path = prepare_output_file(output_file_path or input_file_path.with_suffix('.mp4'))
    assert input_file_path != output_file_path
    stream = (
        ffmpeg
        .input(str(input_file_path), threads=0)
        # TODO: output target must be seekable. Is it possible to use a buffer instead of a file?
        .output(str(output_file_path), vcodec='libx264', acodec='aac', audio_bitrate='160k', ac=2, format='mp4')
    )
    print('ffmpeg args:', stream.get_args())
    try:
        stream.run(input=input_file_path.read_bytes(), capture_stdout=True, capture_stderr=True, overwrite_output=WHISPER_OVERWRITE)
    except ffmpeg.Error as e:
        print(e.stderr.decode())
        raise
    return output_file_path


if __name__ == '__main__':
    input_file_path = WHISPER_HOME_DIR / 'test.mp4'
    output_file_path = WHISPER_HOME_DIR / 'test.out.mp4'
    encode_video_from_file(input_file_path, output_file_path)
