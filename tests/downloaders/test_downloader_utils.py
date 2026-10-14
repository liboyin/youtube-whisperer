import logging

import pytest

import youtube_whisperer.downloaders.utils as testee


@pytest.fixture(autouse=True)
def clear_firefox_cookies_cache():
    """Own cached cookie discovery for each test and clear it on teardown."""
    testee.is_firefox_cookies_available.cache_clear()
    yield
    testee.is_firefox_cookies_available.cache_clear()


@pytest.mark.parametrize('cookies_available', [False, True])
def test_build_youtube_dl_options_returns_independent_nested_defaults(cookies_available, mocker):
    """Baseline options are exact, independent at every mapping level, and pure."""
    detector = mocker.patch.object(testee, 'is_firefox_cookies_available', side_effect=AssertionError('unexpected discovery'))
    expected = {'verbose': True, 'js_runtimes': {'deno': {}}}
    if cookies_available:
        expected['cookiesfrombrowser'] = ('firefox',)
    first = testee.build_youtube_dl_options(cookies_available)
    second = testee.build_youtube_dl_options(cookies_available)
    assert first == second == expected
    assert first is not second
    assert first['js_runtimes'] is not second['js_runtimes']
    assert first['js_runtimes']['deno'] is not second['js_runtimes']['deno']
    first['verbose'] = False
    first['js_runtimes']['deno']['path'] = 'changed'
    first['js_runtimes']['node'] = {}
    assert second == testee.build_youtube_dl_options(cookies_available) == expected
    detector.assert_not_called()


@pytest.mark.parametrize('cookies_available', [False, True])
def test_operation_retains_exact_options_and_discovers_cookies_at_invocation(cookies_available, youtube_dl_factory, mocker, monkeypatch, tmp_path):
    """Each operation retains exact defaults and uses lazy cached owned discovery."""
    monkeypatch.setenv('HOME', str(tmp_path))
    detector = testee.is_firefox_cookies_available
    detector.cache_clear()
    created = youtube_dl_factory(testee, cookies_available=cookies_available, extract_info_result={'title': 'title'})
    discovery = mocker.patch.object(testee, 'is_firefox_cookies_available', wraps=detector)
    cookies = tmp_path / '.mozilla' / 'firefox' / 'owned' / 'cookies.sqlite'
    if cookies_available:
        cookies.parent.mkdir(parents=True)
        cookies.write_text('owned')
    try:
        assert detector.cache_info().misses == 0
        discovery.assert_not_called()
        testee.get_video_title('url')
        expected = {'verbose': True, 'js_runtimes': {'deno': {}}, 'simulate': True}
        if cookies_available:
            expected['cookiesfrombrowser'] = ('firefox',)
        assert created.instances[0].options == expected
        if cookies_available:
            cookies.unlink()
        else:
            cookies.parent.mkdir(parents=True)
            cookies.write_text('owned')
        testee.get_video_title('url')
        assert created.instances[1].options == expected
        assert discovery.call_count == 2
        assert detector.cache_info().misses == 1
        assert detector.cache_info().hits == 1
        assert created.instances[0].options is not created.instances[1].options
        assert created.instances[0].options['js_runtimes'] is not created.instances[1].options['js_runtimes']
        assert [instance.extract_info_calls for instance in created.instances] == [[('url', False)], [('url', False)]]
    finally:
        detector.cache_clear()


def test_get_video_title_uses_yt_dlp_and_optional_firefox_cookies(youtube_dl_factory):
    """Test that the title is extracted via yt-dlp using Firefox cookies when available."""
    created = youtube_dl_factory(testee, cookies_available=True, extract_info_result={"title": "Expected Title"})

    result = testee.get_video_title("https://example.com/watch?v=1")

    assert result == "Expected Title"
    assert created.instances[0].options["simulate"] is True
    assert created.instances[0].options["cookiesfrombrowser"] == ("firefox",)
    assert created.instances[0].extract_info_calls == [("https://example.com/watch?v=1", False)]


def test_get_video_title_omits_cookies_when_unavailable(youtube_dl_factory):
    """Test that title extraction omits Firefox cookies when no browser profile is available."""
    created = youtube_dl_factory(testee, cookies_available=False, extract_info_result={"title": "Cookieless Title"})

    result = testee.get_video_title("https://example.com/watch?v=2")

    assert result == "Cookieless Title"
    # Asking yt-dlp for browser cookies that do not exist makes it fail instead of extracting anonymously.
    assert "cookiesfrombrowser" not in created.instances[0].options


