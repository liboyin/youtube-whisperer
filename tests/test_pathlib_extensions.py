from pathlib import Path

import pytest

from youtube_whisperer.pathlib_extensions import (
    NotAFileError,
    SuffixError,
    prepare_input_dir,
    prepare_input_file,
    prepare_output_dir,
    prepare_output_file,
)


def test_prepare_input_dir_valid():
    assert prepare_input_dir(Path.cwd()) == Path.cwd()


def test_prepare_input_dir_invalid():
    with pytest.raises(NotADirectoryError):
        prepare_input_dir(__file__)


def test_prepare_input_dir_not_found():
    with pytest.raises(FileNotFoundError):
        prepare_input_dir('path/that/does/not/exist')


def test_prepare_input_file_valid():
    assert prepare_input_file(__file__) == Path(__file__)


def test_prepare_input_file_invalid():
    with pytest.raises(NotAFileError):
        prepare_input_file(Path.cwd())


def test_prepare_input_file_not_found():
    with pytest.raises(FileNotFoundError):
        prepare_input_file('file/that/does/not/exist')


def test_prepare_input_file_check_suffix():
    with pytest.raises(SuffixError):
        prepare_input_file(__file__, check_suffix='.txt')


def test_prepare_input_file_with_suffix():
    assert prepare_input_file(__file__, with_suffix='.py') == Path(__file__)


def test_prepare_input_file_invalid_argument():
    with pytest.raises(ValueError):
        prepare_input_file(__file__, check_suffix='.txt', with_suffix='.txt')


def test_prepare_output_dir_valid(tmp_path):
    d = tmp_path / "sub"
    d.mkdir()
    assert prepare_output_dir(d) == d


def test_prepare_output_dir_invalid():
    with pytest.raises(NotADirectoryError):
        prepare_output_dir(__file__)


def test_prepare_output_dir_create(tmp_path):
    d = tmp_path / "sub2"
    assert prepare_output_dir(d, create=True) == d


def test_prepare_output_file_valid(tmp_path):
    p = tmp_path / "testfile.txt"
    p.write_text("content")
    assert prepare_output_file(p) == p


def test_prepare_output_file_invalid(tmp_path):
    d = tmp_path / "sub"
    d.mkdir()
    with pytest.raises(NotAFileError):
        prepare_output_file(d)


def test_prepare_output_file_check_suffix(tmp_path):
    p = tmp_path / "testfile.txt"
    p.write_text("content")
    with pytest.raises(SuffixError):
        prepare_output_file(p, check_suffix='.py')


def test_prepare_output_file_with_suffix(tmp_path):
    p = tmp_path / "testfile"
    p.write_text("content")
    assert prepare_output_file(p, with_suffix='.txt') == tmp_path / "testfile.txt"


def test_prepare_output_file_invalid_argument(tmp_path):
    p = tmp_path / "testfile"
    p.write_text("content")
    with pytest.raises(ValueError):
        prepare_output_file(p, check_suffix='.txt', with_suffix='.txt')
