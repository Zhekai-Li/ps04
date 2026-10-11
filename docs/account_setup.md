# Account and local-backend setup checklist

Complete these steps personally before the first live run.

1. Install the Codex CLI, run `codex login`, and choose ChatGPT authentication. The default pipeline uses the existing ChatGPT/Codex plan allowance, not API-token billing.
2. Run `bash scripts/setup.sh` on the Apple Silicon Mac. This installs the pinned `mlx-whisper==0.4.3` environment.
3. Run `bash scripts/check_backends.sh --download`. It verifies the Codex login and configured `gpt-5.6-sol` model, checks FFmpeg and MLX, and downloads `mlx-community/whisper-turbo` on first use.
4. Leave `PS04_ALLOW_PAID_FALLBACK` unset for normal runs. The presence of `OPENAI_API_KEY` alone never enables a paid call.
5. Only for a deliberately authorized one-run fallback, set both `PS04_ALLOW_PAID_FALLBACK=1` and `OPENAI_API_KEY`. The run records that choice in `run.json` and receipts.
6. Create or verify the **Scholar in the Loop** Substack publication and confirm posts can be read without a paid subscription.
7. Create or verify the YouTube channel and set each of the four assignment uploads to **Unlisted**.
8. Verify Google Vids access for the three audience-facing videos, then test all final links in a signed-out/private browser window.

Never paste credentials into chat, configuration, screenshots, logs, or Git. Supported environment variables are optional `PS04_ALLOW_PAID_FALLBACK`, optional `OPENAI_API_KEY` for that explicit fallback, test-only `PS04_MOCK_RESPONSES_DIR` and `PS04_EVIDENCE_DIR`, and failure-demo `PS04_FAIL_COLLECTOR`.
