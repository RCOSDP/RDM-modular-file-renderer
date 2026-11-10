import hashlib
import os
import shutil
import sys
import urllib.request
import zipfile

from invoke import task

WHEELHOUSE_PATH = os.environ.get('WHEELHOUSE')

ROOT = os.path.dirname(os.path.abspath(__file__))
NODE_MODULES = os.path.join(ROOT, 'node_modules')

# Browser-side libraries are declared in package.json and installed by `npm ci`; `invoke assets`
# copies the served files from node_modules into the static directories the templates load them
# from. The copies are not tracked by git (see .gitignore).
ASSET_FILES = {
    # destination under mfr/: source under node_modules/
    'server/static/js/jquery.min.js': 'jquery/dist/jquery.min.js',
    'server/static/js/jquery.min.map': 'jquery/dist/jquery.min.map',
    'server/static/js/bootstrap.min.js': 'bootstrap/dist/js/bootstrap.min.js',
    'server/static/css/bootstrap.min.css': 'bootstrap/dist/css/bootstrap.min.css',
    'extensions/tabular/static/js/bootstrap.min.js': 'bootstrap/dist/js/bootstrap.min.js',
    'extensions/tabular/static/css/bootstrap.min.css': 'bootstrap/dist/css/bootstrap.min.css',
    'extensions/image/static/js/jquery.mousewheel.js': 'jquery-mousewheel/jquery.mousewheel.js',
}
# bootstrap.min.css refers to ../fonts/, so the glyphicon fonts go next to each copy of it
for _font in ('eot', 'svg', 'ttf', 'woff', 'woff2'):
    for _static in ('server/static', 'extensions/tabular/static'):
        ASSET_FILES[f'{_static}/fonts/glyphicons-halflings-regular.{_font}'] = \
            f'bootstrap/dist/fonts/glyphicons-halflings-regular.{_font}'

# PDF.js: the engine (worker, renderer, cmaps, fonts, decoders, images) comes from the npm package
# pdfjs-dist like the other libraries, so package.json is the only place its version is written.
# The viewer page itself (viewer.mjs, viewer.css, the locale files) is not published on npm; it is
# only in the release archive on GitHub, and viewer.mjs has to be paired with the pdf.mjs of the
# same build because both embed an identifier generated at build time. `invoke assets` therefore
# downloads the archive for the installed version, checks its SHA-256 against the digest recorded
# in package.json under "mfr"."pdfjsViewerArchive" (published on the GitHub release page), checks
# that the files the archive shares with the npm package are identical, and copies the four
# viewer files from it. The legacy build is used because it also supports Safari, Edge and
# older Chrome and Firefox releases.
VENDOR_DIR = os.path.join(ROOT, 'vendor')
PDFJS_STATIC = os.path.join(ROOT, 'mfr', 'extensions', 'pdf', 'static')
PDFJS_NPM = os.path.join(NODE_MODULES, 'pdfjs-dist')
# directories copied whole from node_modules/pdfjs-dist: destination under mfr/: source
ASSET_DIRS = {
    'extensions/pdf/static/web/cmaps': 'pdfjs-dist/cmaps',
    'extensions/pdf/static/web/standard_fonts': 'pdfjs-dist/standard_fonts',
    'extensions/pdf/static/web/wasm': 'pdfjs-dist/wasm',
    'extensions/pdf/static/web/iccs': 'pdfjs-dist/iccs',
    'extensions/pdf/static/web/images': 'pdfjs-dist/legacy/web/images',
}
ASSET_FILES.update({
    'extensions/pdf/static/build/pdf.worker.mjs': 'pdfjs-dist/legacy/build/pdf.worker.mjs',
    'extensions/pdf/static/build/pdf.renderer.mjs': 'pdfjs-dist/legacy/build/pdf.renderer.mjs',
})
# archive members copied to the same path under mfr/extensions/pdf/static/
PDFJS_ARCHIVE_MEMBERS = ['build/pdf.mjs', 'web/viewer.mjs', 'web/viewer.css', 'web/locale/']
# archive members that must be identical to the npm package (archive path: npm path)
PDFJS_SHARED_MEMBERS = {
    'build/pdf.worker.mjs': 'legacy/build/pdf.worker.mjs',
    'build/pdf.renderer.mjs': 'legacy/build/pdf.renderer.mjs',
    'web/cmaps/': 'cmaps/',
    'web/standard_fonts/': 'standard_fonts/',
    'web/wasm/': 'wasm/',
    'web/iccs/': 'iccs/',
}


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _pdfjs_version_and_digest():
    """The installed pdfjs-dist version and the SHA-256 recorded for its viewer archive."""
    import json
    with open(os.path.join(PDFJS_NPM, 'package.json')) as f:
        version = json.load(f)['version']
    with open(os.path.join(ROOT, 'package.json')) as f:
        digests = json.load(f).get('mfr', {}).get('pdfjsViewerArchive', {})
    digest = digests.get(version)
    if not digest:
        sys.exit(f'package.json has no "mfr"."pdfjsViewerArchive" entry for pdfjs-dist {version}; '
                 f'add the SHA-256 of pdfjs-{version}-legacy-dist.zip shown on '
                 f'https://github.com/mozilla/pdf.js/releases/tag/v{version}')
    return version, digest


