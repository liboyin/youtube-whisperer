import pathlib_extensions

import youtube_whisperer.publication as testee


def test_publication_forwards_the_library_helpers_under_their_previous_names():
    """The D18 forwarder exports exactly the pathlib-extensions publication functions."""
    assert testee.__all__ == ['publish_staged_file', 'resolve_publication_target']
    assert testee.publish_staged_file is pathlib_extensions.publish_staged_file
    assert testee.resolve_publication_target is pathlib_extensions.resolve_publication_target
