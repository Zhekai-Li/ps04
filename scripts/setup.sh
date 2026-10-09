#!/usr/bin/env bash
# Creates the pinned Python 3.12 environment. Exit 0 success, 1 operational failure, 2 invalid environment.
set -u
ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT_DIR" || exit 1
if ! command -v python3.12 >/dev/null 2>&1; then echo "python3.12 is required" >&2; exit 2; fi
python3.12 -m venv .venv || exit 1
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
mkdir -p data/assets data/cache data/evidence data/media runs
echo "Environment ready. Set OPENAI_API_KEY locally, then run: bash scripts/check_openai.sh" >&2
