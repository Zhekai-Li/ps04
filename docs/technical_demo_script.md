# Technical demonstration script (target: 5 minutes)

Replace every placeholder with actual run paths and results before recording.

| Time | Screen and narration |
| --- | --- |
| 0:00–0:35 | Show the architecture diagram in `docs/LEARNING_GUIDE.md` and `run.sh`. Explain Bash orchestration, typed Python components, SQLite ownership, and the manual approval boundary. |
| 0:35–1:45 | Trace one published claim: candidate record → extracted asset/segments → `data/store.sh get ITEM VERSION` → decision → brief locator → article and video claim marker → package source note. Open the exact quote or timestamp. |
| 1:45–2:35 | Compare the two live `summary.json` files. Show actual UTC dates, new/changed/unchanged counts, and explain whether new evidence changed an editorial choice. |
| 2:35–3:20 | Show replay `changes.jsonl` proving unchanged inputs do not create versions, then the labeled withheld item. Open the failure-demo collector receipt and explicit incomplete-coverage summary. |
| 3:20–4:10 | Show one reviewed AI decision, Zhekai’s disagreement or correction, the pre/post policy text, and the affected rerun output. Explain the evidence behind the correction. |
| 4:10–4:45 | Demonstrate the review fingerprint and approval gate. Explain why a changed draft makes approval stale and why the pipeline cannot author human approval. |
| 4:45–5:00 | Close with the tradeoff: simple auditable Bash interfaces and JSONL artifacts versus less type safety across process boundaries, mitigated by Pydantic validation and receipts. |

Keep identifiers and text readable, narrate rather than silently scrolling, and show that the video is a separate Unlisted upload from the three audience-facing videos.
