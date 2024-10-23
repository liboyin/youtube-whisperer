from youtube_whisperer.worker import redis_connection

def test_redis_connection(mocker):
    mock_client = mocker.MagicMock()
    mocker.patch('youtube_whisperer.worker.get_redis_client', return_value=mock_client)
    with redis_connection() as client:
        assert client == mock_client
    mock_client.close.assert_called_once()
