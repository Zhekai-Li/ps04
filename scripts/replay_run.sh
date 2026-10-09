#!/usr/bin/env bash
# Replays retained candidates. This is always mode=replay and never counts as a live run.
set -u
if [[ $# -lt 1 || $# -gt 2 ]]; then echo "usage: bash scripts/replay_run.sh SOURCE_RUN_DIR [WITHHELD_CANDIDATES.jsonl]" >&2; exit 2; fi
ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
PYTHON="$ROOT_DIR/.venv/bin/python"; [[ -x "$PYTHON" ]] || PYTHON=python3.12
cd "$ROOT_DIR" || exit 1
SOURCE_RUN=$1
[[ -f "$SOURCE_RUN/run.json" && -f "$SOURCE_RUN/candidates.jsonl" ]] || { echo "source run is missing run.json or candidates.jsonl" >&2; exit 2; }
AS_OF=$(jq -r '.as_of_date' "$SOURCE_RUN/run.json")
RUN_DIR=$("$PYTHON" -m src.run_setup create replay --as-of-date "$AS_OF") || exit $?
cp "$SOURCE_RUN"/config/* "$RUN_DIR/config/"
cp "$SOURCE_RUN"/prompts/* "$RUN_DIR/prompts/"
cp "$SOURCE_RUN/candidates.jsonl" "$RUN_DIR/candidates.jsonl"
if [[ $# -eq 2 ]]; then sed '/^[[:space:]]*$/d' "$2" >> "$RUN_DIR/candidates.jsonl"; fi
bash data/store.sh init || exit 1
overall=0
sed '/^[[:space:]]*$/d' "$RUN_DIR/candidates.jsonl" | bash processing/extract_content.sh "$RUN_DIR" > "$RUN_DIR/items.jsonl" || overall=1
bash data/store.sh upsert "$RUN_DIR" < "$RUN_DIR/items.jsonl" > "$RUN_DIR/changes.jsonl" || exit 1
bash data/store.sh list > "$RUN_DIR/corpus.jsonl" || exit 1
bash processing/filter_items.sh "$RUN_DIR" < "$RUN_DIR/corpus.jsonl" > "$RUN_DIR/eligible.jsonl" || exit 1
bash workflows/create_series.sh "$RUN_DIR" || overall=1
bash reporting/summarize_run.sh "$RUN_DIR" > "$RUN_DIR/summary.json"
cat "$RUN_DIR/summary.json"
exit "$overall"
