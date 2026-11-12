import pytest
from importlib.metadata import entry_points

from mfr.core import utils as mfr_utils
from mfr.core.utils import fix_name


class TestGetRendererName:

    def test_get_renderer_name_explicit_assertions(self):
        assert mfr_utils.get_renderer_name('jpg') == 'ImageRenderer'
        assert mfr_utils.get_renderer_name('txt') == 'CodePygmentsRenderer'
        assert mfr_utils.get_renderer_name('xlsx') == 'TabularRenderer'
        assert mfr_utils.get_renderer_name('odt') == 'UnoconvRenderer'
        assert mfr_utils.get_renderer_name('pdf') == 'PdfRenderer'

    def test_get_renderer_name(self):
        for ep in entry_points().select(group='mfr.renderers'):
            expected = ep.value.split(":")[1].split('.')[0]
            assert mfr_utils.get_renderer_name(ep.name) == expected

    def test_get_renderer_name_no_entry_point(self):
        assert mfr_utils.get_renderer_name('.jpg') == ''  # extensions must begin with a period


class TestGetExporterName:

    def test_get_exporter_name_explicit_assertions(self):
        assert mfr_utils.get_exporter_name('jpg') == 'ImageExporter'
        assert mfr_utils.get_exporter_name('odt') == 'UnoconvExporter'

    def test_get_exporter_name(self):
        for ep in entry_points().select(group='mfr.exporters'):
            expected = ep.value.split(":")[1].split('.')[0]
            assert mfr_utils.get_exporter_name(ep.name) == expected

    def test_get_exporter_name_no_entry_point(self):
        assert mfr_utils.get_exporter_name('.jpg') == ''  # extensions must begin with a period

@pytest.mark.parametrize(
    "inp, out",
    [
        ["jpg", "jpg"],
        ["c++", "cpp"],
        ["h++", "hpp"],
        ["php[345]", "php"],
        ["lasso[89]", "lasso"],
        ["css.in", "css"],
        ["js.in", "js"],
        ["xul.in", "xul"],
    ],
)
def test_fix_name(inp, out):
    assert fix_name(inp) == out
    assert fix_name(f'.{inp}') == out


class TestClientSession:

    def test_session_is_shared_and_keeps_no_cookies(self):
        import asyncio
        import aiohttp

        async def check():
            first = mfr_utils.get_client_session()
            second = mfr_utils.get_client_session()
            assert first is second
            assert isinstance(first.cookie_jar, aiohttp.DummyCookieJar)
            await mfr_utils.close_client_session()
            assert first.closed
            third = mfr_utils.get_client_session()
            assert third is not first
            await mfr_utils.close_client_session()

        asyncio.run(check())
