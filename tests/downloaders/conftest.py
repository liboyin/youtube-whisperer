import pytest


class FakeYoutubeDL:
    """Record one owned downloader session without network or profile access."""

    def __init__(self, options, extract_info_result, error):
        """Initialize independent call records and injected operation outcomes.

        Args:
            options: Options supplied by the production caller.
            extract_info_result: Metadata returned unchanged, including None.
            error: Optional exception raised by extraction or download.
        """
        self.options = options
        self.extract_info_result = extract_info_result
        self.error = error
        self.extract_info_calls = []
        self.download_calls = []
        self.exit_calls = []

    def __enter__(self):
        """Enter this session without creating external resources."""
        return self

    def __exit__(self, exc_type, exc, tb):
        """Record context exit and propagate the original exception."""
        self.exit_calls.append((exc_type, exc, tb))
        return False

    def extract_info(self, url, download=False):
        """Record extraction and return injected metadata or raise its error."""
        self.extract_info_calls.append((url, download))
        if self.error is not None:
            raise self.error
        return self.extract_info_result

    def download(self, urls):
        """Record download URLs and raise an injected error when supplied."""
        self.download_calls.append(urls)
        if self.error is not None:
            raise self.error


class YoutubeDLFactory:
    """Install and record fresh downloader sessions owned by one test."""

    def __init__(self, mocker):
        """Retain the test-owned patch manager and independent records."""
        self.mocker = mocker
        self.instances = []
        self.extract_info_result = None
        self.error = None

    def __call__(self, module, *, cookies_available, extract_info_result=None, error=None):
        """Install the session constructor and inject cookie availability.

        Args:
            module: Source module whose downloader dependencies are patched.
            cookies_available: Synthetic cookie availability; no profile is read.
            extract_info_result: Metadata returned unchanged by new sessions.
            error: Optional original exception for downloader operations.

        Returns:
            YoutubeDLFactory: This factory with its test-local session records.
        """
        self.extract_info_result = extract_info_result
        self.error = error
        self.mocker.patch.object(module, 'is_firefox_cookies_available', return_value=cookies_available)
        self.mocker.patch.object(module.yt_dlp, 'YoutubeDL', side_effect=self.create)
        return self

    def create(self, options):
        """Create a session with fresh call records for supplied options."""
        instance = FakeYoutubeDL(options, self.extract_info_result, self.error)
        self.instances.append(instance)
        return instance


@pytest.fixture
def youtube_dl_factory(mocker):
    """Supply one function-scoped constructor with test-owned patch teardown."""
    return YoutubeDLFactory(mocker)