def test_get_video_title_and_id_reads_both_from_one_metadata_request(youtube_dl_factory):
    """Title and ID come from a single simulated yt-dlp extraction."""
    created = youtube_dl_factory(testee, cookies_available=False, extract_info_result={'title': 'Owned Title', 'id': 'n9xhJrPXop4'})
    assert testee.get_video_title_and_id('https://example.com/watch?v=3') == ('Owned Title', 'n9xhJrPXop4')
    assert len(created.instances) == 1
    assert created.instances[0].options['simulate'] is True
    assert created.instances[0].extract_info_calls == [('https://example.com/watch?v=3', False)]


def test_default_media_filename_tags_title_with_video_id():
    """Equal titles of different videos get different names, with reserved characters replaced."""
    first = testee.default_media_filename('Same: Title', 'aaaaaaaaaaa', '.mp4')
    second = testee.default_media_filename('Same: Title', 'bbbbbbbbbbb', '.mp4')
    assert first == 'Same_ Title [aaaaaaaaaaa].mp4'
    assert second == 'Same_ Title [bbbbbbbbbbb].mp4'


def test_default_media_filename_keeps_id_and_suffix_when_truncating_long_titles():
    """Titles equal up to the byte limit still differ by ID, and dots stay title text."""
    title = 'Mr. Smith Goes to Washington ' + 'x' * 300
    first = testee.default_media_filename(title + ' part 1', 'aaaaaaaaaaa', '.srt')
    second = testee.default_media_filename(title + ' part 2', 'bbbbbbbbbbb', '.srt')
    assert first == title[:220 - len(' [aaaaaaaaaaa].srt')] + ' [aaaaaaaaaaa].srt'
    assert second.endswith(' [bbbbbbbbbbb].srt')
    assert len(first.encode('utf-8')) == len(second.encode('utf-8')) == 220


def test_default_media_filename_replaces_reserved_characters_in_id():
    """An extractor ID containing a path separator cannot create a subdirectory."""
    assert testee.default_media_filename('Title', 'a/b', '.mp4') == 'Title [a_b].mp4'


def test_legacy_media_filename_matches_pre_id_naming():
    """The legacy name is the sanitized title, truncated to 220 bytes, plus the suffix."""
    assert testee.legacy_media_filename('Bad: Title', '.mp4') == 'Bad_ Title.mp4'
    assert testee.legacy_media_filename('y' * 300, '.srt') == 'y' * 216 + '.srt'


def test_legacy_media_filename_is_none_when_no_legacy_name_could_exist():
    """A title the old truncation rejected has no legacy file to look for."""
    assert testee.legacy_media_filename('x.' + 'a' * 300, '.mp4') is None


def test_resolve_default_media_path_uses_id_tagged_name_by_default(tmp_path):
    """Without existing files the ID-tagged path is chosen."""
    assert testee.resolve_default_media_path(tmp_path, 'Title', 'aaaaaaaaaaa', '.mp4') == tmp_path / 'Title [aaaaaaaaaaa].mp4'


def test_resolve_default_media_path_reuses_existing_legacy_file(tmp_path):
    """A title-only file from before IDs were added is reused when the tagged name is absent."""
    (tmp_path / 'Title.srt').write_text('legacy')
    assert testee.resolve_default_media_path(tmp_path, 'Title', 'aaaaaaaaaaa', '.srt') == tmp_path / 'Title.srt'


def test_resolve_default_media_path_prefers_existing_id_tagged_file(tmp_path):
    """When both names exist, the ID-tagged file wins over the legacy one."""
    (tmp_path / 'Title.mp4').write_text('legacy')
    (tmp_path / 'Title [aaaaaaaaaaa].mp4').write_text('tagged')
    assert testee.resolve_default_media_path(tmp_path, 'Title', 'aaaaaaaaaaa', '.mp4') == tmp_path / 'Title [aaaaaaaaaaa].mp4'


def test_resolve_default_media_path_ignores_legacy_directory(tmp_path):
    """Only a legacy regular file is reused, never a directory with that name."""
    (tmp_path / 'Title.mp4').mkdir()
    assert testee.resolve_default_media_path(tmp_path, 'Title', 'aaaaaaaaaaa', '.mp4') == tmp_path / 'Title [aaaaaaaaaaa].mp4'


