#!/usr/bin/env bash
# Exit 0: complete; 1: partial/operational failure with artifacts preserved; 2: invalid use.
set -u
if [[ $# -ne 1 ]]; then echo "usage: bash workflows/collect_sources.sh RUN_DIR" >&2; exit 2; fi
ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
RUN_DIR=$1
PYTHON="$ROOT_DIR/.venv/bin/python"; [[ -x "$PYTHON" ]] || PYTHON=python3.12
cd "$ROOT_DIR" || exit 1
if [[ ! -f "$RUN_DIR/run.json" ]]; then echo "invalid run directory: $RUN_DIR" >&2; exit 2; fi
# shellcheck source=scripts/lib/ui.sh
source "$ROOT_DIR/scripts/lib/ui.sh"
# shellcheck disable=SC2329  # Invoked by the EXIT trap.
finish_receipt() { code=$?; trap - EXIT; "$PYTHON" -m src.receipt_cli "$RUN_DIR" collect_sources_workflow "$code" >/dev/null 2>&1 || true; exit "$code"; }
trap finish_receipt EXIT

overall=0
collector_index=0
for kind in feeds youtube podcasts; do
  collector_index=$((collector_index + 1))
  case "$kind" in
    feeds) label="Discover RSS articles"; detail="Fetch configured feeds and publication metadata." ;;
    youtube) label="Discover YouTube videos"; detail="Resolve each selected video's real upload date; usually the slowest collector." ;;
    podcasts) label="Discover podcast episodes"; detail="Preserve episode, enclosure, and transcript locations." ;;
  esac
  ps04_step "$collector_index" 7 "$label" "$detail"
  set +e
  bash "collectors/fetch_${kind}.sh" "$RUN_DIR" > "$RUN_DIR/candidates/${kind}.jsonl"
  code=$?
  count=$(ps04_file_count "$RUN_DIR/candidates/${kind}.jsonl")
  if [[ $code -ne 0 ]]; then overall=1; ps04_warn "$kind collector returned $code with $count usable records"; else ps04_ok "$count records discovered"; fi
done

: > "$RUN_DIR/candidates.jsonl"
for path in "$RUN_DIR/candidates/feeds.jsonl" "$RUN_DIR/candidates/youtube.jsonl" "$RUN_DIR/candidates/podcasts.jsonl"; do
  [[ -f "$path" ]] && sed '/^[[:space:]]*$/d' "$path" >> "$RUN_DIR/candidates.jsonl"
done

candidate_count=$(ps04_file_count "$RUN_DIR/candidates.jsonl")
ps04_step 4 7 "Extract substantive evidence" "$candidate_count candidates. Articles use conditional HTTP; media uses cached/public transcripts first, then Whisper when necessary."
set +e
sed '/^[[:space:]]*$/d' "$RUN_DIR/candidates.jsonl" | bash processing/extract_content.sh "$RUN_DIR" > "$RUN_DIR/items.jsonl"
extract_code=$?
item_count=$(ps04_file_count "$RUN_DIR/items.jsonl")
if [[ $extract_code -ne 0 ]]; then overall=1; ps04_warn "Extraction was partial: $item_count items preserved"; else ps04_ok "$item_count evidence items extracted"; fi

ps04_step 5 7 "Upsert evidence versions" "Classifies each item as new, changed, or unchanged."
if ! bash data/store.sh upsert "$RUN_DIR" < "$RUN_DIR/items.jsonl" > "$RUN_DIR/changes.jsonl"; then exit 1; fi
new_count=$(jq -r 'select(.change == "new") | .item_id' "$RUN_DIR/changes.jsonl" | wc -l | tr -d ' ')
changed_count=$(jq -r 'select(.change == "changed") | .item_id' "$RUN_DIR/changes.jsonl" | wc -l | tr -d ' ')
unchanged_count=$(jq -r 'select(.change == "unchanged") | .item_id' "$RUN_DIR/changes.jsonl" | wc -l | tr -d ' ')
ps04_ok "new=$new_count · changed=$changed_count · unchanged=$unchanged_count"

ps04_step 6 7 "Export latest evidence corpus" "Historical versions remain available through data/store.sh get."
if ! bash data/store.sh list > "$RUN_DIR/corpus.jsonl"; then exit 1; fi
ps04_ok "$(ps04_file_count "$RUN_DIR/corpus.jsonl") latest item versions exported"

ps04_step 7 7 "Apply the inclusive 30-day window" "Keeps D−29 through D and records a reason for every exclusion."
if ! bash processing/filter_items.sh "$RUN_DIR" < "$RUN_DIR/corpus.jsonl" > "$RUN_DIR/eligible.jsonl"; then exit 1; fi
ps04_ok "eligible=$(ps04_file_count "$RUN_DIR/eligible.jsonl") · excluded=$(ps04_file_count "$RUN_DIR/exclusions.jsonl")"
exit "$overall"
