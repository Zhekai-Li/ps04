#!/usr/bin/env bash
# Minimal authenticated check; never prints the API key.
set -u
ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
PYTHON="$ROOT_DIR/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then echo "run bash scripts/setup.sh first" >&2; exit 2; fi
if [[ -z ${OPENAI_API_KEY:-} ]]; then echo "OPENAI_API_KEY is not set" >&2; exit 2; fi
cd "$ROOT_DIR" || exit 1
"$PYTHON" -c 'from openai import OpenAI; models=OpenAI().models.list(); print("OpenAI authentication succeeded; model listing returned", len(models.data), "entries")'
