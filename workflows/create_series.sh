#!/usr/bin/env bash
# Exit 0: stages assessed successfully; 1: operational/evidence failure; 2: invalid use.
set -u
if [[ $# -ne 1 ]]; then echo "usage: bash workflows/create_series.sh RUN_DIR" >&2; exit 2; fi
ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
RUN_DIR=$1
PYTHON="$ROOT_DIR/.venv/bin/python"; [[ -x "$PYTHON" ]] || PYTHON=python3.12
cd "$ROOT_DIR" || exit 1
if [[ ! -f "$RUN_DIR/run.json" ]]; then echo "invalid run directory: $RUN_DIR" >&2; exit 2; fi
# shellcheck source=scripts/lib/ui.sh
source "$ROOT_DIR/scripts/lib/ui.sh"
# shellcheck disable=SC2329  # Invoked by the EXIT trap.
finish_receipt() { code=$?; trap - EXIT; "$PYTHON" -m src.receipt_cli "$RUN_DIR" create_series_workflow "$code" >/dev/null 2>&1 || true; exit "$code"; }
trap finish_receipt EXIT

ps04_step 1 5 "Editorial selection" "The model must decide accept/reject/defer for every eligible evidence version."
bash editorial/select_items.sh "$RUN_DIR" < "$RUN_DIR/eligible.jsonl" > "$RUN_DIR/decisions.jsonl" || exit $?
ps04_ok "$(ps04_file_count "$RUN_DIR/decisions.jsonl") structured decisions saved"

ps04_step 2 5 "Build three editorial briefs" "Each argument needs at least three independent publishers and exact evidence locators."
bash editorial/create_briefs.sh "$RUN_DIR" < "$RUN_DIR/decisions.jsonl" > "$RUN_DIR/briefs.jsonl" || exit $?
ps04_ok "Three briefs saved"

ps04_step 3 5 "Draft three articles" "Targets 600–900 words and preserves claim markers."
bash content/write_articles.sh "$RUN_DIR" < "$RUN_DIR/briefs.jsonl" > "$RUN_DIR/articles.jsonl" || exit $?
ps04_ok "Three article drafts saved"

ps04_step 4 5 "Draft three video scripts" "Targets 3–5 minutes and uses the same claims as each article."
bash content/write_video_scripts.sh "$RUN_DIR" < "$RUN_DIR/briefs.jsonl" > "$RUN_DIR/video_scripts.jsonl" || exit $?
ps04_ok "Three video scripts saved"

ps04_step 5 5 "Check evidence and consistency" "Verifies dates, coverage, quotes, segment IDs, claim markers, and length warnings."
bash review/check_content.sh "$RUN_DIR" > "$RUN_DIR/review.json" || exit $?
if [[ $(jq -r '.passed' "$RUN_DIR/review.json") == true ]]; then ps04_ok "Automated review passed; human review is next"; else ps04_warn "Automated review found blocking issues"; fi
exit 0
