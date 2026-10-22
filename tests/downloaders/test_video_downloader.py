import stat
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest
from pathlib_extensions import OverwritePolicy

import youtube_whisperer.downloaders.video_downloader as testee


@pytest.fixture
def staged_youtube_dl_factory(mocker, tmp_path):
    """Evaluate real templates while replacing network I/O with owned writes."""
    real_youtube_dl = testee.yt_dlp.YoutubeDL
    state = SimpleNamespace(instances=[], error=None, output='file', during_download=None, exit_error=None)

    class OwnedYoutubeDL(real_youtube_dl):
        """Use the installed template evaluator without extraction or network I/O."""

        def __init__(self, options):
            """Retain invocation options and create an inert real template evaluator."""
            self.options = options
            # yt-dlp normalizes its parameters; retain the caller's dictionary
            # identity so option-freshness assertions observe production behavior.
            super().__init__(deepcopy(options), auto_init=False)
            self.download_calls = []
            self.exit_calls = []
            self.staged_path = None
            state.instances.append(self)

        def __exit__(self, exc_type, exc, tb):
            """Record the original exception, close the session and inject an exit failure."""
            self.exit_calls.append((exc_type, exc, tb))
            result = super().__exit__(exc_type, exc, tb)
            if state.exit_error is not None and exc_type is None:
                raise state.exit_error
            return result

        def download(self, urls):
            """Write synthetic bytes only where real template evaluation directs."""
            self.download_calls.append(urls)
            self.staged_path = Path(self.prepare_filename({'id': 'AAAAAAAAAAA', 'title': 'synthetic', 'ext': 'mp4'}))
            assert self.staged_path.is_relative_to(tmp_path)
            self.staged_path.parent.mkdir(parents=True, exist_ok=True)
            if state.output == 'file':
                self.staged_path.write_bytes(b'new video')
                # Distinguish mode restoration even under an unusually restrictive umask.
                self.staged_path.chmod(0o600)
            elif state.output == 'directory':
                self.staged_path.mkdir()
            if state.during_download is not None:
                state.during_download()
            if state.error is not None:
                raise state.error
            return 0

    def install(module, *, cookies_available, error=None):
        """Patch the constructor and cookie discovery with test-owned dependencies."""
        state.error = error
        mocker.patch.object(module, 'is_firefox_cookies_available', return_value=cookies_available)
        mocker.patch.object(module.yt_dlp, 'YoutubeDL', side_effect=OwnedYoutubeDL)
        return state

    return install


@pytest.mark.parametrize('cookies_available', [False, True])
def test_operation_retains_exact_options_and_discovers_cookies_at_invocation(cookies_available, staged_youtube_dl_factory, mocker, monkeypatch, tmp_path):
    """Each operation retains exact defaults and uses lazy cached owned discovery."""
    monkeypatch.setenv('HOME', str(tmp_path))
    detector = testee.is_firefox_cookies_available
    detector.cache_clear()
    created = staged_youtube_dl_factory(testee, cookies_available=cookies_available)
    discovery = mocker.patch.object(testee, 'is_firefox_cookies_available', wraps=detector)
    cookies = tmp_path / '.mozilla' / 'firefox' / 'owned' / 'cookies.sqlite'
    if cookies_available:
        cookies.parent.mkdir(parents=True)
        cookies.write_text('owned')
    try:
        assert detector.cache_info().misses == 0
        discovery.assert_not_called()
        testee.download_video('url', tmp_path / 'video.mp4', OverwritePolicy.ALWAYS)
        expected = {'verbose': True, 'js_runtimes': {'deno': {}}, 'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]'}
        if cookies_available:
            expected['cookiesfrombrowser'] = ('firefox',)
        assert {key: value for key, value in created.instances[0].options.items() if key != 'outtmpl'} == expected
        assert created.instances[0].options['outtmpl'] == str(created.instances[0].staged_path)
        if cookies_available:
            cookies.unlink()
        else:
            cookies.parent.mkdir(parents=True)
            cookies.write_text('owned')
        testee.download_video('url', tmp_path / 'video.mp4', OverwritePolicy.ALWAYS)
        assert {key: value for key, value in created.instances[1].options.items() if key != 'outtmpl'} == expected
        assert created.instances[1].options['outtmpl'] == str(created.instances[1].staged_path)
        assert created.instances[0].staged_path != created.instances[1].staged_path
        assert list(tmp_path.glob('.staging-*')) == []
        assert (tmp_path / 'video.mp4').read_bytes() == b'new video'
        assert discovery.call_count == 2
        assert detector.cache_info().misses == 1
        assert detector.cache_info().hits == 1
        assert created.instances[0].options is not created.instances[1].options
        assert created.instances[0].options['js_runtimes'] is not created.instances[1].options['js_runtimes']
        assert [instance.download_calls for instance in created.instances] == [[['url']], [['url']]]
    finally:
        detector.cache_clear()


