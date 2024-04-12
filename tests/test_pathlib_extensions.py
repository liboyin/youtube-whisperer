import pytest

from youtube_whisperer.pathlib_extensions import prepare_output_file, NotAFileError, SuffixError


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
