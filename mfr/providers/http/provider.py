import os
import hashlib
import logging
import mimetypes
from urllib.parse import urlparse


from waterbutler.core import streams

from mfr.core import provider
from mfr.core import exceptions
from mfr.core import utils

logger = logging.getLogger(__name__)


class HttpProvider(provider.BaseProvider):
    """Basic MFR provider.  Infers file metadata (extension, type) from the url. Downloads by
    issuing a GET to the url.
    """

    NAME = 'http'

    async def metadata(self):
        path = urlparse(self.url).path
        name, ext = os.path.splitext(os.path.split(path)[-1])
        content_type, _ = mimetypes.guess_type(self.url)
        unique_key = hashlib.sha256(self.url.encode('utf-8')).hexdigest()
        return provider.ProviderMetadata(name, ext, content_type, unique_key, self.url)

    async def download(self):
        # The response is kept open on purpose, the returned stream reads from it.
        response = await utils.get_client_session().get(self.url)
        if response.status >= 400:
            err_resp = await response.text()
            await response.release()
            logger.error(f'Unable to download file: ({response.status}) {err_resp}')
            raise exceptions.DownloadError(
                'Unable to download the requested file, please try again later.',
                download_url=self.url,
                response=err_resp,
                code=response.status,
                provider='http',
            )
        return streams.ResponseStreamReader(response)