def test_download_video_returns_early_when_existing_file_should_not_be_overwritten(mocker, tmp_path):
    """Test that an existing file is not re-downloaded when overwrite is denied."""
    target_path = tmp_path / "video.mp4"
    target_path.write_text("existing")
    mock_overwrite = mocker.patch.object(testee, "resolve_output_path", wraps=testee.resolve_output_path)
    mock_prepare = mocker.patch.object(testee, "prepare_output_file")
    mock_ydl = mocker.patch.object(testee.yt_dlp, "YoutubeDL")

    testee.download_video("https://example.com/watch?v=1", target_path, OverwritePolicy.NEVER)

    mock_overwrite.assert_called_once_with(target_path, OverwritePolicy.NEVER)
    mock_prepare.assert_not_called()
    mock_ydl.assert_not_called()


def test_download_video_rejects_rename_before_any_download_work(mocker, tmp_path):
    """RENAME fails before preparing the destination or constructing the downloader."""
    downloader = mocker.patch.object(testee.yt_dlp, "YoutubeDL")
    with pytest.raises(ValueError, match="RENAME is not supported"):
        testee.download_video("https://example.com/watch?v=1", tmp_path / "out" / "video.mp4", OverwritePolicy.RENAME)
    downloader.assert_not_called()
    assert list(tmp_path.iterdir()) == []


def test_download_video_downloads_with_cookies_when_available(mocker, tmp_path, staged_youtube_dl_factory):
    """Test that available Firefox cookies are passed to yt-dlp for the download."""
    target_path = tmp_path / "video.mp4"
    created = staged_youtube_dl_factory(testee, cookies_available=True)

    testee.download_video("https://example.com/watch?v=2", target_path, OverwritePolicy.ALWAYS)

    assert created.instances[0].options["outtmpl"] == str(created.instances[0].staged_path)
    assert created.instances[0].staged_path.parent.parent == target_path.parent
    assert created.instances[0].staged_path.name == "video.mp4"
    assert target_path.read_bytes() == b"new video"
    assert list(tmp_path.glob(".staging-*")) == []
    assert created.instances[0].options["cookiesfrombrowser"] == ("firefox",)
    assert created.instances[0].download_calls == [["https://example.com/watch?v=2"]]


def test_download_video_omits_cookies_when_unavailable(mocker, tmp_path, staged_youtube_dl_factory):
    """Test that the download omits Firefox cookies when no browser profile is available."""
    target_path = tmp_path / "video.mp4"
    created = staged_youtube_dl_factory(testee, cookies_available=False)

    testee.download_video("https://example.com/watch?v=4", target_path, OverwritePolicy.ALWAYS)

    # Asking yt-dlp for browser cookies that do not exist makes it fail instead of downloading anonymously.
    assert "cookiesfrombrowser" not in created.instances[0].options
    assert created.instances[0].download_calls == [["https://example.com/watch?v=4"]]