def _fetch_pdfjs_archive(version, digest):
    """Return the path of the verified archive, downloading it when missing or altered."""
    os.makedirs(VENDOR_DIR, exist_ok=True)
    name = f'pdfjs-{version}-legacy-dist.zip'
    archive = os.path.join(VENDOR_DIR, name)
    if os.path.isfile(archive) and _sha256(archive) == digest:
        return archive
    url = f'https://github.com/mozilla/pdf.js/releases/download/v{version}/{name}'
    print(f'downloading {url}')
    with urllib.request.urlopen(url, timeout=120) as response, open(archive, 'wb') as out:
        shutil.copyfileobj(response, out)
    actual = _sha256(archive)
    if actual != digest:
        os.remove(archive)
        sys.exit(f'{name}: SHA-256 is {actual}, package.json records {digest}')
    return archive


def _members(names, member):
    """Archive member names covered by `member` (a file, or a directory ending in /)."""
    if member.endswith('/'):
        return [n for n in names if n.startswith(member) and not n.endswith('/')]
    return [member] if member in names else []


def _copy_pdfjs_viewer(archive):
    """Check the archive against the npm package and copy the viewer files from it."""
    copied = 0
    with zipfile.ZipFile(archive) as zf:
        names = zf.namelist()
        for member, npm_path in PDFJS_SHARED_MEMBERS.items():
            selected = _members(names, member)
            if not selected:
                sys.exit(f'{os.path.basename(archive)} has no member {member}')
            for name in selected:
                # the same relative path below the npm directory as below the archive member
                relative = name[len(member):] if member.endswith('/') else ''
                npm_file = os.path.join(PDFJS_NPM, *npm_path.strip('/').split('/'),
                                        *relative.split('/')) if relative else \
                    os.path.join(PDFJS_NPM, *npm_path.split('/'))
                with zf.open(name) as f, open(npm_file, 'rb') as g:
                    if f.read() != g.read():
                        sys.exit(f'{name} in {os.path.basename(archive)} differs from '
                                 f'node_modules/pdfjs-dist/{npm_path}; not the same release')
        for member in PDFJS_ARCHIVE_MEMBERS:
            selected = _members(names, member)
            if not selected:
                sys.exit(f'{os.path.basename(archive)} has no member {member}')
            for name in selected:
                if name.startswith('/') or '..' in name.split('/'):
                    sys.exit(f'{os.path.basename(archive)}: refusing to extract {name}')
                dest = os.path.join(PDFJS_STATIC, *name.split('/'))
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with zf.open(name) as src, open(dest, 'wb') as out:
                    shutil.copyfileobj(src, out)
                copied += 1
    return copied


