# MFR (Modular File Renderer)

`master` Build Status: [![Build Status](https://travis-ci.org/RCOSDP/RDM-modular-file-renderer.svg?branch=master)](https://travis-ci.org/RCOSDP/RDM-modular-file-renderer)

`develop` Build Status: [![Build Status](https://travis-ci.org/RCOSDP/RDM-modular-file-renderer.svg?branch=develop)](https://travis-ci.org/RCOSDP/RDM-modular-file-renderer)

[![Coverage Status](https://coveralls.io/repos/github/RCOSDP/RDM-modular-file-renderer/badge.svg)](https://coveralls.io/github/RCOSDP/RDM-modular-file-renderer)

A Python package for rendering files to HTML via an embeddable iframe.

### Compatibility

MFR is compatible with Python 3.13.

### Documentation

Documentation available at: http://modular-file-renderer.readthedocs.io/en/latest/

### Setting up

Install the latest version of python3.13.

For MacOSX users:

```bash
brew install python@3.13
# optional, needed for some converters
brew install pspp libreoffice
```
For Ubuntu users:

```bash
apt-get install python3.13
# optional, needed for some converters
apt-get install pspp libreoffice
```

After installing python3.13, set up the project with the following commands:

```bash
pip install poetry
poetry env use python3.13
poetry install

poetry run invoke install
poetry run invoke server
```

The browser-side libraries the renderers load are not kept in the repository: jQuery, Bootstrap,
jquery-mousewheel and PDF.js are declared in `package.json`. The PDF.js viewer page is not on
npm, so the task below also downloads the release archive of the installed PDF.js version from
GitHub and checks it against the SHA-256 recorded in `package.json` (`mfr.pdfjsViewerArchive`;
add the digest shown on the GitHub release page when updating the version). Install the npm
packages and copy everything into the static directories before starting the server, and again
whenever `package.json` changes:

```bash
npm ci --omit=optional
poetry run invoke assets
```

### Configuring

MFR configuration is done through a JSON file (`mfr-test.json`) that lives in the `.cos` directory of your home directory.  If this is your first time setting up MFR or its sister project, [WaterButler](https://github.com/CenterForOpenScience/waterbutler/), you probably do not have this directory and will need to create it:

```bash
mkdir ~/.cos
```

The defaults should suffice for most local testing.  If you're running the OSF or WaterButler on something other than `http://localhost:5000/` and `http://localhost:7777/`, you'll need to update the `ALLOWED_PROVIDER_DOMAINS` settings value. `ALLOWED_PROVIDER_DOMAINS` is a list formatted as a space-separated string.  This allows MFR to be configured via an environment variable (which are always strings), as is done in the OSF's `.docker-compose.mfr.env`.  Example of customized domains:

```json
{
  "SERVER_CONFIG": {
    "ALLOWED_PROVIDER_DOMAINS": "http://my_osf:5001/ http://my_wb:23405/"
  }
}
```

If you encounter the error message `TypeError: throw() takes 2 positional arguments but 4 were given`, you've run into a [core asyncio bug](https://bugs.python.org/issue25394)!  This bug is triggered by turning on debugging. You'll need to set the `SERVER_CONFIG.DEBUG` flag to `false`:

```json
{
  "SERVER_CONFIG": {
    "DEBUG": false
  }
}
```

### Testing

Before running the tests, you will need to install some additional requirements. In your checkout, run:

```bash
poetry run invoke install --develop
poetry run invoke test
```

### Create your own module

Interested in adding support for a new provider or file format? Check out the CONTRIBUTING.rst docs.

### License

Copyright 2013-2018 Center for Open Science

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

### COS is hiring!

Want to help save science? Want to get paid to develop free, open source software? [Check out our openings!](https://cos.io/our-communities/jobs/)
