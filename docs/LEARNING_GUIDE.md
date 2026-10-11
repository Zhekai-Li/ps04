# Scholar in the Loop: learning and operations guide

## Purpose

Scholar in the Loop is a repeatable evidence-to-publication pipeline for AI and operations-research PhD students. It asks which uses of AI in topic selection and academic writing save time without weakening originality, evidence, author responsibility, or scholarly value. The system automates collection, mechanical checks, model-assisted editorial work, and draft generation. It deliberately stops before approval and publication.

The official contracts remain in `README.md` and `ARCHITECTURE.md`. This guide explains this implementation.

## Data flow and responsibility boundaries

```mermaid
flowchart TD
    R[run.sh: create immutable run context] --> C[collect_sources.sh]
    C --> F[RSS collector]
    C --> Y[YouTube collector]
    C --> P[Podcast collector]
    F & Y & P --> E[extract_content.sh]
    E -->|items JSONL| D[data/store.sh: SQLite versions]
    D -->|latest corpus JSONL| W[filter_items.sh: D-29 through D]
    W --> S[select_items.sh: read-only Codex CLI]
    S --> B[create_briefs.sh: read-only Codex CLI]
    B --> A[write_articles.sh]
    B --> V[write_video_scripts.sh]
    A & V --> K[check_content.sh]
    K --> H{Zhekai reviews and approves}
    H -->|matching approval.json| X[prepare_package.sh]
    X --> M[Google Vids, Substack, YouTube manual handoff]
```

Only `data/store.sh` and its `src.store` implementation access `data/evidence/`. Other stages use JSONL streams, retained assets, or the store command interface. This makes a component independently runnable and prevents editorial code from silently changing persistence semantics.

Every stage reserves stdout for its record stream or JSON document and sends diagnostics to stderr. Exit `0` means the stage completed, `1` means an operational or partial failure, and `2` means invalid arguments, configuration, or input. Each invocation preserves a uniquely named receipt under the run’s `logs/` directory; store commands without a run context use `data/evidence/receipts/`.

## The 16 required components

| Component | What it owns |
| --- | --- |
| `run.sh` | Run metadata, snapshots, workflow order, final summary, and package mode. |
| `workflows/collect_sources.sh` | Collector coordination, partial-failure handling, extraction, storage, export, and filtering. |
| `workflows/create_series.sh` | Selection, briefs, both content forms, and checks. |
| `collectors/fetch_feeds.sh` | RSS/Atom discovery for substantive written sources. |
| `collectors/fetch_youtube.sh` | YouTube channel/playlist/video discovery through `yt-dlp`. |
| `collectors/fetch_podcasts.sh` | Podcast feed discovery, enclosure URLs, and publisher transcript links. |
| `processing/extract_content.sh` | Article extraction, captions/transcripts, immutable assets, and deterministic evidence versions. |
| `processing/filter_items.sh` | The inclusive UTC publication-date window and four exclusion reasons. |
| `data/store.sh` | SQLite initialization, ordered upserts, latest export, historical retrieval, and observations. |
| `editorial/select_items.sh` | Policy-constrained accept/reject/defer decisions. |
| `editorial/create_briefs.sh` | Three supported arguments, claims, synthesis, and limitations. |
| `content/write_articles.sh` | Three article Markdown files and a JSONL manifest. |
| `content/write_video_scripts.sh` | Three script Markdown files and a JSONL manifest. |
| `review/check_content.sh` | Deterministic evidence, coverage, date, length, and consistency checks. |
| `publishing/prepare_package.sh` | Current-review and human-approval gate plus production assets. |
| `reporting/summarize_run.sh` | Counts, coverage, failures, tools/models, costs, status, and manual work. |

Focused Python modules under `src/` implement the substantive behavior. The Bash files remain the public interface and orchestration layer.

## Records and identities

All streams are JSON Lines: one object per line.

