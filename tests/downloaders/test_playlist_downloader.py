import inspect

import youtube_whisperer.downloaders.playlist_downloader as testee


def test_yield_flattened_video_urls(mocker):
    mock_yield_playlist = mocker.patch.object(
        testee,
        'yield_video_urls_from_playlist',
        return_value=iter(['video1', 'video2'])
    )
    result = testee.yield_flattened_video_urls([
        'https://youtube.com/watch?v=direct1',
        'https://youtube.com/playlist?list=123',
        'https://youtube.com/watch?v=direct2',
    ])
    assert inspect.isgenerator(result)
    assert list(result) == ['https://youtube.com/watch?v=direct1', 'video1', 'video2', 'https://youtube.com/watch?v=direct2']
    mock_yield_playlist.assert_called_once_with('https://youtube.com/playlist?list=123')