def test_download_video_propagates_error_and_exits_context(tmp_path, staged_youtube_dl_factory):
    """Download failure exits its session and preserves the exception identity."""
    target = tmp_path / 'video.mp4'
    target.write_bytes(b'previous video')
    error = RuntimeError('download failed')
    created = staged_youtube_dl_factory(testee, cookies_available=False, error=error)
    with pytest.raises(RuntimeError) as caught:
        testee.download_video('url', target, OverwritePolicy.ALWAYS)
    assert target.read_bytes() == b'previous video'
    assert list(tmp_path.glob('.staging-*')) == []
    assert caught.value is error
    instance = created.instances[0]
    assert instance.download_calls == [['url']]
    assert len(instance.exit_calls) == 1
    assert instance.exit_calls[0][:2] == (RuntimeError, error)
    assert instance.exit_calls[0][2] is not None


@pytest.mark.parametrize('name', ['ordinary', '100%', '%%', 'Progress %(id)s', 'Price $NB8_UNSET'])
@pytest.mark.parametrize('directory', ['ordinary', 'dir%', 'dir%%', 'dir%(id)s', 'dir$NB8_UNSET'])
def test_download_video_publishes_literal_names_after_real_template_evaluation(name, directory, monkeypatch, tmp_path, staged_youtube_dl_factory):
    """Titles and directory metacharacters survive installed yt-dlp evaluation."""
    monkeypatch.delenv('NB8_UNSET', raising=False)
    target = tmp_path / directory / f'{name}.mp4'
    created = staged_youtube_dl_factory(testee, cookies_available=False)

    testee.download_video('url', target, OverwritePolicy.ALWAYS)

    instance = created.instances[0]
    assert instance.staged_path.parent.parent == target.parent
    assert instance.staged_path.name == 'video.mp4'
    assert instance.options['outtmpl'] == str(instance.staged_path).replace('%', '%%')
    assert target.read_bytes() == b'new video'
    assert list(target.parent.iterdir()) == [target]


def test_download_video_rejects_expanding_parent_before_staging(monkeypatch, mocker, tmp_path, staged_youtube_dl_factory):
    """A set variable in the parent fails before staging or downloader construction."""
    monkeypatch.setenv('NB8_SET', 'owned-expanded')
    parent = tmp_path / '$NB8_SET'
    parent.mkdir()
    created = staged_youtube_dl_factory(testee, cookies_available=False)
    make_stage = mocker.spy(testee, 'StagedFile')

    with pytest.raises(ValueError, match='expand'):
        testee.download_video('url', parent / 'video.mp4', OverwritePolicy.ALWAYS)

    make_stage.assert_not_called()
    assert created.instances == []
    assert list(parent.iterdir()) == []
    assert list(tmp_path.iterdir()) == [parent]


def test_download_video_keeps_set_variable_in_title_literal(monkeypatch, tmp_path, staged_youtube_dl_factory):
    """A set variable in a title is safe because titles never enter the template."""
    monkeypatch.setenv('NB8_SET', 'owned-expanded')
    target = tmp_path / 'Price $NB8_SET.mp4'
    staged_youtube_dl_factory(testee, cookies_available=False)

    testee.download_video('url', target, OverwritePolicy.ALWAYS)

    assert target.read_bytes() == b'new video'
    assert list(tmp_path.iterdir()) == [target]


def test_download_video_replaces_authorized_existing_file_and_preserves_mode(mocker, tmp_path, staged_youtube_dl_factory):
    """ALWAYS replacement publishes new bytes with the previous permission bits."""
    target = tmp_path / 'video.mp4'
    target.write_bytes(b'previous video')
    target.chmod(0o640)
    created = staged_youtube_dl_factory(testee, cookies_available=False)
    consent = mocker.patch.object(testee, 'resolve_output_path', wraps=testee.resolve_output_path)

    def observe_previous_output():
        """Check that the old video survives until download completion."""
        assert target.read_bytes() == b'previous video'

    created.during_download = observe_previous_output
    testee.download_video('url', target, OverwritePolicy.ALWAYS)

    consent.assert_called_once_with(target, OverwritePolicy.ALWAYS)
    assert target.read_bytes() == b'new video'
    assert stat.S_IMODE(target.stat().st_mode) == 0o640
    assert list(tmp_path.iterdir()) == [target]


