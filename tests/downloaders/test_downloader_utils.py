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