@task
def assets(ctx):
    """Copy the browser-side libraries into the static directories.

    Run `npm ci` first. Also downloads the PDF.js viewer archive matching the installed pdfjs-dist
    (into vendor/, once). The Docker build runs this in the build stage; for a local checkout run
    it once after cloning and again whenever package.json changes.
    """
    if not os.path.isdir(NODE_MODULES):
        sys.exit('node_modules/ not found; run `npm ci` first')
    for subdir in ('build', 'web'):
        shutil.rmtree(os.path.join(PDFJS_STATIC, subdir), ignore_errors=True)
    for dest, src in ASSET_FILES.items():
        src_path = os.path.join(NODE_MODULES, *src.split('/'))
        if not os.path.isfile(src_path):
            sys.exit(f'node_modules/{src} is missing; package.json and ASSET_FILES disagree')
        dest_path = os.path.join(ROOT, 'mfr', *dest.split('/'))
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        shutil.copyfile(src_path, dest_path)
    for dest, src in ASSET_DIRS.items():
        src_path = os.path.join(NODE_MODULES, *src.split('/'))
        if not os.path.isdir(src_path):
            sys.exit(f'node_modules/{src} is missing; package.json and ASSET_DIRS disagree')
        shutil.copytree(src_path, os.path.join(ROOT, 'mfr', *dest.split('/')), dirs_exist_ok=True)
    print(f'copied {len(ASSET_FILES)} files and {len(ASSET_DIRS)} directories from node_modules')
    version, digest = _pdfjs_version_and_digest()
    copied = _copy_pdfjs_viewer(_fetch_pdfjs_archive(version, digest))
    print(f'copied {copied} viewer files from pdfjs-{version}-legacy-dist.zip')


@task
def flake(ctx):
    ctx.run('poetry run flake8 .', pty=True)


@task
def test(ctx, verbose=False, nocov=False, extension=None, path=None):
    """Run full or customized tests for MFR.
    :param ctx: the ``invoke`` context
    :param verbose: the flag to increase verbosity
    :param nocov: the flag to disable coverage
    :param extension: limit the tests to the given extension only
    :param path: limit the tests to the given path only
    :return: None
    """
    flake(ctx)
    # `--extension=` and `--path=` are mutually exclusive options
    assert not (extension and path)
    if path:
        path = f'/{path}' if path else ''
    elif extension:
        path = f'/extensions/{extension}/' if extension else ''
    else:
        path = ''
    coverage = ' --cov-report term-missing --cov mfr' if not nocov else ''
    verbose = '-v' if verbose else ''
    cmd = f'poetry run pytest{coverage} tests{path} {verbose}'
    ctx.run(cmd, pty=True)


@task
def server(ctx):
    if os.environ.get('REMOTE_DEBUG', None):
        import pydevd
        # e.g. '127.0.0.1:5678'
        remote_parts = os.environ.get('REMOTE_DEBUG').split(':')
        pydevd.settrace(remote_parts[0], port=int(remote_parts[1]), suspend=False, stdoutToServer=True, stderrToServer=True)

    from mfr.server.app import serve
    serve()

@task
def celery(ctx, loglevel='INFO', hostname='%h', concurrency=None):
    from mfr.tasks.app import app
    command = ['worker']
    if loglevel:
        command.extend(['--loglevel', loglevel])
    if hostname:
        command.extend(['--hostname', hostname])
    if concurrency:
        command.extend(['--concurrency', concurrency])
    app.worker_main(command)


@task
def newrelic_init(ctx, key=None, verbose=False):
    if key is None:
        sys.exit('No newrelic api key given.  Please generate one and rerun this command '
                 'with `invoke newrelic-init --key=$key`')

    cmd_tmpl = 'newrelic-admin generate-config {} newrelic.ini'
    cmd = cmd_tmpl.format(key)
    if verbose:
        print(cmd_tmpl.format('<redacted>'))
    ctx.run(cmd, pty=True)


@task
def newrelic_server(ctx, config='newrelic.ini', verbose=False):
    if not os.path.exists(config):
        sys.exit("Couldn't find config file '{}'.  Check path or run `invoke newrelic_init` "
                 "to generate it.".format(config))

    cmd = f'poetry run env NEW_RELIC_CONFIG_FILE={config} newrelic-admin run-program invoke server'
    if verbose:
        print(cmd)
    ctx.run(cmd, pty=True)
