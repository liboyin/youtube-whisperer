import argparse
from pathlib import Path
import time

import ffmpeg
from pathlib_extensions import OverwriteMode, overwrite_existing_path, prepare_input_dir, prepare_input_file, prepare_output_file

from youtube_whisperer.utils import WHISPER_ASSETS_DIR


def encode_to_mp4(input_file_path: Path, output_file_path: Path | None = None, overwrite: OverwriteMode = OverwriteMode.PROMPT) -> Path:
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
        overwrite (OverwriteMode, optional): Whether to overwrite `output_file_path` if it already exists. Defaults to `OverwriteMode.PROMPT`.

    Returns:
        Path: The path to the encoded MP4 file.
    """
    prepare_input_file(input_file_path)
    output_file_path = output_file_path or input_file_path.with_suffix('.mp4')
    if output_file_path.is_file() and not overwrite_existing_path(output_file_path, overwrite):
        return output_file_path
    prepare_output_file(output_file_path)
    assert isinstance(output_file_path, Path)  # narrow down type from `Path | None` to `Path`
    stream = (
        ffmpeg
        .input(str(input_file_path), threads=0)  # ffmpeg automatically detects the optimal number of threads
        # TODO: output target must be seekable. Is it possible to use a buffer instead of a file?
        .output(str(output_file_path), vcodec='libx264', acodec='aac', audio_bitrate='160k', ac=2, format='mp4')
    )
    print('ffmpeg args:', stream.get_args())
    try:
        stream.run(capture_stdout=True, capture_stderr=True, overwrite_output=True)
    except ffmpeg.Error as e:
        print(e.stderr.decode())
        raise
    return output_file_path


def monitor_dir_and_encode_to_mp4(dir_path: Path = WHISPER_ASSETS_DIR, sleep_seconds: int = 60) -> None:
    """
    Monitors a directory for new MKV files and encodes them to MP4.

    Args:
        dir_path (Path, optional): The directory to monitor for new MKV files. Defaults to `WHISPER_ASSETS_DIR`.
        sleep_seconds (int, optional): The number of seconds to sleep between checks. Defaults to 60.
    """
    while True:
        file_found = False
        for input_file_path in prepare_input_dir(dir_path).glob("*.mkv"):
            output_file_path = input_file_path.with_suffix('.mp4')
            if not output_file_path.exists():
                encode_to_mp4(input_file_path, output_file_path, OverwriteMode.NEVER)
            file_found = True
        if not file_found:
            print(f"No new file detected. Sleeping for {sleep_seconds} seconds...")
        time.sleep(sleep_seconds)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("dir", type=Path, default=WHISPER_ASSETS_DIR, help="The directory to monitor for new MKV files, defaults to `WHISPER_ASSETS_DIR`.")
    monitor_dir_and_encode_to_mp4(parser.parse_args().dir)


if __name__ == "__main__":
    main()
