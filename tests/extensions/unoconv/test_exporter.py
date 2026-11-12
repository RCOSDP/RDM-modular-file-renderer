"""Integration tests for the unoconv exporter against a running unoserver.

These tests need a LibreOffice conversion server (see Dockerfile.unoserver) reachable at
``UNOSERVER_EXTENSION_CONFIG_HOST`` / ``UNOSERVER_EXTENSION_CONFIG_PORT``.  They are skipped
unless ``MFR_UNOSERVER_TESTS`` is set, so the rest of the suite does not depend on it.
"""
import os

import pytest

from mfr.core import exceptions
from mfr.core import utils as mfr_utils
from mfr.extensions.unoconv import UnoconvExporter

BASE = os.path.dirname(os.path.abspath(__file__))

pytestmark = pytest.mark.skipif(
    not os.environ.get('MFR_UNOSERVER_TESTS'),
    reason='set MFR_UNOSERVER_TESTS=1 and point UNOSERVER_EXTENSION_CONFIG_HOST at a unoserver',
)


@pytest.fixture
def directory(tmpdir):
    return str(tmpdir)


class TestUnoconvExporter:

    @pytest.mark.parametrize('file_name', ['test.docx', 'test.pptx', 'test.odt', 'test.ods'])
    def test_export_to_pdf(self, directory, file_name):
        source_file_path = os.path.join(BASE, 'files', file_name)
        output_file_path = os.path.join(directory, 'test.pdf')
        ext = os.path.splitext(file_name)[1]

        exporter = mfr_utils.make_exporter(ext, source_file_path, output_file_path, 'pdf', {})
        assert isinstance(exporter, UnoconvExporter)
        assert not os.path.exists(output_file_path)

        exporter.export()

        assert os.path.exists(output_file_path)
        with open(output_file_path, 'rb') as fp:
            pdf = fp.read()
        assert pdf.startswith(b'%PDF-')
        # every fixture contains Japanese text, which must be embedded with a CJK font
        assert b'NotoSansCJK' in pdf or b'NotoSerifCJK' in pdf

    def test_export_missing_file(self, directory):
        # LibreOffice happily imports arbitrary bytes as text, so a missing source file is the
        # reliable way to exercise the error path of the exporter
        source_file_path = os.path.join(directory, 'missing.docx')
        output_file_path = os.path.join(directory, 'missing.pdf')

        exporter = mfr_utils.make_exporter('.docx', source_file_path, output_file_path, 'pdf', {})

        with pytest.raises(exceptions.SubprocessError) as exc:
            exporter.export()

        assert exc.value.process == 'unoserver'
        assert not os.path.exists(output_file_path)