@pytest.mark.parametrize('policy', [OverwritePolicy.NEVER])
def test_download_video_preserves_existing_file_without_constructing_downloader(policy, tmp_path, staged_youtube_dl_factory):
    """Existing files satisfy NEVER without staging or downloader work."""
    target = tmp_path / 'video.mp4'
    target.write_bytes(b'previous video')
    created = staged_youtube_dl_factory(testee, cookies_available=False)

    testee.download_video('url', target, policy)

    assert created.instances == []
    assert target.read_bytes() == b'previous video'
    assert list(tmp_path.iterdir()) == [target]


@pytest.mark.parametrize('policy', [OverwritePolicy.NEVER])
def test_download_video_publishes_absent_output_under_preserving_policies(policy, tmp_path, staged_youtube_dl_factory):
    """Create-if-absent publishes a completed new video and removes its stage."""
    target = tmp_path / 'video.mp4'
    staged_youtube_dl_factory(testee, cookies_available=False)

    testee.download_video('url', target, policy)

    assert target.read_bytes() == b'new video'
    assert list(tmp_path.iterdir()) == [target]


@pytest.mark.parametrize('policy', [OverwritePolicy.NEVER])
@pytest.mark.parametrize('collision', ['file', 'directory', 'dangling-symlink', 'file-symlink'])
def test_download_video_preserves_competing_file_and_propagates_other_collisions(policy, collision, tmp_path, staged_youtube_dl_factory):
    """Create-if-absent keeps competing files and reports non-file collisions."""
    target = tmp_path / 'video.mp4'
    other = tmp_path / 'other.mp4'
    created = staged_youtube_dl_factory(testee, cookies_available=False)

    def create_competitor():
        """Introduce the collision after preflight and before publication."""
        if collision == 'file':
            target.write_bytes(b'competing video')
        elif collision == 'directory':
            target.mkdir()
        elif collision == 'dangling-symlink':
            target.symlink_to(other)
        else:
            other.write_bytes(b'competing video')
            target.symlink_to(other)

    created.during_download = create_competitor
    if collision in ('file', 'file-symlink'):
        testee.download_video('url', target, policy)
        assert target.read_bytes() == b'competing video'
    else:
        with pytest.raises(FileExistsError):
            testee.download_video('url', target, policy)
        if collision == 'directory':
            assert target.is_dir()
        else:
            assert target.is_symlink()
            assert not other.exists()
    assert list(tmp_path.glob('.staging-*')) == []


@pytest.mark.parametrize('output', ['missing', 'directory'])
def test_download_video_requires_regular_staged_output(output, tmp_path, staged_youtube_dl_factory):
    """A return without regular staged output cannot publish or damage old bytes."""
    target = tmp_path / 'video.mp4'
    target.write_bytes(b'previous video')
    created = staged_youtube_dl_factory(testee, cookies_available=False)
    created.output = output

    with pytest.raises(FileNotFoundError, match='regular staged video'):
        testee.download_video('url', target, OverwritePolicy.ALWAYS)

    assert target.read_bytes() == b'previous video'
    assert list(tmp_path.iterdir()) == [target]


def test_download_video_missing_staged_output_does_not_create_destination(tmp_path, staged_youtube_dl_factory):
    """An absent staged output leaves an absent destination absent."""
    target = tmp_path / 'video.mp4'
    created = staged_youtube_dl_factory(testee, cookies_available=False)
    created.output = 'missing'

    with pytest.raises(FileNotFoundError):
        testee.download_video('url', target, OverwritePolicy.ALWAYS)

    assert list(tmp_path.iterdir()) == []


