# Dual Technical Demonstrations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give reviewers clear access to both the requirements-compliant AI-narrated technical demonstration and the supplementary human-narrated recording while preserving truthful duration and provenance metadata.

**Architecture:** Keep the immutable course `README.md` and `ARCHITECTURE.md` unchanged. Rename and retain the human MP4 in the final package, expose both variants from `SUBMISSION.md`, describe their roles in the technical-demo documentation, and make the final audit verify both records and files.

**Tech Stack:** Markdown, JSON, Python, FFmpeg/FFprobe, Git.

---

### Task 1: Normalize the human recording artifact

**Files:**
- Rename: `runs/live-20261010T142614Z-b7aaa14e/package/technical_demo/video2913004894.mp4`
- To: `runs/live-20261010T142614Z-b7aaa14e/package/technical_demo/technical-demo-human-narrated.mp4`

- [x] Rename the opaque upload to the descriptive English filename.
- [x] Verify its SHA-256, 1920×1080 resolution, audio/video streams, and 444.32-second duration.
- [x] Retain the MP4 in Git so a repository reviewer can open it without access to a private local path.

### Task 2: Document both technical demonstrations

**Files:**
- Modify: `SUBMISSION.md`
- Modify: `docs/technical_demo_script.md`
- Modify: `runs/live-20261010T142614Z-b7aaa14e/package/technical_demo/manifest.json`

- [x] Present the 5:57 AI-narrated YouTube version as the formal 4–6 minute submission.
- [x] Present the 7:24 human-narrated MP4 as a supplementary reviewer-accessible version.
- [x] Link the human-recording deck, preview, and MP4 using repository-relative paths.
- [x] State the duration difference plainly and avoid claiming that the supplementary recording satisfies the 4–6 minute limit.

### Task 3: Enforce consistency and verify

**Files:**
- Modify: `scripts/audit_submission.py`

- [x] Verify that the AI version remains published Unlisted at 1920×1080 and within 4–6 minutes.
- [x] Verify that the human MP4 exists at the documented path, has matching SHA-256 metadata, and is labeled supplementary.
- [x] Run pytest, shellcheck, JSON validation, the submission audit, and Git diff checks.
- [x] Confirm `README.md`, `ARCHITECTURE.md`, and historical failed runs remain unchanged.
- [x] Commit and push the consistent dual-demo submission state.
