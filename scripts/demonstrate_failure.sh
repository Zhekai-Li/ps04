#!/usr/bin/env bash
# Creates a labeled failure-demo run with a deliberately failed collector and partial continuation.
set -u
if [[ $# -gt 1 ]]; then echo "usage: bash scripts/demonstrate_failure.sh [feeds|youtube|podcasts]" >&2; exit 2; fi
ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
PYTHON="$ROOT_DIR/.venv/bin/python"; [[ -x "$PYTHON" ]] || PYTHON=python3.12
cd "$ROOT_DIR" || exit 1
FAIL_KIND=${1:-youtube}
case "$FAIL_KIND" in feeds|youtube|podcasts) ;; *) echo "invalid collector kind: $FAIL_KIND" >&2; exit 2;; esac
RUN_DIR=$("$PYTHON" -m src.run_setup create failure-demo) || exit $?
bash data/store.sh init || exit 1
PS04_FAIL_COLLECTOR="$FAIL_KIND" bash workflows/collect_sources.sh "$RUN_DIR"
collection_code=$?
bash reporting/summarize_run.sh "$RUN_DIR" > "$RUN_DIR/summary.json"
cat "$RUN_DIR/summary.json"
[[ $collection_code -eq 1 ]] || exit 1
exit 0