def test_download_video_cleans_stage_on_interruption(tmp_path, staged_youtube_dl_factory):
    """Interruption unwinding removes partial stages and preserves previous bytes."""
    target = tmp_path / 'video.mp4'
    target.write_bytes(b'previous video')
    interruption = KeyboardInterrupt()
    created = staged_youtube_dl_factory(testee, cookies_available=False, error=interruption)

    with pytest.raises(KeyboardInterrupt) as caught:
        testee.download_video('url', target, OverwritePolicy.ALWAYS)

    assert caught.value is interruption
    assert created.instances[0].exit_calls[0][:2] == (KeyboardInterrupt, interruption)
    assert target.read_bytes() == b'previous video'
    assert list(tmp_path.iterdir()) == [target]


@pytest.mark.parametrize(('policy', 'existing'), [(OverwritePolicy.ALWAYS, True), (OverwritePolicy.NEVER, False)])
def test_download_video_publishes_only_after_downloader_context_exit(policy, existing, tmp_path, staged_youtube_dl_factory):
    """A failing downloader exit after a complete download publishes nothing and removes the stage."""
    target = tmp_path / 'video.mp4'
    if existing:
        target.write_bytes(b'previous video')
    created = staged_youtube_dl_factory(testee, cookies_available=False)
    error = RuntimeError('downloader exit failed')
    created.exit_error = error

    with pytest.raises(RuntimeError) as caught:
        testee.download_video('url', target, policy)

    assert caught.value is error
    assert created.instances[0].download_calls == [['url']]
    if existing:
        assert target.read_bytes() == b'previous video'
        assert list(tmp_path.iterdir()) == [target]
    else:
        assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('policy', [OverwritePolicy.NEVER, OverwritePolicy.ALWAYS])
def test_download_video_cleans_stage_after_publication_error(policy, mocker, tmp_path, staged_youtube_dl_factory):
    """Unsupported publication errors propagate while removing only the owned stage."""
    target = tmp_path / 'video.mp4'
    unrelated = tmp_path / '.staging-unrelated'
    unrelated.mkdir()
    (unrelated / 'keep').write_bytes(b'unrelated')
    staged_youtube_dl_factory(testee, cookies_available=False)
    error = OSError('publication failed')
    operation = 'link' if policy == OverwritePolicy.NEVER else 'replace'
    mocker.patch.object(testee.os, operation, side_effect=error)

    with pytest.raises(OSError) as caught:
        testee.download_video('url', target, policy)

    assert caught.value is error
    assert not target.exists()
    assert list(tmp_path.iterdir()) == [unrelated]
    assert (unrelated / 'keep').read_bytes() == b'unrelated'


def test_download_video_resolves_symlink_and_leaves_hardlinked_alias_unchanged(tmp_path, staged_youtube_dl_factory):
    """D22 follows the symlink target and replaces its inode without alias truncation."""
    real = tmp_path / 'nested' / 'real.mp4'
    real.parent.mkdir()
    real.write_bytes(b'previous video')
    real.chmod(0o640)
    link = tmp_path / 'video.mp4'
    link.symlink_to(real)
    alias = tmp_path / 'alias.mp4'
    alias.hardlink_to(real)
    created = staged_youtube_dl_factory(testee, cookies_available=False)

    testee.download_video('url', link, OverwritePolicy.ALWAYS)

    assert link.is_symlink()
    assert real.read_bytes() == link.read_bytes() == b'new video'
    assert alias.read_bytes() == b'previous video'
    assert stat.S_IMODE(real.stat().st_mode) == 0o640
    assert created.instances[0].staged_path.parent.parent == real.parent
    assert list(real.parent.iterdir()) == [real]


