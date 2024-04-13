from pathlib import Path

import ffmpeg

from youtube_whisperer.pathlib_extensions import prepare_output_file


def encode_video_from_file(input_file: Path, output_file: Path | None = None) -> Path:
    """
    Encode a video file to MP4 with H.264 video codec and AAC audio codec.

    cmd = [
        'ffmpeg',
        '-i', input_file,
        '-c:v', 'libx264',  # sets video codec to H.264
        '-c:a', 'aac',  # sets audio codec to AAC
        '-b:a', '160k',  # sets audio bitrate to 160 kbps
        '-ac', '2',  # sets audio channel to stereo
        '-f', 'mp4',  # saves output in an MP4 container
        '-'  # output to stdout instead of a file
    ]

    Args:
        input_file (Path): The path to the input video file.
        output_file (Path, optional): The path to the output MP4 file. If not provided, a path with the same name as the input file and .mp4 extension will be used.

    Returns:
        Path: The path to the encoded MP4 file.
    """
    if output_file is None:
        output_file = input_file.with_suffix('.mp4')
    assert input_file != output_file
    output_file = prepare_output_file(output_file)
    stream = (
        ffmpeg
        .input(str(input_file), threads=0)
        # TODO: output target must be seekable. Is it possible to use a buffer instead of a file?
        .output(str(output_file), vcodec='libx264', acodec='aac', audio_bitrate='160k', ac=2, format='mp4')
    )
    print(f'ffmpeg args: {stream.get_args()}')
    try:
        stream.run(input=input_file.read_bytes(), capture_stdout=True, capture_stderr=True, overwrite_output=True)
    except ffmpeg.Error as e:
        print(e.stderr.decode())
        raise
    return output_file


if __name__ == '__main__':
    input_file = Path.home() / '.whisper/test.mp4'
    output_file = Path.home() / '.whisper/test.out.mp4'
    encode_video_from_file(input_file, output_file)
