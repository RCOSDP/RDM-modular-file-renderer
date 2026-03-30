#!/bin/bash
set -euo pipefail
set -x

if [ "$#" -ne 1 ]; then
    echo "usage: $0 <TEST_BUILD>" >&2
    exit 1
fi

TEST_BUILD="$1"
REPO_ROOT=$(git rev-parse --show-toplevel)
cd "$REPO_ROOT"

read -r -d '' container_script <<'BASH' || true
export WHEELHOUSE=$HOME/wheelhouse
pip install --upgrade pip
pip install setuptools==37.0.0
pip install wheel==0.26.0
pip install invoke==0.13.0
invoke wheelhouse --develop
invoke install --develop
invoke test
BASH

docker run --rm -t \
    -e TEST_BUILD="$TEST_BUILD" \
    ${MFR_TEST_IMAGE} bash -lc "$container_script"
