from pathlib import Path

import ffmpeg

from youtube_whisperer.pathlib_extensions import prepare_output_file


def encode_video_from_bytes(data: bytes) -> bytes:
    """
    Encode a video from a bytes object with NVENC H.264 video codec and AAC audio codec.

    cmd = [
        'ffmpeg',
        '-i', input_file,
        '-c:v', 'h264_nvenc',  # set video codec to NVENC H.264
        '-cq', '27',  # set constant quality level to 27
        '-c:a', 'aac',  # set audio codec to AAC
        '-b:a', '160k',  # set audio bitrate to 160 kbps
        '-ac', '2',  # set audio channel to stereo
        '-f', 'mp4',  # save output in an MP4 container
        "-"  # output to stdout instead of a file
    ]
    """
    stream = (
        ffmpeg
        .input('pipe:', format='mp4')
        .output('pipe:', vcodec='h264_nvenc', cq=27, acodec='aac', audio_bitrate='160k', ac=2, format='mp4')
    )
    print(f'ffmpeg args: {stream.get_args()}')
    out, err = stream.run(input=data, capture_stdout=True, capture_stderr=True)
    print(err.decode())
    return out


def encode_video_from_file(input_file: Path, output_file: Path | None = None) -> Path:
    """
    Encode a video from a file to an MP4 file with NVENC H.264 video codec and AAC audio codec.

    Args:
        input_file (Path): The path to the input video file.
        output_file (Path, optional): The path to the output MP4 file. If not provided, a path with the same name as the input file and .mp4 extension will be used.

    Returns:
        Path: The path to the encoded MP4 file.
    """
    if output_file is None:
        output_file = input_file.with_suffix('.mp4')
    result = encode_video_from_bytes(input_file.read_bytes())
    prepare_output_file(output_file).write_bytes(result)
    return output_file
