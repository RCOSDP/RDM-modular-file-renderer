from http import HTTPStatus

import pytest
from tornado import testing
from tornado.httpclient import HTTPClientError

from mfr.server import settings as server_settings
from mfr.server.app import http_server_options

from tests import utils


class TestRequestLimits(utils.HandlerTestCase):
    """The server caps request bodies and headers so crafted requests are refused before
    tornado parses them (handlers only answer GET and never read a body)."""

    def get_httpserver_options(self):
        return http_server_options()

    @testing.gen_test
    def test_ordinary_request_is_served(self):
        resp = yield self.http_client.fetch(self.get_url('/status'))
        assert resp.code == HTTPStatus.OK

    @testing.gen_test
    def test_oversized_body_is_refused(self):
        body = b'a' * (server_settings.MAX_BODY_SIZE + 1)
        with pytest.raises(HTTPClientError) as exc:
            yield self.http_client.fetch(
                self.get_url('/status'), method='POST', body=body,
                headers={'Content-Type': 'multipart/form-data; boundary=x'},
            )
        assert exc.value.code in (HTTPStatus.BAD_REQUEST, 599)

    @testing.gen_test
    def test_oversized_headers_are_refused(self):
        with pytest.raises(HTTPClientError) as exc:
            yield self.http_client.fetch(
                self.get_url('/status'),
                headers={'X-Padding': 'a' * (server_settings.MAX_HEADER_SIZE + 1)},
            )
        assert exc.value.code in (HTTPStatus.BAD_REQUEST, 599)
