# Account setup checklist

Complete these steps personally before the first live run.

1. Create or verify an OpenAI Platform account, a billed project, and a project-scoped API key.
2. Store the secret only in the local `OPENAI_API_KEY` environment variable. Do not paste it into chat, configuration, screenshots, logs, or Git.
3. Run `bash scripts/check_openai.sh`. It lists models to verify authentication but never prints the key.
4. Create or verify the **Scholar in the Loop** Substack publication and confirm posts can be read without a paid subscription.
5. Create or verify the YouTube channel and set each of the four assignment uploads to **Unlisted**.
6. Verify Google Vids access for the three audience-facing videos.
7. Test all final links in a signed-out/private browser window.

Only these environment-variable names are part of the repository: `OPENAI_API_KEY`, optional test-only `PS04_MOCK_RESPONSES_DIR`, optional test-only `PS04_EVIDENCE_DIR`, and failure-demo `PS04_FAIL_COLLECTOR`.

