#!/usr/bin/env bash
# Validate the default ChatGPT-plan Codex and local MLX backends without exposing credentials.
set -u
ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
PYTHON="$ROOT_DIR/.venv/bin/python"; [[ -x "$PYTHON" ]] || PYTHON=python3.12
DOWNLOAD=0
PROBE=1
for argument in "$@"; do
  case "$argument" in
    --download) DOWNLOAD=1 ;;
    --no-model-probe) PROBE=0 ;;
    *) echo "usage: bash scripts/check_backends.sh [--download] [--no-model-probe]" >&2; exit 2 ;;
  esac
done
cd "$ROOT_DIR" || exit 1
"$PYTHON" -m src.run_setup validate || exit 2
command -v codex >/dev/null || { echo "codex CLI is not installed" >&2; exit 1; }
command -v ffmpeg >/dev/null || { echo "ffmpeg is not installed" >&2; exit 1; }
command -v ffprobe >/dev/null || { echo "ffprobe is not installed" >&2; exit 1; }
codex login status >/dev/null || { echo "Codex is not logged in with ChatGPT" >&2; exit 1; }
"$PYTHON" -c 'import mlx_whisper' || { echo "mlx-whisper is not installed; run bash scripts/setup.sh" >&2; exit 1; }

MODEL=$(jq -r '.editorial_model' config/models.json)
EFFORT=$(jq -r '.reasoning_effort' config/models.json)
TRANSCRIPTION_MODEL=$(jq -r '.transcription_model' config/models.json)
if [[ $DOWNLOAD -eq 1 ]]; then
  "$PYTHON" - "$TRANSCRIPTION_MODEL" <<'PY'
import sys
from huggingface_hub import snapshot_download
path = snapshot_download(sys.argv[1])
print(f"MLX model cached at {path}")
PY
fi
"$PYTHON" - "$TRANSCRIPTION_MODEL" <<'PY'
import sys
from huggingface_hub import scan_cache_dir
repo = sys.argv[1]
matches = [item for item in scan_cache_dir().repos if item.repo_id == repo]
if not matches:
    raise SystemExit(f"MLX model is not cached: {repo}; rerun with --download")
print(f"MLX model cache ready: {repo} ({next(iter(matches[0].revisions)).commit_hash})")
PY

if [[ $PROBE -eq 1 ]]; then
  CHECK_TMP=$(mktemp -d "${TMPDIR:-/tmp}/ps04-backends.XXXXXX") || exit 1
  trap 'rm -rf -- "$CHECK_TMP"' EXIT
  printf '%s\n' '{"type":"object","properties":{"ok":{"type":"boolean"}},"required":["ok"],"additionalProperties":false}' > "$CHECK_TMP/schema.json"
  if ! printf '%s\n' 'Return {"ok":true}. Do not call tools.' | codex --ask-for-approval never exec \
      --ephemeral --ignore-user-config --ignore-rules --model "$MODEL" --sandbox read-only \
      --skip-git-repo-check --config "model_reasoning_effort=\"$EFFORT\"" \
      --output-schema "$CHECK_TMP/schema.json" --output-last-message "$CHECK_TMP/response.json" --json - \
      > "$CHECK_TMP/events.jsonl" 2> "$CHECK_TMP/stderr.log"; then
    tail -n 3 "$CHECK_TMP/stderr.log" >&2
    echo "Codex model probe failed for $MODEL" >&2
    exit 1
  fi
  jq -e '.ok == true' "$CHECK_TMP/response.json" >/dev/null || { echo "Codex model probe returned invalid output" >&2; exit 1; }
fi
echo "Backends ready: $(codex --version); model=$MODEL effort=$EFFORT; transcription=$TRANSCRIPTION_MODEL; ffmpeg=$(ffmpeg -version | sed -n '1s/ .*//p')"
if [[ ${PS04_ALLOW_PAID_FALLBACK:-0} == 1 ]]; then
  [[ -n ${OPENAI_API_KEY:-} ]] || { echo "PS04_ALLOW_PAID_FALLBACK=1 but OPENAI_API_KEY is absent" >&2; exit 2; }
  echo "WARNING: paid API fallback is enabled for this process" >&2
fi