def test_resolve_default_media_path_uses_tagged_name_when_no_legacy_name_could_exist(tmp_path):
    """A title the old naming rejected resolves straight to its ID-tagged name."""
    title = 'x.' + 'a' * 300
    assert testee.resolve_default_media_path(tmp_path, title, 'aaaaaaaaaaa', '.mp4') == tmp_path / (title[:220 - len(' [aaaaaaaaaaa].mp4')] + ' [aaaaaaaaaaa].mp4')


@pytest.mark.parametrize('suffix', ['.mp4', '.srt'])
def test_resolve_default_media_path_never_reuses_another_videos_tagged_file(tmp_path, suffix):
    """A title ending in another video's ID tag cannot pick up that video's file as legacy output."""
    (tmp_path / f'Title [aaaaaaaaaaa]{suffix}').write_text('video a')
    result = testee.resolve_default_media_path(tmp_path, 'Title [aaaaaaaaaaa]', 'bbbbbbbbbbb', suffix)
    assert result == tmp_path / f'Title [aaaaaaaaaaa] [bbbbbbbbbbb]{suffix}'


def test_resolve_default_media_path_reuses_legacy_file_tagged_with_its_own_id(tmp_path):
    """A legacy name ending in this video's own ID tag is still this video's file."""
    (tmp_path / 'Title [bbbbbbbbbbb].mp4').write_text('legacy')
    assert testee.resolve_default_media_path(tmp_path, 'Title [bbbbbbbbbbb]', 'bbbbbbbbbbb', '.mp4') == tmp_path / 'Title [bbbbbbbbbbb].mp4'


def test_resolve_default_media_path_reuses_legacy_file_whose_tag_is_followed_by_a_newline(tmp_path):
    """Only a tag at the very end of the stem blocks reuse, not one before a trailing newline."""
    (tmp_path / 'Title [aaaaaaaaaaa]\n.mp4').write_text('legacy')
    assert testee.resolve_default_media_path(tmp_path, 'Title [aaaaaaaaaaa]\n', 'bbbbbbbbbbb', '.mp4') == tmp_path / 'Title [aaaaaaaaaaa]\n.mp4'


def test_resolve_default_media_path_reuses_legacy_file_with_non_id_bracket(tmp_path):
    """Ordinary bracketed title text does not block reuse of a legacy file."""
    (tmp_path / 'Song [Official Video].mp4').write_text('legacy')
    assert testee.resolve_default_media_path(tmp_path, 'Song [Official Video]', 'bbbbbbbbbbb', '.mp4') == tmp_path / 'Song [Official Video].mp4'


def test_is_firefox_cookies_available_detects_cookie_file(monkeypatch, tmp_path, caplog):
    """Test that a cookies.sqlite under the Firefox profile is detected."""
    monkeypatch.setenv("HOME", str(tmp_path))
    cookies = tmp_path / ".mozilla" / "firefox" / "profile" / "cookies.sqlite"
    cookies.parent.mkdir(parents=True)
    cookies.write_text("cookie")

    with caplog.at_level(logging.INFO):
        assert testee.is_firefox_cookies_available() is True
    assert "Found Firefox cookies:" in caplog.text


def test_is_firefox_cookies_available_skips_non_file_matches(monkeypatch, tmp_path, caplog):
    """Test that a non-file named cookies.sqlite is skipped so a real cookie file deeper in the tree is still found."""
    monkeypatch.setenv("HOME", str(tmp_path))
    firefox_dir = tmp_path / ".mozilla" / "firefox"
    # rglob walks top down, so this directory shadowing the cookie file name is matched before the
    # real one below it. Both live under the same search root, so stepping over the non-file has to
    # resume the same scan; abandoning that root would miss the cookies that are actually there.
    (firefox_dir / "cookies.sqlite").mkdir(parents=True)
    real_cookies = firefox_dir / "profile" / "cookies.sqlite"
    real_cookies.parent.mkdir(parents=True)
    real_cookies.write_text("cookie")

    with caplog.at_level(logging.INFO):
        assert testee.is_firefox_cookies_available() is True
    assert f"Found Firefox cookies: {real_cookies}" in caplog.text


def test_is_firefox_cookies_available_returns_false_when_missing(monkeypatch, tmp_path, caplog):
    """Test that a missing cookies file reports cookies as unavailable."""
    monkeypatch.setenv("HOME", str(tmp_path))

    with caplog.at_level(logging.INFO):
        assert testee.is_firefox_cookies_available() is False
    assert "No Firefox cookies found" in caplog.text
