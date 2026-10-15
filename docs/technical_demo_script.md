# Technical demonstration script

**Formal published duration:** 5 minutes 57 seconds

**Visual source:** `runs/live-20261010T142614Z-b7aaa14e/package/technical_demo/technical-demo-final.pptx`

**Voice:** Nyla

**Course requirement interpretation:** `README.md` requires a separate 4–6 minute narrated demonstration and specifies its content, but it does not require the student's face, personal voice, or a manually captured screen recording. The AI voiceover is disclosed here and in the publication metadata.

**Status:** formal AI-narrated version published to YouTube as an Unlisted technical demonstration

**Published video:** https://youtu.be/-XfGao1GRJs

## Available versions

- **Formal AI-narrated version:** the 5:57 Unlisted YouTube video above, using the full eight-slide `technical-demo-final.pptx`. It satisfies the course's 4–6 minute limit.
- **Supplementary human-narrated version:** [`technical-demo-human-narrated.mp4`](../runs/live-20261010T142614Z-b7aaa14e/package/technical_demo/technical-demo-human-narrated.mp4), visibly using the same full eight-slide `technical-demo-final.pptx`. Zhekai Li narrates this 7:24 version personally. It is retained for reviewer access but is not designated as the formal duration-compliant submission.

The separate five-slide [`technical-demo-human-recording.pptx`](../runs/live-20261010T142614Z-b7aaa14e/package/technical_demo/technical-demo-human-recording.pptx) is an alternate recording deck, not the deck shown in the retained 7:24 human MP4.

## Scene 1 — From fresh evidence to accountable publication

Scholar in the Loop is a repeatable intelligence pipeline for PhD students using AI in research topic selection and academic writing. It preserves the route from fresh evidence to an editorial decision, a reviewed claim, and a publication package. The entry point is `bash run.sh`. Bash keeps all sixteen required component boundaries visible, while typed Python validates the records passed between them. The system stops at a human approval boundary. I will show the architecture, trace one source into a claim, compare two dates, explain a policy correction, and demonstrate duplicate handling and failure recovery.

## Scene 2 — Architecture and ownership

Three collectors handle RSS, YouTube, and podcasts. Extraction retrieves article text or produces timestamped transcripts. Only `data/store.sh` owns the SQLite evidence index; every other stage uses its interface. A thirty-day filter records eligibility and exclusions. Codex applies the snapshotted editorial policy, builds briefs, and drafts matching articles and scripts. Deterministic review resolves every locator and checks claim consistency. Its fingerprint binds the drafts to their evidence and configuration. Packaging succeeds only when Zhekai's approval names that exact fingerprint. Google Vids, Substack, and YouTube remain explicit handoffs, so a generated file is never misreported as published.

## Scene 3 — Two dates, inspectable changes

The first complete live run is dated October ninth. It extracted fifty items and recorded three new versions and forty-seven unchanged versions. It reached `awaiting_review` with three articles and three scripts. The corrected October tenth run extracted forty-four current observations. Every one matched an existing version, so `changes.jsonl` records forty-four as unchanged and creates no unnecessary version. The eligible pool still includes feed, YouTube, and podcast evidence. Nine items are accepted, and the run reaches `ready_for_production` after review and approval. Repeated observations remain visible without inflating the evidence history or pretending that a source changed.

## Scene 4 — One source, exact evidence

One source trace begins with a SciSpace YouTube testimonial, “A Medical Doctor on How SciSpace Changed Her Research Process.” Its stable item ID is `youtube:q_g-rU1kW2o`; the stored version begins `1972602e`. The evidence store points to a timestamped transcript. From fifty-one seconds, the speaker proposes outsourcing tedious work while retaining human thinking, analysis, reasoning, judgment, and deeper paper development. The source also makes a dramatic efficiency comparison. That number lacks matched tasks, independent corroboration, and quality assessment. The qualitative perspective and unsupported performance claim therefore require different evidentiary treatment.

## Scene 5 — Human correction changed the policy

The first editorial decision rejected the whole testimonial because its time-saving claim was unsupported. In human review, I agreed about the number but disagreed with discarding the qualitative division of labor. Policy version three makes that correction repeatable. Relevant stakeholder testimony must be considered when it offers a specific perspective for cross-source synthesis. Unsupported quantitative claims remain excluded, commercial incentives must be disclosed, and testimony cannot establish performance or causation without corroboration. The corrected October tenth rerun accepts the item for pieces two and three, retains only its qualitative perspective, and labels it commercially published testimony rather than independent validation.

## Scene 6 — From decision to claim

The accepted item enters brief three as claim `03-c4`: outsource tedious literature work while retaining human reasoning and judgment. The brief carries the exact item version and timestamped locators. The article and video script reuse the same claim marker, preventing silent divergence. The article also states that the testimony does not validate the product or its claimed acceleration. The package source note resolves `03-c4` to segments twenty-two through twenty-seven, from fifty-one seconds to one minute eleven. The trace therefore connects identity, immutable version, passage, bounded decision, brief claim, two audience formats, and viewer-facing source notes.

## Scene 7 — Failure recovery and local backends

An earlier October ninth run remains as a real failure artifact. Two long podcasts exceeded the paid transcription path's media limit, and the brief stage emitted invalid uppercase claim ID `01-C1`. The repair transcribes long audio locally on Apple MLX with word timestamps and stable global segments. The schema accepts only lower-case identifiers such as `01-c1`; semantic failures receive one bounded retry. Four text stages run through the local Codex CLI in read-only isolation, and tool or search events are rejected. In the final run, both podcasts participate, the schema passes, and incremental API cost is zero. Codex use is reported as ChatGPT-plan consumption, not a fabricated dollar estimate.

## Scene 8 — Approval boundary and tradeoff

The final review produces fingerprint `1361c8b…da4194a`. It binds evidence, policy, prompts, articles, scripts, and deterministic checks. `approval.json` names that exact value. If any input changes, the fingerprint changes and the old approval becomes stale. The pipeline can request review; it cannot manufacture consent. The architectural tradeoff is deliberate: small Bash commands and JSONL streams are easy to replay and inspect but provide less compile-time safety. Pydantic schemas, immutable snapshots, receipts, and one storage owner mitigate that cost. The result is an auditable publication pipeline.

## Recording checklist

- Keep all file paths and identifiers readable at 1920×1080.
- Use the same restrained academic-business visual system as the three audience videos.
- Do not show credentials, browser history, private account details, or hidden model reasoning.
- Export as an MP4 between four and six minutes.
- Upload separately from the three audience-facing videos and set visibility to **Unlisted**.