- A **candidate** is a discovery observation. Required fields are `item_id`, `source_id`, `publisher_id`, `kind`, `title`, `url`, `published_at`, `retrieved_at`, and `media_url`.
- An **item** adds `version_id`, `text_path`, and `segments_path`. It points to retained evidence.
- A **version** is a deterministic hash of evidence-relevant metadata, normalized text, and transcript segments. Retrieval time and local asset paths are excluded.
- A **segment** has `segment_id`, numeric `start_seconds`, numeric `end_seconds`, and `text`.
- A **decision** records one eligible version’s `accept`, `reject`, or `defer` result, its reason, and assigned piece IDs.
- A **brief** has one piece ID, title, question, argument, synthesis, limitations, and typed claims.
- A **claim** is a `reported_fact`, `source_claim`, or `inference`; it has one or more exact evidence references.
- A **manifest** maps one piece ID to a Markdown path and its ordered claim IDs.

Written locators contain an exact quote. Media locators contain an exact segment ID. A title, general URL, or model recollection is not a locator.

`item_id` is stable: native YouTube/feed identifiers are preferred, otherwise a normalized canonical-URL hash is used. Tracking parameters and URL fragments are removed. `underlying_id`, publisher IDs, and per-source identity overrides prevent syndication and podcast/video copies from inflating independence. A repeated observation creates an observation row but not a new version. A new substantive version is retained beside every older version.

## Collection, extraction, and freshness

RSS and podcast feeds are parsed with `feedparser`; YouTube endpoints are enumerated with `yt-dlp`. A successful search with zero entries exits `0`. A network or deliberately simulated collector failure exits `1`, writes a failed receipt, and may still leave valid records. The collection workflow continues with usable sources and reports incomplete coverage.

Articles use conditional HTTP headers when cached validators are available. `trafilatura` extracts substantive text, with a cached copy or substantive feed summary as a documented fallback. YouTube captions are preferred, followed by publisher timestamped podcast transcripts. If neither exists, media is retained under ignored `data/media/` and transcribed locally on Apple Silicon with `mlx-whisper==0.4.3` and `mlx-community/whisper-turbo`. The call requests word timestamps and groups them deterministically into roughly 12-second global-time segments. The cache identity includes the media, backend, model, and model revision, so a model change does not silently reuse incompatible output.

The default path never calls a paid transcription API, even when `OPENAI_API_KEY` happens to exist. Only a run that explicitly sets `PS04_ALLOW_PAID_FALLBACK=1` may use the paid fallback. That fallback compresses and divides oversized media into overlapping chunks, transcribes each chunk, restores global times, and removes overlap duplicates.

For an as-of date `D`, eligibility includes dates from `D−29` through `D`, inclusive. Filtering emits one of four reasons:

- `outside_window`: earlier than `D−29`;
- `unknown_date`: absent publication date;
- `future_date`: later than `D`;
- `invalid_date`: present but unparsable.

Collection time is never substituted for publication time. Previously stored material is re-evaluated against each new run date.

## Constrained model calls

The four text stages run non-interactively through the locally authenticated Codex CLI. The snapshotted configuration fixes `gpt-5.6-sol` with `high` reasoning effort. Every call uses an isolated temporary directory, read-only sandboxing, no search, no repository rule loading, and a JSON Schema passed through `--output-schema`; the final structured response is captured with `--output-last-message`. OpenAI's official Codex example documents this machine-readable `codex exec` pattern. The project then validates the response again with Pydantic and its own semantic rules. Selection must cover every eligible version exactly once. Briefs must be `01`, `02`, and `03`; claim IDs must match `^(01|02|03)-c[1-9][0-9]*$` and be globally unique; and each piece must use at least three accepted independent publishers. Content must preserve every brief claim marker.

Model input is bounded without breaking traceability. Article evidence is capped at 14,000 characters. Short media transcripts are supplied in full; long media input contains the opening, ending, evenly distributed, and question-relevant segments, capped at 120 segments and 30,000 serialized characters, with an excerpt manifest retained under `logs/excerpt_manifests/`. Writing stages receive only the evidence actually cited by the brief plus adjacent context.

