#!/usr/bin/env bash
set -u
if [[ $# -ne 1 ]]; then echo "usage: bash processing/extract_content.sh RUN_DIR < candidates.jsonl" >&2; exit 2; fi
ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
PYTHON="$ROOT_DIR/.venv/bin/python"; [[ -x "$PYTHON" ]] || PYTHON=python3.12
cd "$ROOT_DIR" || exit 1
exec "$PYTHON" -m src.extraction "$1"
