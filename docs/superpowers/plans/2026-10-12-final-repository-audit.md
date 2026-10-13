# Final Repository Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkboxes so completion can be audited.

**Goal:** Reconcile the completed project with every course requirement, make the English repository internally consistent, and leave a submission-ready verification record.

**Architecture:** Treat `README.md` and `ARCHITECTURE.md` as immutable course contracts. Verify the implementation and retained runs against those contracts, then update only student-authored documentation and post-publication metadata. Add deterministic repository checks where they make the final state easier to verify.

**Tech Stack:** Bash, Python 3.12, JSON/JSONL, SQLite, pytest, shellcheck, Markdown, Git.

---

## Task 1: Build the requirement-to-evidence matrix

- [x] Extract every required deliverable and process step from `README.md` and `ARCHITECTURE.md`.
- [x] Map each requirement to a committed file, retained live-run artifact, or public URL.
- [x] Separate course requirements from optional quality improvements.
- [x] Record any genuine gaps before changing files.

## Task 2: Audit repository-wide consistency

- [x] Scan tracked text for non-English prose, unfinished markers, stale backend instructions, stale publication states, broken local paths, and inconsistent dates or names.
- [x] Verify all 16 required Bash commands exist and are executable.
- [x] Verify the two successful live runs are on different UTC dates and the earlier failed run remains intact.
- [x] Verify final run counts, source-type coverage, review approval, package metadata, publication links, and costs.

## Task 3: Reconcile student-authored documentation and metadata

- [x] Keep `README.md` and `ARCHITECTURE.md` byte-for-byte unchanged.
- [x] Update `SUBMISSION.md` into a clear final status and requirement-evidence checklist.
- [x] Correct stale or ambiguous wording in student-authored guides and package metadata.
- [x] Ensure all new or changed repository prose is English.

## Task 4: Add and run final submission checks

- [x] Add a deterministic final-audit command if existing tests do not cover submission-level consistency.
- [x] Run pytest, shellcheck, Python compilation, JSON validation, configuration validation, and offline replay.
- [x] Check public URLs and repository-local links without mutating live evidence.
- [x] Review the final Git diff and confirm no historical run snapshot was rewritten.

## Task 5: Hand off the completed submission

- [x] Summarize what is complete, what is optional, and whether any user action remains.
- [x] Give the user the next action in plain Chinese while keeping the repository itself English.
- [x] Commit and push only after all checks pass and the final diff is reviewed.
