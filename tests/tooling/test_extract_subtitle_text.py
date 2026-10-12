"""Run the SRT text extraction script in owned bash subprocesses on synthetic subtitles."""

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


def run(runner, *args):
    """Run the script through the shared owned-subprocess runner, capturing bytes to observe CR and BOM."""
    return runner(SCRIPT, *args, text=False)


def extract(runner, content, name='input.srt'):
    """Write subtitle bytes to an owned file and return the completed extraction."""
    path = runner.cwd / name
    path.write_bytes(content)
    return run(runner, str(path))


def assert_output(result, expected):
    """Require a successful run that printed exactly the expected bytes and no diagnostics."""
    assert (result.returncode, result.stdout, result.stderr) == (0, expected, b'')


def test_cue_text_is_kept_and_srt_structure_is_dropped(run_shell_script):
    """Numeric and arrow-bearing dialogue survive while indexes, timings and blanks are removed."""
    result = extract(run_shell_script, ''.join(f'{line}\n' for line in SAMPLE_LINES).encode())
    assert_output(result, SAMPLE_TEXT)


def test_crlf_input_matches_lf_output(run_shell_script):
    """A CRLF subtitle produces the same bytes as its LF equivalent and no carriage returns."""
    lf = extract(run_shell_script, ''.join(f'{line}\n' for line in SAMPLE_LINES).encode(), 'lf.srt')
    crlf = extract(run_shell_script, ''.join(f'{line}\r\n' for line in SAMPLE_LINES).encode(), 'crlf.srt')
    assert_output(crlf, lf.stdout)
    assert crlf.stdout == SAMPLE_TEXT
    assert b'\r' not in crlf.stdout


@pytest.mark.parametrize('ending', ['\n', '\r\n'])
@pytest.mark.parametrize('last', ['Final words', '2026'])
def test_last_line_without_final_newline_is_kept(run_shell_script, ending, last):
    """An unterminated final line, including a held digits-only line, is printed with LF."""
    content = ending.join(['1', '00:00:01,000 --> 00:00:02,000', 'First', '', '2', '00:00:03,000 --> 00:00:04,000', last])
    assert_output(extract(run_shell_script, content.encode()), f'First\n{last}\n'.encode())


@pytest.mark.parametrize('ending', ['\n', '\r\n'])
def test_bom_prefixed_first_index_is_removed(run_shell_script, ending):
    """A UTF-8 BOM before the first cue index does not turn the index into dialogue."""
    content = ending.join(['1', '00:00:01,000 --> 00:00:02,000', 'Hello', '']).encode()
    assert_output(extract(run_shell_script, b'\xef\xbb\xbf' + content), b'Hello\n')


def test_file_name_with_equals_sign_is_read_as_subtitle(run_shell_script, tmp_path):
    """A name awk could parse as an assignment is still read as the subtitle file."""
    (tmp_path / 'cue=1.srt').write_bytes(b'1\n00:00:01,000 --> 00:00:02,000\nHello\n')
    # Only a relative name begins with an identifier, which is awk's assignment syntax.
    assert_output(run(run_shell_script, 'cue=1.srt'), b'Hello\n')


@pytest.mark.parametrize('args', [(), ('one.srt', 'two.srt')])
def test_wrong_argument_count_prints_usage_and_exits_1(run_shell_script, args):
    """The CLI rejects anything other than one subtitle argument with its usage message."""
    result = run(run_shell_script, *args)
    assert (result.returncode, result.stdout, result.stderr) == (1, f'Usage: {SCRIPT} <srt_file>\n'.encode(), b'')


def test_missing_file_exits_non_zero_without_output(run_shell_script, tmp_path):
    """An unreadable subtitle path fails with a diagnostic and prints no text."""
    result = run(run_shell_script, str(tmp_path / 'missing.srt'))
    assert result.returncode != 0
    assert result.stdout == b''
    assert b'missing.srt' in result.stderr
