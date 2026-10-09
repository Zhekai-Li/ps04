#!/usr/bin/env bash
# Exit 0: complete; 1: partial/operational failure with artifacts preserved; 2: invalid use.
set -u
if [[ $# -ne 1 ]]; then echo "usage: bash workflows/collect_sources.sh RUN_DIR" >&2; exit 2; fi
ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
RUN_DIR=$1
PYTHON="$ROOT_DIR/.venv/bin/python"; [[ -x "$PYTHON" ]] || PYTHON=python3.12
cd "$ROOT_DIR" || exit 1
if [[ ! -f "$RUN_DIR/run.json" ]]; then echo "invalid run directory: $RUN_DIR" >&2; exit 2; fi
# shellcheck disable=SC2329  # Invoked by the EXIT trap.
finish_receipt() { code=$?; trap - EXIT; "$PYTHON" -m src.receipt_cli "$RUN_DIR" collect_sources_workflow "$code" >/dev/null 2>&1 || true; exit "$code"; }
trap finish_receipt EXIT

overall=0
for kind in feeds youtube podcasts; do
  set +e
  bash "collectors/fetch_${kind}.sh" "$RUN_DIR" > "$RUN_DIR/candidates/${kind}.jsonl"
  code=$?
  if [[ $code -ne 0 ]]; then overall=1; fi
done

: > "$RUN_DIR/candidates.jsonl"
for path in "$RUN_DIR/candidates/feeds.jsonl" "$RUN_DIR/candidates/youtube.jsonl" "$RUN_DIR/candidates/podcasts.jsonl"; do
  [[ -f "$path" ]] && sed '/^[[:space:]]*$/d' "$path" >> "$RUN_DIR/candidates.jsonl"
done

set +e
sed '/^[[:space:]]*$/d' "$RUN_DIR/candidates.jsonl" | bash processing/extract_content.sh "$RUN_DIR" > "$RUN_DIR/items.jsonl"
extract_code=$?
if [[ $extract_code -ne 0 ]]; then overall=1; fi

if ! bash data/store.sh upsert "$RUN_DIR" < "$RUN_DIR/items.jsonl" > "$RUN_DIR/changes.jsonl"; then exit 1; fi
if ! bash data/store.sh list > "$RUN_DIR/corpus.jsonl"; then exit 1; fi
if ! bash processing/filter_items.sh "$RUN_DIR" < "$RUN_DIR/corpus.jsonl" > "$RUN_DIR/eligible.jsonl"; then exit 1; fi
exit "$overall"
