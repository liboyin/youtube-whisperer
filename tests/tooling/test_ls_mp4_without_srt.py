"""Exercise the MP4-without-SRT listing script in owned temporary directories."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

# Shell scripts are not importable, so the script under test is named by path instead of `testee`.
SCRIPT = Path(__file__).resolve().parents[2] / 'ls_mp4_without_srt.sh'
BASH = shutil.which('bash')


@pytest.fixture
def run_script(tmp_path):
    """Run the script in a fresh bash process with a minimal environment owned by the test."""
    assert BASH is not None, 'bash is required to exercise the shell script'
    home = tmp_path / 'home'
    temp = tmp_path / 'temp'
    home.mkdir()
    temp.mkdir()
    env = {'PATH': os.defpath, 'HOME': str(home), 'TMPDIR': str(temp), 'LC_ALL': 'C.UTF-8'}

    def run(*args):
        """Return the completed process for one script invocation rooted in the test directory."""
        return subprocess.run([BASH, str(SCRIPT), *args], cwd=tmp_path, env=env, check=False, capture_output=True, text=True, timeout=10)

    return run


def test_missing_argument_prints_usage_and_exits_one(run_script):
    """Invoking without a directory reports usage on stdout and fails."""
    result = run_script()
    assert (result.returncode, result.stdout, result.stderr) == (1, f'Usage: {SCRIPT} <directory_path>\n', '')


def test_missing_directory_reports_error_and_exits_one(run_script, tmp_path):
    """A nonexistent directory is named in the error and the script fails."""
    missing = tmp_path / 'no such dir'
    result = run_script(str(missing))
    assert (result.returncode, result.stdout, result.stderr) == (1, f"Error: Directory '{missing}' not found.\n", '')


def test_empty_directory_prints_nothing_and_succeeds(run_script, tmp_path):
    """An unmatched glob must not be printed as a literal `*.mp4` path."""
    media = tmp_path / 'media'
    media.mkdir()
    result = run_script(str(media))
    assert (result.returncode, result.stdout, result.stderr) == (0, '', '')


def test_directory_without_mp4_files_prints_nothing_and_succeeds(run_script, tmp_path):
    """Other files, including orphan subtitles, are never listed."""
    media = tmp_path / 'media'
    media.mkdir()
    for name in ('orphan.srt', 'notes.txt', 'clip.mp4.part'):
        (media / name).write_text('owned')
    result = run_script(str(media))
    assert (result.returncode, result.stdout, result.stderr) == (0, '', '')


def test_lists_only_mp4_files_missing_sibling_srt_in_glob_order(run_script, tmp_path):
    """Spaced names resolve their own SRT sibling and missing ones print as `<directory>/<name>.mp4`."""
    media = tmp_path / 'media library'
    media.mkdir()
    for name in ('b no sub.mp4', 'a with sub.mp4', 'a with sub.srt', 'c.mp4', 'd done.mp4', 'd done.srt', 'e other.srt'):
        (media / name).write_text('owned')
    result = run_script(str(media))
    assert (result.returncode, result.stdout, result.stderr) == (0, f'{media}/b no sub.mp4\n{media}/c.mp4\n', '')
