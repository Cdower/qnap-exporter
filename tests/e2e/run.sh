#!/usr/bin/env bash
# Runs the end-to-end test: starts a simulated QNAP NAS, a Prometheus
# remote_write receiver and the exporter, then checks what arrives.
#
#   tests/e2e/run.sh                 # builds docker/ and tests it
#   EXPORTER_IMAGE=img:tag tests/e2e/run.sh --no-build
#                                    # tests an image built elsewhere
#
# Any further arguments are passed to check.py.
#
# Set KEEP=1 to leave the stack running afterwards for poking at
# http://127.0.0.1:12345 (Alloy UI) and http://127.0.0.1:9090 (receiver).
set -euo pipefail

cd "$(dirname "$0")"

build_flag=--build
if [[ "${1:-}" == "--no-build" ]]; then
  shift
  build_flag=--no-build
  # snmpsim is local to the test, so it is always built.
  docker compose build snmpsim
fi

cleanup() {
  status=$?
  if [[ $status -ne 0 ]]; then
    echo "::group::exporter logs"
    docker compose logs --no-color exporter || true
    echo "::endgroup::"
    echo "::group::receiver logs"
    docker compose logs --no-color receiver || true
    echo "::endgroup::"
    echo "::group::snmpsim logs (last 200 lines)"
    docker compose logs --no-color --tail 200 snmpsim || true
    echo "::endgroup::"
  fi
  if [[ "${KEEP:-0}" != "1" ]]; then
    docker compose down --volumes --remove-orphans >/dev/null 2>&1 || true
  fi
  exit $status
}
trap cleanup EXIT

docker compose up --detach "$build_flag"
python3 check.py "$@"
