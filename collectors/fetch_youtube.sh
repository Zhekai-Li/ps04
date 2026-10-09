#!/usr/bin/env bash
set -u
if [[ $# -ne 1 ]]; then echo "usage: bash collectors/fetch_youtube.sh RUN_DIR" >&2; exit 2; fi
ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
PYTHON="$ROOT_DIR/.venv/bin/python"; [[ -x "$PYTHON" ]] || PYTHON=python3.12
cd "$ROOT_DIR" || exit 1
exec "$PYTHON" -m src.collectors youtube "$1"