def test_download_video_with_default_title_names_file_after_title_and_id(mocker, tmp_path):
    """The default name is the sanitized title tagged with the video ID."""
    mocker.patch.object(testee, 'get_video_title_and_id', return_value=('bad:/title', 'n9xhJrPXop4'))
    mock_download = mocker.patch.object(testee, 'download_video')

    result = testee.download_video_with_default_title('https://example.com/watch?v=3', target_dir=tmp_path, overwrite=OverwritePolicy.NEVER)

    assert result == tmp_path / 'bad__title [n9xhJrPXop4].mp4'
    mock_download.assert_called_once_with('https://example.com/watch?v=3', result, overwrite=OverwritePolicy.NEVER)


def test_download_video_with_default_title_rejects_rename_before_metadata_or_settings(mocker):
    """RENAME fails before the asset directory is resolved or video metadata is requested."""
    metadata = mocker.patch.object(testee, 'get_video_title_and_id', side_effect=AssertionError('metadata requested'))
    settings = mocker.patch.object(testee, 'Settings', side_effect=AssertionError('settings resolved'))
    with pytest.raises(ValueError, match='RENAME is not supported'):
        testee.download_video_with_default_title('https://example.com/watch?v=3', overwrite=OverwritePolicy.RENAME)
    metadata.assert_not_called()
    settings.assert_not_called()


def test_download_video_with_default_title_reuses_existing_title_only_video(mocker, tmp_path):
    """A video downloaded before IDs were added to names is reused under its old name."""
    legacy = tmp_path / 'Title.mp4'
    legacy.write_bytes(b'legacy video')
    mocker.patch.object(testee, 'get_video_title_and_id', return_value=('Title', 'n9xhJrPXop4'))
    mock_download = mocker.patch.object(testee, 'download_video')

    result = testee.download_video_with_default_title('https://example.com/watch?v=5', target_dir=tmp_path, overwrite=OverwritePolicy.NEVER)

    assert result == legacy
    mock_download.assert_called_once_with('https://example.com/watch?v=5', legacy, overwrite=OverwritePolicy.NEVER)


def test_download_video_with_default_title_truncates_long_dotted_title_keeping_mp4_suffix(mocker, tmp_path):
    """A long title containing dots is truncated to 220 bytes and keeps its ID tag and .mp4 suffix."""
    title = 'Mr. Smith Goes to Washington ' + 'x' * 300
    mocker.patch.object(testee, 'get_video_title_and_id', return_value=(title, 'n9xhJrPXop4'))
    mock_download = mocker.patch.object(testee, 'download_video')

    result = testee.download_video_with_default_title('https://example.com/watch?v=4', target_dir=tmp_path, overwrite=OverwritePolicy.NEVER)

    assert result == tmp_path / (title[:220 - len(' [n9xhJrPXop4].mp4')] + ' [n9xhJrPXop4].mp4')
    mock_download.assert_called_once_with('https://example.com/watch?v=4', result, overwrite=OverwritePolicy.NEVER)


def test_download_video_with_default_title_keeps_videos_apart_when_title_ends_in_another_id(mocker, tmp_path):
    """Video B titled like video A's tagged name gets its own file, not A's media."""
    metadata = {'url-a': ('Title', 'aaaaaaaaaaa'), 'url-b': ('Title [aaaaaaaaaaa]', 'bbbbbbbbbbb')}
    mocker.patch.object(testee, 'get_video_title_and_id', side_effect=metadata.__getitem__)
    downloads = mocker.patch.object(testee, 'download_video', side_effect=lambda url, path, overwrite: path.write_text(url))

    first = testee.download_video_with_default_title('url-a', target_dir=tmp_path, overwrite=OverwritePolicy.NEVER)
    second = testee.download_video_with_default_title('url-b', target_dir=tmp_path, overwrite=OverwritePolicy.NEVER)

    assert first == tmp_path / 'Title [aaaaaaaaaaa].mp4'
    assert second == tmp_path / 'Title [aaaaaaaaaaa] [bbbbbbbbbbb].mp4'
    assert first.read_text() == 'url-a'
    assert second.read_text() == 'url-b'
    assert downloads.call_count == 2
