import os
import shutil
import sys

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


@task
def wheelhouse(ctx, develop=False, pty=True):
    extras = '--with dev' if develop else ''
    cmd = f'poetry export --format=requirements.txt {extras} | pip wheel --find-links={WHEELHOUSE_PATH} -r /dev/stdin --wheel-dir={WHEELHOUSE_PATH}'
    ctx.run(cmd, pty=pty)


@task
def install(ctx, develop=False, pty=True):
    extras = '--with dev' if develop else ''
    ctx.run(f'poetry install {extras}', pty=pty)


@task
def assets(ctx):
    """Copy the browser-side libraries from node_modules into the static directories.

    Run `npm ci` first. The Docker build runs this in the build stage; for a local checkout run
    it once after cloning and again whenever package.json changes.
    """
    if not os.path.isdir(NODE_MODULES):
        sys.exit('node_modules/ not found; run `npm ci` first')
    for dest, src in ASSET_FILES.items():
        src_path = os.path.join(NODE_MODULES, src)
        if not os.path.isfile(src_path):
            sys.exit(f'node_modules/{src} is missing; package.json and ASSET_FILES disagree')
        dest_path = os.path.join(ROOT, 'mfr', dest)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        shutil.copyfile(src_path, dest_path)
    print(f'copied {len(ASSET_FILES)} files into mfr/')


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
