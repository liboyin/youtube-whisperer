import argparse
from pathlib import Path

import ffmpeg
from pathlib_extensions import OverwriteMode, overwrite_existing_path, prepare_input_file, prepare_output_file


def encode_to_mp3(input_file_path: Path, output_file_path: Path | None = None, overwrite: OverwriteMode = OverwriteMode.PROMPT) -> Path:
    """
    Encodes a video file to MP3 format.

    Args:
        input_file_path (Path): The path to the input video file.
        output_file_path (Path, optional): The path to the output MP3 file. If not provided, a path with the same name as the input file and .mp3 extension will be used.
        overwrite (OverwriteMode, optional): Whether to overwrite `output_file_path` if it already exists. Defaults to `OverwriteMode.PROMPT`.

    Returns:
        Path: The path to the encoded MP3 file.
    """
    prepare_input_file(input_file_path)
    output_file_path = output_file_path or input_file_path.with_suffix('.mp3')
    if output_file_path.is_file() and not overwrite_existing_path(output_file_path, overwrite):
        return output_file_path
    prepare_output_file(output_file_path)
    assert isinstance(output_file_path, Path)  # narrow down type from `Path | None` to `Path`
    stream = (
        ffmpeg
        .input(str(input_file_path), threads=0)
        .output(str(output_file_path), vn=None, acodec='libmp3lame', qscale='2')
    )
    print('ffmpeg args:', stream.get_args())
    try:
        stream.run(capture_stdout=True, capture_stderr=True, overwrite_output=True)
    except ffmpeg.Error as e:
        print(e.stderr.decode())
        raise
    return output_file_path


def main() -> None:
    """
    CLI entry point to encode video files to MP3 format.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", type=Path, nargs='+', metavar='path', help="Video file paths to encode to MP3.")
    parser.add_argument("-o", "--overwrite", choices=OverwriteMode.values(), default=OverwriteMode.PROMPT.value, help="Whether to overwrite existing MP3 files. Defaults to `OverwriteMode.PROMPT`.")
    args = parser.parse_args()
    overwrite = OverwriteMode(args.overwrite)
    for path in args.paths:
        encode_to_mp3(path, overwrite=overwrite)


if __name__ == "__main__":
    main()
