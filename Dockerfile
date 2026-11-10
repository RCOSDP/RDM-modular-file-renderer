# Assets stage: installs the browser-side libraries declared in package.json. Only
# node_modules is carried over, so Node.js and npm stay out of the other stages.
FROM node:24-slim AS assets

WORKDIR /assets
COPY package.json package-lock.json /assets/
# --omit=optional: pdfjs-dist lists a native canvas binding for Node.js that the browser never uses
RUN npm ci --omit=optional --ignore-scripts --no-audit --no-fund


# Build stage: compilers and development headers are only needed to install
# the Python dependencies, so they stay out of the runtime image.
FROM python:3.13-slim AS build

ENV POETRY_HOME=/opt/poetry \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=0 \
    POETRY_VIRTUALENVS_IN_PROJECT=1
ENV PATH="${POETRY_HOME}/bin:${PATH}"

RUN apt-get update \
    && apt-get install -y \
        # waterbutler is installed from a git repository
        git \
        build-essential \
        libffi-dev \
        libssl-dev \
    && apt-get clean \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Keep poetry in its own virtualenv so it is not installed into site-packages
RUN python -m venv ${POETRY_HOME} \
    && ${POETRY_HOME}/bin/pip install --no-cache-dir poetry==2.1.2

RUN mkdir -p /code
WORKDIR /code

COPY pyproject.toml poetry.lock /code/
RUN poetry install --no-root --without=docs

# Copy the rest of the code over
COPY ./ /code/

# Install the project and verify the resolved dependency tree is self-consistent
RUN poetry install --without=docs \
    && python -m pip check

# Copy the served files from node_modules and the PDF.js viewer archive into the static
# directories (tasks.py)
COPY --from=assets /assets/node_modules /code/node_modules
RUN /usr/local/bin/python -m invoke assets


# Runtime stage
FROM python:3.13-slim

RUN usermod -d /home www-data && chown www-data:www-data /home

RUN apt-get update \
    # pick up Debian security updates published after the base image was built
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends \
        # convert .step to jsc3d-compatible format
        freecad \
        # convert SPSS .sav to .csv (pspp-convert)
        pspp \
        # grab gosu for easy step-down from root
        gosu \
    && apt-get clean \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

COPY --from=build /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=build /usr/local/bin /usr/local/bin
# nbconvert templates used by the ipynb renderer live outside site-packages
COPY --from=build /usr/local/share/jupyter /usr/local/share/jupyter
COPY --from=build /code /code

# pip is not needed at runtime and ships its own copies of urllib3, msgpack and
# setuptools, so remove it together with the wheel bundled for ensurepip
RUN python3 -m pip uninstall -y pip \
    && rm -rf /usr/local/lib/python3.13/ensurepip/_bundled \
    && rm -f /usr/local/bin/pip /usr/local/bin/pip3 /usr/local/bin/pip3.13

WORKDIR /code

ARG GIT_COMMIT=
ENV GIT_COMMIT=${GIT_COMMIT}

EXPOSE 7778

CMD ["gosu", "www-data", "python3", "-m", "invoke", "server"]
