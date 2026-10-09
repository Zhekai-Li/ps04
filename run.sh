#!/usr/bin/env bash
# Exit 0: run reached awaiting_review/ready_for_production; 1: failed; 2: invalid use.
set -u
ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PYTHON="$ROOT_DIR/.venv/bin/python"; [[ -x "$PYTHON" ]] || PYTHON=python3.12
cd "$ROOT_DIR" || exit 1
# shellcheck source=scripts/lib/ui.sh
source "$ROOT_DIR/scripts/lib/ui.sh"

summarize_and_exit() {
  local target=$1
  local tmp_summary="$target/summary.json.tmp"
  if bash reporting/summarize_run.sh "$target" > "$tmp_summary"; then
    mv "$tmp_summary" "$target/summary.json"
    cat "$target/summary.json"
    if [[ $(jq -r '.status' "$target/summary.json") == "failed" ]]; then return 1; fi
    return 0
  fi
  rm -f "$tmp_summary"
  return 1
}

if [[ $# -eq 2 && $1 == "--package" ]]; then
  RUN_DIR=$2
  if [[ ! -f "$RUN_DIR/run.json" ]]; then echo "invalid run directory: $RUN_DIR" >&2; exit 2; fi
  # shellcheck disable=SC2329  # Invoked by the EXIT trap.
  finish_run_receipt() { code=$?; trap - EXIT; "$PYTHON" -m src.receipt_cli "$RUN_DIR" run_package "$code" >/dev/null 2>&1 || true; exit "$code"; }
  trap finish_run_receipt EXIT
  ps04_banner "SCHOLAR IN THE LOOP · PACKAGE"
  ps04_info "Run directory: $RUN_DIR"
  ps04_info "Progress is printed to stderr; manifest JSON remains on stdout."
  review_tmp="$RUN_DIR/review.json.tmp"
  ps04_step 1 3 "Rechecking reviewed content" "Recomputes the fingerprint and verifies every evidence locator."
  if ! bash review/check_content.sh "$RUN_DIR" > "$review_tmp"; then rm -f "$review_tmp"; summarize_and_exit "$RUN_DIR"; exit 1; fi
  mv "$review_tmp" "$RUN_DIR/review.json"
  ps04_ok "Content check completed"
  ps04_step 2 3 "Verifying human approval and building package" "Approval must match the current review_id."
  set +e
  bash publishing/prepare_package.sh "$RUN_DIR" > "$RUN_DIR/package-manifest-output.json"
  package_code=$?
  if [[ $package_code -eq 0 ]]; then ps04_ok "Production package created"; else ps04_fail "Packaging failed; inspect the diagnostic above"; fi
  ps04_step 3 3 "Refreshing summary" "Reports readiness and remaining manual publishing steps."
  summarize_and_exit "$RUN_DIR"
  summary_code=$?
  [[ $package_code -eq 0 && $summary_code -eq 0 ]] && exit 0
  exit 1
fi

if [[ $# -ne 0 ]]; then echo "usage: bash run.sh | bash run.sh --package runs/RUN_ID" >&2; exit 2; fi
if [[ -n ${PS04_MOCK_RESPONSES_DIR:-} ]]; then echo "mock responses are forbidden in a live run; use scripts/replay_run.sh" >&2; exit 2; fi
if [[ -z ${OPENAI_API_KEY:-} ]]; then echo "OPENAI_API_KEY is required for a live run; see docs/account_setup.md" >&2; exit 2; fi

if ! "$PYTHON" -m src.run_setup validate; then exit 2; fi
RUN_DIR=$("$PYTHON" -m src.run_setup create live) || exit $?
# shellcheck disable=SC2329  # Invoked by the EXIT trap.
finish_run_receipt() { code=$?; trap - EXIT; "$PYTHON" -m src.receipt_cli "$RUN_DIR" run "$code" >/dev/null 2>&1 || true; exit "$code"; }
trap finish_run_receipt EXIT
ps04_banner "SCHOLAR IN THE LOOP · LIVE RUN"
ps04_info "Run directory: $RUN_DIR"
ps04_info "Progress and explanations → stderr; final summary JSON → stdout."
ps04_warn "Typical time: 5–15 min with cached/public transcripts; 20–60+ min when audio needs Whisper transcription."
ps04_info "Safe to stop with Ctrl-C. Completed assets are cached; extraction records now flush item by item."

ps04_step 1 4 "Initialize evidence store" "Creates missing SQLite tables without erasing prior evidence."
bash data/store.sh init || { summarize_and_exit "$RUN_DIR"; exit 1; }
ps04_ok "Evidence store ready"

set +e
ps04_step 2 4 "Collect and normalize evidence" "RSS, YouTube, podcasts → text/captions/transcripts → versioned store → 30-day filter."
bash workflows/collect_sources.sh "$RUN_DIR"
collection_code=$?
if [[ $collection_code -eq 0 ]]; then ps04_ok "Collection workflow completed"; else ps04_warn "Collection was partial; usable evidence was preserved"; fi
ps04_step 3 4 "Create the three-piece series" "AI selection, evidence-grounded briefs, articles, scripts, and deterministic checks."
bash workflows/create_series.sh "$RUN_DIR"
series_code=$?
if [[ $series_code -eq 0 ]]; then ps04_ok "Series drafts and review completed"; else ps04_fail "Series workflow stopped; inspect the last stage diagnostic"; fi

ps04_step 4 4 "Write run summary" "Counts evidence, coverage, failures, models, cost, and next human action."
summarize_and_exit "$RUN_DIR"
summary_code=$?
if [[ $series_code -ne 0 || $summary_code -ne 0 ]]; then exit 1; fi
# A partial collector result remains visible in receipts and summary but does not erase usable evidence.
[[ $collection_code -eq 0 ]] || echo "run.sh: collection was incomplete; inspect summary and receipts" >&2
exit 0
