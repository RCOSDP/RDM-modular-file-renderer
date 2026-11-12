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

NETWORK="mfr-tests-$$"
docker network create "$NETWORK"
cleanup() {
    docker rm -f mfr-unoserver >/dev/null 2>&1 || true
    docker network rm "$NETWORK" >/dev/null 2>&1 || true
}
trap cleanup EXIT

# Start the LibreOffice conversion server so the unoconv exporter tests run against the real thing
docker run -d --name mfr-unoserver --network "$NETWORK" "${MFR_UNOSERVER_IMAGE}"
for _ in $(seq 1 60); do
    if docker logs mfr-unoserver 2>&1 | grep -q 'INFO:unoserver:Started.'; then
        break
    fi
    sleep 1
done
docker logs mfr-unoserver 2>&1 | grep -q 'INFO:unoserver:Started.'

read -r -d '' container_script <<'BASH' || true
poetry install --without=docs --with=dev
invoke test
BASH

docker run --rm -t \
    --network "$NETWORK" \
    -e TEST_BUILD="$TEST_BUILD" \
    -e MFR_UNOSERVER_TESTS=1 \
    -e UNOSERVER_EXTENSION_CONFIG_HOST=mfr-unoserver \
    ${MFR_TEST_IMAGE} bash -c "$container_script"
