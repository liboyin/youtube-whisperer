"""Run the SRT text extraction script in owned bash subprocesses on synthetic subtitles."""

import os
import subprocess
from pathlib import Path

import pytest

# Shell scripts are not importable; tests run this path in a fresh bash process.
SCRIPT = Path(__file__).resolve().parents[2] / 'extract_subtitle_text.sh'

# Cue indexes, both millisecond separators, cue settings, a timing line without an index,
# repeated blanks, and dialogue that resembles structure.
SAMPLE_LINES = [
    '1',
    '00:00:01,000 --> 00:00:02,500',
    '2026',
    'was a good year',
    '',
    '',
    '2',
    '00:00:03.000 --> 00:00:04.000 align:start position:10%',
    '42',
    '',
    '3',
    '100:00:05,000\t-->  100:00:06,000',
    'A --> B',
    '1 --> 2',
    '7',
    '8',
    '',
    '00:00:07,000 --> 00:00:08,000',
    'Unnumbered cue',
    '',
    '',
    '',
]
SAMPLE_TEXT = b'2026\nwas a good year\n42\nA --> B\n1 --> 2\n7\n8\nUnnumbered cue\n'


def run(tmp_path, *args):
    """Run the script with a minimal owned environment, working directory and empty stdin."""
    home = tmp_path / 'home'
    home.mkdir(exist_ok=True)
    env = {'PATH': os.defpath, 'HOME': str(home), 'TMPDIR': str(home), 'LC_ALL': 'C.UTF-8'}
    return subprocess.run(['bash', str(SCRIPT), *args], cwd=tmp_path, env=env, stdin=subprocess.DEVNULL,
                          check=False, capture_output=True, timeout=30)


def extract(tmp_path, content, name='input.srt'):
    """Write subtitle bytes to an owned file and return the completed extraction."""
    path = tmp_path / name
    path.write_bytes(content)
    return run(tmp_path, str(path))


def assert_output(result, expected):
    """Require a successful run that printed exactly the expected bytes and no diagnostics."""
    assert (result.returncode, result.stdout, result.stderr) == (0, expected, b'')


def test_cue_text_is_kept_and_srt_structure_is_dropped(tmp_path):
    """Numeric and arrow-bearing dialogue survive while indexes, timings and blanks are removed."""
    result = extract(tmp_path, ''.join(f'{line}\n' for line in SAMPLE_LINES).encode())
    assert_output(result, SAMPLE_TEXT)


def test_crlf_input_matches_lf_output(tmp_path):
    """A CRLF subtitle produces the same bytes as its LF equivalent and no carriage returns."""
    lf = extract(tmp_path, ''.join(f'{line}\n' for line in SAMPLE_LINES).encode(), 'lf.srt')
    crlf = extract(tmp_path, ''.join(f'{line}\r\n' for line in SAMPLE_LINES).encode(), 'crlf.srt')
    assert_output(crlf, lf.stdout)
    assert crlf.stdout == SAMPLE_TEXT
    assert b'\r' not in crlf.stdout


@pytest.mark.parametrize('ending', ['\n', '\r\n'])
@pytest.mark.parametrize('last', ['Final words', '2026'])
def test_last_line_without_final_newline_is_kept(tmp_path, ending, last):
    """An unterminated final line, including a held digits-only line, is printed with LF."""
    content = ending.join(['1', '00:00:01,000 --> 00:00:02,000', 'First', '', '2', '00:00:03,000 --> 00:00:04,000', last])
    assert_output(extract(tmp_path, content.encode()), f'First\n{last}\n'.encode())


@pytest.mark.parametrize('ending', ['\n', '\r\n'])
def test_bom_prefixed_first_index_is_removed(tmp_path, ending):
    """A UTF-8 BOM before the first cue index does not turn the index into dialogue."""
    content = ending.join(['1', '00:00:01,000 --> 00:00:02,000', 'Hello', '']).encode()
    assert_output(extract(tmp_path, b'\xef\xbb\xbf' + content), b'Hello\n')


def test_file_name_with_equals_sign_is_read_as_subtitle(tmp_path):
    """A name awk could parse as an assignment is still read as the subtitle file."""
    (tmp_path / 'cue=1.srt').write_bytes(b'1\n00:00:01,000 --> 00:00:02,000\nHello\n')
    # Only a relative name begins with an identifier, which is awk's assignment syntax.
    assert_output(run(tmp_path, 'cue=1.srt'), b'Hello\n')


@pytest.mark.parametrize('args', [(), ('one.srt', 'two.srt')])
def test_wrong_argument_count_prints_usage_and_exits_1(tmp_path, args):
    """The CLI rejects anything other than one subtitle argument with its usage message."""
    result = run(tmp_path, *args)
    assert (result.returncode, result.stdout, result.stderr) == (1, f'Usage: {SCRIPT} <srt_file>\n'.encode(), b'')


def test_missing_file_exits_non_zero_without_output(tmp_path):
    """An unreadable subtitle path fails with a diagnostic and prints no text."""
    result = run(tmp_path, str(tmp_path / 'missing.srt'))
    assert result.returncode != 0
    assert result.stdout == b''
    assert b'missing.srt' in result.stderr
