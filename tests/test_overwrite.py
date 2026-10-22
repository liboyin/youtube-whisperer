import pytest
from pathlib_extensions import NotAFileError, OverwritePolicy

import youtube_whisperer.overwrite as testee


@pytest.mark.parametrize('policy', [OverwritePolicy.ALWAYS, OverwritePolicy.NEVER])
def test_require_supported_policy_returns_always_and_never_unchanged(policy):
    """ALWAYS and NEVER are the supported policies and pass through as the same object."""
    assert testee.require_supported_policy(policy) is policy


def test_require_supported_policy_rejects_rename():
    """RENAME would publish numbered copies that break MP4/SRT pairing, so it is refused."""
    with pytest.raises(ValueError, match='RENAME is not supported'):
        testee.require_supported_policy(OverwritePolicy.RENAME)


def test_resolve_output_path_keeps_existing_file_under_never(tmp_path):
    """NEVER keeps an existing file and reports that nothing may be written."""
    path = tmp_path / 'out.srt'
    path.write_text('existing')
    assert testee.resolve_output_path(path, OverwritePolicy.NEVER) is None


@pytest.mark.parametrize('policy', [OverwritePolicy.ALWAYS, OverwritePolicy.NEVER])
def test_resolve_output_path_allows_absent_file(tmp_path, policy):
    """A missing destination may be written under either supported policy."""
    path = tmp_path / 'out.srt'
    assert testee.resolve_output_path(path, policy) == path


def test_resolve_output_path_allows_replacing_existing_file_under_always(tmp_path):
    """ALWAYS approves writing over an existing file."""
    path = tmp_path / 'out.srt'
    path.write_text('existing')
    assert testee.resolve_output_path(path, OverwritePolicy.ALWAYS) == path


def test_resolve_output_path_rejects_rename_before_checking_the_filesystem(tmp_path):
    """RENAME is refused even where the library would choose a numbered free name."""
    path = tmp_path / 'out.srt'
    path.write_text('existing')
    with pytest.raises(ValueError, match='RENAME is not supported'):
        testee.resolve_output_path(path, OverwritePolicy.RENAME)
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize('policy', [OverwritePolicy.ALWAYS, OverwritePolicy.NEVER])
def test_resolve_output_path_rejects_directory_destination_before_work(tmp_path, policy):
    """A directory in the way fails immediately, before any expensive work."""
    with pytest.raises(NotAFileError):
        testee.resolve_output_path(tmp_path, policy)
