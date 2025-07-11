import argparse
from pathlib import Path

import ffmpeg
from pathlib_extensions import OverwriteMode, overwrite_existing_path, prepare_input_file, prepare_output_file


def encode_media(input_file_path: Path, output_file_path: Path, ffmpeg_output_params: dict, overwrite: OverwriteMode) -> Path:
    """
    Encodes media from the input file path to the output file path using ffmpeg with the specified parameters.

    Args:
        input_file_path (Path): The path to the input media file.
        output_file_path (Path): The path where the encoded media file will be saved.
        ffmpeg_output_params (dict): A dictionary of parameters to pass to ffmpeg for encoding.
        overwrite (OverwriteMode): The mode that determines whether to overwrite the existing output file.

    Returns:
        Path: The path to the encoded media file.
    """
    prepare_input_file(input_file_path)
    if output_file_path.is_file() and not overwrite_existing_path(output_file_path, overwrite):
        return output_file_path
    prepare_output_file(output_file_path)
    stream = ffmpeg.input(str(input_file_path), threads=0).output(str(output_file_path), **ffmpeg_output_params)
    print('ffmpeg args:', stream.get_args())
    try:
        stream.run(capture_stdout=True, capture_stderr=True, overwrite_output=True)
    except ffmpeg.Error as e:
        print(e.stderr.decode())
        raise
    return output_file_path


def encode_to_mp3(input_file_path: Path, output_file_path: Path | None = None, overwrite: OverwriteMode = OverwriteMode.PROMPT) -> Path:
    """
    Encodes an input media file to MP3 format using FFmpeg.

    Args:
        input_file_path (Path): The path to the input media file.
        output_file_path (Path | None, optional): The path to save the encoded MP3 file.
            If None, the output file will have the same name as the input file with a .mp3 extension. Defaults to None.
        overwrite (OverwriteMode, optional): The mode to handle overwriting of existing files.
            Defaults to OverwriteMode.PROMPT.

    Returns:
        Path: The path to the encoded MP3 file.
    """
    output_file_path = output_file_path or input_file_path.with_suffix('.mp3')
    ffmpeg_output_params = {
        'vn': None,
        'acodec': 'libmp3lame',
        'qscale:a': '2',
    }
    return encode_media(input_file_path, output_file_path, ffmpeg_output_params, overwrite)


def encode_to_mp4(input_file_path: Path, output_file_path: Path | None = None, overwrite: OverwriteMode = OverwriteMode.PROMPT) -> Path:
    """
    Encodes a given media file to MP4 format using FFmpeg.

    Args:
        input_file_path (Path): The path to the input media file.
        output_file_path (Path | None, optional): The path to the output MP4 file. If None, the output file will have the same name as the input file with an .mp4 extension. Defaults to None.
        overwrite (OverwriteMode, optional): The mode to handle overwriting of existing files. Defaults to OverwriteMode.PROMPT.

    Returns:
        Path: The path to the encoded MP4 file.
    """
    output_file_path = output_file_path or input_file_path.with_suffix('.mp4')
    # TODO: use NVENC when possible
    ffmpeg_output_params = {
        'vcodec': 'libx264',
        'acodec': 'aac',
        'b:a': '160k',
        'ac': 2,
        'f': 'mp4',
    }
    return encode_media(input_file_path, output_file_path, ffmpeg_output_params, overwrite)


def main() -> None:
    parser = argparse.ArgumentParser(description='Encode video files to MP3 or MP4 format.')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    def add_encode_subparser(command_name, help_message, encode_func):
        parser_cmd = subparsers.add_parser(command_name, help=help_message)
        parser_cmd.add_argument('paths', type=Path, nargs='+', metavar='path', help=f'Video file paths to encode to {command_name.upper()}.')
        parser_cmd.add_argument('-o', '--overwrite', type=OverwriteMode, choices=OverwriteMode.values(), default=OverwriteMode.PROMPT, help='Whether to overwrite existing files. Defaults to `prompt`.')
        parser_cmd.set_defaults(encode_func=encode_func)

    add_encode_subparser('mp3', 'Encode media files to MP3.', encode_to_mp3)
    add_encode_subparser('mp4', 'Encode video files to MP4.', encode_to_mp4)
    args = parser.parse_args()
    if hasattr(args, 'encode_func'):
        overwrite = args.overwrite
        for path in args.paths:
            args.encode_func(path, overwrite=overwrite)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
