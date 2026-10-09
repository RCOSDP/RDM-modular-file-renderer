import asyncio
from unittest import mock

import pytest

from waterbutler.core import streams

from mfr.core import exceptions
from mfr.providers.osf import OsfProvider


WB_URL = 'http://localhost:7777/v1/resources/abcde/providers/osfstorage/0123456789'
SIGNED_URL = 'https://storage.example.com/bucket/key?X-Amz-Signature=secret'


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
    return OsfProvider(request, WB_URL, {})


class TestOsfProviderDownload:

    def test_download_streams_direct_response(self, provider):
        response = make_response(200, {'Content-Length': '3'})
        with mock.patch.object(provider, '_make_request', mock.AsyncMock(return_value=response)):
            stream = asyncio.run(provider.download())

        assert isinstance(stream, streams.ResponseStreamReader)
        assert stream.response is response
        response.release.assert_not_awaited()

    def test_download_follows_redirect_to_location_without_credentials(self, provider):
        redirect = make_response(302, {'location': SIGNED_URL})
        final = make_response(200, {'Content-Length': '3'})
        session = mock.Mock()
        session.get = mock.AsyncMock(return_value=final)

        with mock.patch.object(provider, '_make_request', mock.AsyncMock(return_value=redirect)) as make_request, \
                mock.patch('mfr.core.utils.get_client_session', return_value=session):
            stream = asyncio.run(provider.download())

        # the first request goes to WaterButler with the MFR header and no redirect following
        make_request.assert_awaited_once()
        assert make_request.await_args.args[:2] == ('GET', WB_URL)
        assert make_request.await_args.kwargs['allow_redirects'] is False
        # the redirect target is fetched as-is, and the final response is what gets streamed
        redirect.release.assert_awaited_once()
        session.get.assert_awaited_once_with(SIGNED_URL)
        assert isinstance(stream, streams.ResponseStreamReader)
        assert stream.response is final
        assert provider.metrics.serialize()['download']['saw_redirect'] is True

    def test_download_error_response(self, provider):
        response = make_response(404, text='not found')
        with mock.patch.object(provider, '_make_request', mock.AsyncMock(return_value=response)):
            with pytest.raises(exceptions.DownloadError) as exc:
                asyncio.run(provider.download())

        assert exc.value.download_url == WB_URL
        assert exc.value.response == 'not found'
        response.release.assert_awaited_once()
