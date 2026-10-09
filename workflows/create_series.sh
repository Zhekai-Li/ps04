#!/usr/bin/env bash
# Exit 0: stages assessed successfully; 1: operational/evidence failure; 2: invalid use.
set -u
if [[ $# -ne 1 ]]; then echo "usage: bash workflows/create_series.sh RUN_DIR" >&2; exit 2; fi
ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
RUN_DIR=$1
PYTHON="$ROOT_DIR/.venv/bin/python"; [[ -x "$PYTHON" ]] || PYTHON=python3.12
cd "$ROOT_DIR" || exit 1
if [[ ! -f "$RUN_DIR/run.json" ]]; then echo "invalid run directory: $RUN_DIR" >&2; exit 2; fi
# shellcheck disable=SC2329  # Invoked by the EXIT trap.
finish_receipt() { code=$?; trap - EXIT; "$PYTHON" -m src.receipt_cli "$RUN_DIR" create_series_workflow "$code" >/dev/null 2>&1 || true; exit "$code"; }
trap finish_receipt EXIT

bash editorial/select_items.sh "$RUN_DIR" < "$RUN_DIR/eligible.jsonl" > "$RUN_DIR/decisions.jsonl" || exit $?
bash editorial/create_briefs.sh "$RUN_DIR" < "$RUN_DIR/decisions.jsonl" > "$RUN_DIR/briefs.jsonl" || exit $?
bash content/write_articles.sh "$RUN_DIR" < "$RUN_DIR/briefs.jsonl" > "$RUN_DIR/articles.jsonl" || exit $?
bash content/write_video_scripts.sh "$RUN_DIR" < "$RUN_DIR/briefs.jsonl" > "$RUN_DIR/video_scripts.jsonl" || exit $?
bash review/check_content.sh "$RUN_DIR" > "$RUN_DIR/review.json" || exit $?
exit 0
