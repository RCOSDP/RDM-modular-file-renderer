"""Every static file a viewer template loads must exist.

The browser-side libraries are copied into the static directories by `invoke assets` (tasks.py),
so this guards the mapping there against the references in the templates: a file the templates
load but the task does not copy, or a template still pointing at a removed file, fails here.
"""
import glob
import os
import posixpath
import re

import pytest

MFR_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'mfr')
SERVER_STATIC = os.path.join(MFR_ROOT, 'server', 'static')

# attribute references and the string literals handed to $.getScript / getScripts
REFERENCE_RE = re.compile(r"""(?:src|href|poster)="([^"]+)"|'(\$\{base\}/[^']+)'""")
BASE_HREF_RE = re.compile(r'<base href="\$\{base\}/([^"]*)"')
SKIP_PREFIXES = ('http://', 'https://', '//', '#', 'data:', 'mailto:', 'javascript:')


def _templates():
    return sorted(glob.glob(os.path.join(MFR_ROOT, '**', 'templates', '*.mako'), recursive=True))


def _resolve(template, reference, base_dir):
    """Map a reference in the template to a path on disk, or None if it is not a static file."""
    if reference.startswith(SKIP_PREFIXES):
        return None
    if reference.startswith('/static/'):
        return os.path.join(SERVER_STATIC, *reference[len('/static/'):].split('/'))
    if reference.startswith('static/'):
        # relative to the page URL /render, so it also resolves to /static/
        return os.path.join(SERVER_STATIC, *reference[len('static/'):].split('/'))
    extension_static = os.path.join(os.path.dirname(os.path.dirname(template)), 'static')
    if reference.startswith('${base}/'):
        return os.path.join(extension_static, *reference[len('${base}/'):].split('/'))
    if '${' in reference:
        return None  # built from template variables (file URLs, options)
    if base_dir is not None:
        # the pdf viewer declares <base href="${base}/web/">, so plain paths are relative to it
        relative = posixpath.normpath(posixpath.join(base_dir, reference))
        return os.path.join(extension_static, *relative.split('/'))
    return None


def _references():
    for template in _templates():
        text = open(template, encoding='utf-8').read()
        base_match = BASE_HREF_RE.search(text)
        base_dir = base_match.group(1) if base_match else None
        for match in REFERENCE_RE.finditer(text):
            reference = match.group(1) or match.group(2)
            path = _resolve(template, reference, base_dir)
            if path is not None:
                yield os.path.relpath(template, MFR_ROOT), reference, path


@pytest.mark.parametrize('template, reference, path', list(_references()),
                         ids=lambda value: value if isinstance(value, str) and '$' not in value
                         and '/' not in value else None)
def test_referenced_static_file_exists(template, reference, path):
    if reference.endswith('/'):  # <base href="${base}/web/"> names a directory
        assert os.path.isdir(path), f'{template} declares base {reference} but it is not a directory'
        return
    assert os.path.isfile(path), (
        f'{template} loads {reference} but {os.path.relpath(path, MFR_ROOT)} does not exist; '
        f'run `invoke assets` or fix ASSET_FILES in tasks.py'
    )


def test_pdf_viewer_worker_and_cmaps_exist():
    web_dir = os.path.join(MFR_ROOT, 'extensions', 'pdf', 'static', 'web')
    viewer_js = open(os.path.join(web_dir, 'viewer.js'), encoding='utf-8').read()
    for setting in ('workerSrc', 'cMapUrl'):
        match = re.search(rf"PDFJS\.{setting} = '([^']+)'", viewer_js)
        assert match, f'PDFJS.{setting} not found in viewer.js'
        path = os.path.normpath(os.path.join(web_dir, *match.group(1).split('/')))
        assert os.path.exists(path), f'PDFJS.{setting} points at a missing path: {match.group(1)}'


def test_every_reference_was_found():
    # sanity check on the scan itself: the templates reference dozens of files
    assert len(list(_references())) > 40
