import asyncio
from unittest import mock

import pytest

from waterbutler.core import streams

from mfr.core import exceptions
from mfr.providers.http import HttpProvider


URL = 'http://localhost:7777/test.docx'  # localhost:7777 is in the default allowed provider domains


def make_response(status, headers=None, text=''):
    response = mock.Mock()
    response.status = status
    response.headers = headers or {}
    response.release = mock.AsyncMock()
    response.text = mock.AsyncMock(return_value=text)
    response.content = mock.Mock()
    return response


@pytest.fixture
def provider():
    request = mock.Mock()
    request.headers = {}
    request.cookies = {}
    request.query_arguments = {}
    return HttpProvider(request, URL, {})


class TestHttpProviderDownload:

    def test_download_keeps_response_open_for_streaming(self, provider):
        response = make_response(200, {'Content-Length': '3'})
        session = mock.Mock()
        session.get = mock.AsyncMock(return_value=response)

        with mock.patch('mfr.providers.http.provider.ClientSession', return_value=session):
            stream = asyncio.run(provider.download())

        session.get.assert_awaited_once_with(URL)
        assert isinstance(stream, streams.ResponseStreamReader)
        assert stream.response is response
        response.release.assert_not_awaited()

    def test_download_error_response(self, provider):
        response = make_response(404, text='not found')
        session = mock.Mock()
        session.get = mock.AsyncMock(return_value=response)

        with mock.patch('mfr.providers.http.provider.ClientSession', return_value=session):
            with pytest.raises(exceptions.DownloadError) as exc:
                asyncio.run(provider.download())

        assert exc.value.download_url == URL
        assert exc.value.response == 'not found'
        response.release.assert_awaited_once()
