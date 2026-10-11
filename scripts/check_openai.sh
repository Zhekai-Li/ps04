#!/usr/bin/env bash
# Backward-compatible alias. The default pipeline no longer requires an API key.
set -u
ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
echo "scripts/check_openai.sh is deprecated; checking Codex + MLX backends" >&2
exec bash "$ROOT_DIR/scripts/check_backends.sh" "$@"