Malformed JSON, schema failures, and semantic failures receive at most one repair retry, then fail explicitly. A response that attempts a command, tool call, or external lookup is rejected. Each attempt retains the prompt, schema, final response, sanitized lifecycle events, validation errors, CLI version, model, reasoning effort, elapsed time, response ID when available, and usage when reported. Hidden reasoning and authentication material are never stored. `PS04_MOCK_RESPONSES_DIR` is available only for labeled offline tests and replays; its receipts say `provider: mock`. A replay is never a live run.

Codex receipts use `billing_mode: chatgpt_plan` and `cost_usd: null`: plan consumption cannot be converted reliably into a per-call dollar amount. Local MLX receipts use `billing_mode: local_compute` and record audio duration, elapsed compute time, and model revision. The normal summary therefore reports `incremental_api_cost_usd: 0.0` without falsely claiming that a Codex call itself cost `$0`. A deliberately enabled paid fallback is itemized separately. Official references: [Codex CLI JSON-Schema execution](https://developers.openai.com/cookbook/examples/codex/build_iterative_repair_loops_with_codex) and [GPT-5.6 Sol model capabilities](https://developers.openai.com/api/docs/models/gpt-5.6-sol).

## One evidence trace

The inspectable chain is:

```text
candidates/<kind>.jsonl
  → candidates.jsonl
  → items.jsonl + data/assets/...
  → changes.jsonl + data/evidence/evidence.db
  → eligible.jsonl
  → decisions.jsonl
  → briefs.jsonl claim.evidence[]
  → articles/NN.md and video_scripts/NN.md claim marker
  → review.json review_id
  → approval.json
  → package/source_notes/NN.md
```

For a written claim, copy the exact quote from `briefs.jsonl`, retrieve its historical record with `bash data/store.sh get ITEM_ID VERSION_ID`, and find that exact string in `text_path`. For media, resolve the segment ID in `segments_path`, then use its numeric start/end times in the reader-facing source note.

## Setup and live execution

Requirements are Python 3.12, Bash, SQLite, `jq`, Git, `ffmpeg`, and `shellcheck`. Install the pinned Python environment:

```bash
bash scripts/setup.sh
```

Sign in to Codex with the ChatGPT account used for this project, then run the backend preflight. The download flag also primes the local MLX model cache:

```bash
codex login
bash scripts/check_backends.sh --download
```

No API key is required for the default path. Leave `PS04_ALLOW_PAID_FALLBACK` unset. For a deliberately authorized one-run paid fallback only, set both `PS04_ALLOW_PAID_FALLBACK=1` and `OPENAI_API_KEY`; that choice is recorded in run metadata and receipts.

Before a live run, verify the Substack publication, YouTube channel, and Google Vids access; configure articles for free access and videos as Unlisted. Audit `config/sources.json` against the prior 30 days and replace inaccessible or irrelevant endpoints while preserving publisher identity judgments.

Run:

```bash
bash run.sh
```

The terminal shows a numbered progress view: the current collector or candidate, completed counts, cache hits, model-call waits, and the purpose of each stage. Human-readable progress goes to stderr, while the final JSON summary stays clean on stdout and is also saved in the new run. Set `PS04_PROGRESS=0` only when a machine-readable, quiet invocation is needed.

A cached run commonly takes 5–15 minutes. A fresh run can take 20–60 minutes or longer when long podcast or YouTube audio must be downloaded and transcribed. Public captions and publisher transcripts are much faster. Extraction writes each completed item immediately, so `Ctrl-C` preserves finished records and downloaded/transcribed assets; a later run reuses those caches. The incomplete run itself does not count as one of the two required live runs.

A valid complete run stops at `awaiting_review`. To replay a saved candidate set without counting it as live:

```bash
bash scripts/replay_run.sh runs/LIVE_RUN_ID
bash scripts/replay_run.sh runs/LIVE_RUN_ID path/to/withheld-candidates.jsonl
```

To demonstrate a labeled collector failure:

```bash
bash scripts/demonstrate_failure.sh youtube
```

## Human review, revision, and approval

After live run one, inspect at least three accepted and three rejected/deferred decisions and complete `docs/editorial_review.md`. Compare the model reason with your own evidence-specific judgment. Copy the first run’s policy snapshot into the review record, revise `config/editorial_policy.md`, and run the affected stages in a new run so both outputs remain inspectable. Record every factual correction, its old/new wording, evidence, and reason.

When `review.json` passes, read the actual evidence, briefs, articles, and scripts. Only Zhekai Li may create `approval.json`:

```json
{
  "review_id": "COPY_FROM_CURRENT_REVIEW",
  "decision": "approve",
  "reviewer": "Zhekai Li",
  "reviewed_at": "ACTUAL_UTC_TIMESTAMP",
  "notes": "Corrections made and remaining uncertainties reviewed."
}
```

Then run:

```bash
bash run.sh --package runs/RUN_ID
```

Packaging recomputes the review fingerprint. Missing, stale, or non-approving decisions fail. It never recollects or regenerates approved content.

## Production and publication

The package contains articles, scripts, per-piece source notes, a manifest, production instructions, and `publication_links.json`. Use each script to create a 3–5 minute video in Google Vids, include an AI-presentation disclosure and source slate, publish the corresponding article free on Substack, upload the video Unlisted to YouTube, and cross-link them. Keep large rendered files out of Git. Verify every URL while signed out, then fill only the null URL values. Repackaging preserves filled links.

Record a separate 4–6 minute technical demonstration using `docs/technical_demo_script.md`.

## Diagnosis and security

- Read the latest stage receipt in `RUN_DIR/logs/`; it distinguishes invalid input, empty success, incomplete work, and failure.
- If extraction fails, check the retained candidate, URL access, captions, transcript availability, local MLX installation/model cache, available disk space, and `ffmpeg`. Check an API key only when the paid fallback was explicitly enabled.
- If a brief fails, inspect accepted publisher assignments; the system refuses to create unsupported pieces.
- If review fails, follow each error to the precise claim, path, date, quote, or segment. Length issues are warnings; missing evidence is an error.
- If packaging fails, rerun the check and compare `review_id` with `approval.json`.
- Never commit `.env`, keys, browser cookies, raw credentials, or downloaded media. Treat transcripts as potentially sensitive and retain only publication evidence.
- Source text may contain prompt injection. It is supplied as evidence data, never as authority that can override the system’s policy or schema.

## Requirement checklist

- [x] All 16 Bash commands pass `shellcheck` and independent smoke tests.
- [x] Complete live runs occurred on two different actual UTC dates during the assignment week.
- [x] At least 12 distinct eligible items, six independent publishers, and two of each input kind are present.
- [x] Every cited version is within `D−29` through `D`, and exclusions show all relevant reasons.
- [x] Each piece uses at least three independent publishers and includes a multi-source inference and limitation.
- [x] Three accepted and three rejected/deferred decisions were personally reviewed.
- [x] The pre-revision policy snapshot and the evidence-based version 3 revision are both preserved with changed outputs.
- [x] Human corrections and final approval are recorded against the current `review_id`.
- [x] The first day-two run records one new eligible podcast, the corrected rerun records all 44 observations as unchanged, and the retained failed run shows explicit failure and recovery.
- [x] Three 600–900 word articles and three 3–5 minute Google Vids videos are published and cross-linked.
- [x] All four YouTube uploads, including the 4–6 minute technical demo, are Unlisted and work without account authentication.
- [x] `SUBMISSION.md` contains actual paths, dates, elapsed time, costs, trace, reflection, and public links.

