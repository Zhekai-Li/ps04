#!/usr/bin/env python3
"""Deterministic, read-only audit of the final PS04 submission state."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FINAL_RUN = ROOT / "runs/live-20261010T142614Z-b7aaa14e"
FIRST_COMPLETE_RUN = ROOT / "runs/live-20261009T183914Z-438d5dc4"
FAILED_RUN = ROOT / "runs/live-20261009T173953Z-701a3aa8"

REQUIRED_COMPONENTS = (
    "run.sh",
    "workflows/collect_sources.sh",
    "workflows/create_series.sh",
    "collectors/fetch_feeds.sh",
    "collectors/fetch_youtube.sh",
    "collectors/fetch_podcasts.sh",
    "processing/extract_content.sh",
    "processing/filter_items.sh",
    "data/store.sh",
    "editorial/select_items.sh",
    "editorial/create_briefs.sh",
    "content/write_articles.sh",
    "content/write_video_scripts.sh",
    "review/check_content.sh",
    "publishing/prepare_package.sh",
    "reporting/summarize_run.sh",
)

COURSE_FILE_HASHES = {
    "README.md": "4bdeabd9444351b2d0970e7b48d1698d89162dbc3a2a1abc3eb31d396b5328e7",
    "ARCHITECTURE.md": "3f4f89e4b73d4f583b70be88d333df52c653c9ad94854aee9a555bd6753b0e95",
}

PUBLICATION_LINKS = {
    "01": (
        "https://zhekaili.substack.com/p/use-ai-to-expand-the-search-space",
        "https://youtu.be/mcfW1UkP8_M",
    ),
    "02": (
        "https://zhekaili.substack.com/p/fluent-reasoning-is-not-provenance",
        "https://youtu.be/8ZhAS-fPmHw",
    ),
    "03": (
        "https://zhekaili.substack.com/p/preserve-responsibility-by-recording",
        "https://youtu.be/xrAhfqGbpZM",
    ),
}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True
    )
    return [ROOT / value.decode() for value in result.stdout.split(b"\0") if value]


def markdown_local_targets(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    targets = []
    for target in re.findall(r"\[[^]]+\]\(([^)]+)\)", text):
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        target = target.split("#", 1)[0]
        if target:
            targets.append(target)
    return targets


def main() -> int:
    failures: list[str] = []
    checks = 0

    def check(condition: bool, message: str) -> None:
        nonlocal checks
        checks += 1
        if not condition:
            failures.append(message)

    for relative, expected in COURSE_FILE_HASHES.items():
        digest = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        check(digest == expected, f"course contract changed: {relative}")

    for relative in REQUIRED_COMPONENTS:
        path = ROOT / relative
        check(path.is_file(), f"required component missing: {relative}")
        check(path.stat().st_mode & 0o111 != 0, f"required component is not executable: {relative}")

    first_summary = load_json(FIRST_COMPLETE_RUN / "summary.json")
    final_summary = load_json(FINAL_RUN / "summary.json")
    failed_summary = load_json(FAILED_RUN / "summary.json")
    check(first_summary["status"] == "awaiting_review", "first complete run has an unexpected status")
    check(final_summary["status"] == "published", "final run is not marked published")
    check(failed_summary["status"] == "failed", "preserved failure run is not marked failed")
    first_day = date.fromisoformat(first_summary["as_of_date"])
    final_day = date.fromisoformat(final_summary["as_of_date"])
    check(first_day != final_day, "the two complete live runs are not on different UTC dates")

    counts = final_summary["counts"]
    coverage = final_summary["coverage"]
    check(counts["eligible"] >= 12, "final run has fewer than 12 eligible items")
    check(coverage["independent_publishers"] >= 6, "final run has fewer than six publishers")
    for kind in ("feed", "youtube", "podcast"):
        check(coverage["eligible_by_kind"].get(kind, 0) >= 2, f"final run lacks two eligible {kind} items")
        check(coverage["brief_citations_by_kind"].get(kind, 0) >= 1, f"final briefs do not cite {kind} evidence")
    check(counts["articles"] == 3 and counts["video_scripts"] == 3, "final run lacks three content pairs")
    check(final_summary["cost"]["incremental_api_cost_usd"] == 0.0, "default run reports a paid API cost")
    check(final_summary["manual_steps_complete"] is True, "manual publication steps are incomplete")
    check(final_summary["remaining_manual_actions"] == [], "final summary still lists manual actions")

    review = load_json(FINAL_RUN / "review.json")
    approval = load_json(FINAL_RUN / "approval.json")
    manifest = load_json(FINAL_RUN / "package/manifest.json")
    check(review["passed"] is True, "deterministic content review did not pass")
    check(approval["decision"] == "approve", "human approval is not affirmative")
    check(approval["review_id"] == review["review_id"] == manifest["review_id"], "review fingerprints disagree")
    check(manifest["manual_steps_complete"] is True, "package manifest is not publication-complete")
    for count in review["metrics"]["article_word_counts"].values():
        check(600 <= count <= 900, f"article word count is outside 600–900: {count}")

    video_records = load_json(FINAL_RUN / "package/video_drafts.json")
    check(len(video_records) == 3, "video metadata does not contain three audience videos")
    for record in video_records:
        check(180 <= record["duration_seconds"] <= 300, f"video {record['piece_id']} is outside 3–5 minutes")
        check(record["status"] == "published_unlisted", f"video {record['piece_id']} is not marked published Unlisted")
        check(record.get("youtube_processed_resolution") == "1920x1080", f"video {record['piece_id']} lacks verified YouTube 1080p processing")

    demo_record = load_json(FINAL_RUN / "package/technical_demo/manifest.json")
    check(demo_record.get("status") == "published_unlisted", "technical demonstration is not marked published Unlisted")
    check(demo_record.get("youtube_processed_resolution") == "1920x1080", "technical demonstration lacks verified YouTube 1080p processing")
    demo_versions = {record["id"]: record for record in demo_record.get("versions", [])}
    ai_demo = demo_versions.get("ai_narrated_formal", {})
    human_demo = demo_versions.get("human_narrated_supplementary", {})
    check(ai_demo.get("role") == "formal_course_submission", "AI-narrated demo is not designated as the formal submission")
    check(240 <= ai_demo.get("duration_seconds", 0) <= 360, "formal AI-narrated demo is outside 4–6 minutes")
    check(ai_demo.get("meets_duration_requirement") is True, "formal AI demo duration status is incorrect")
    check(human_demo.get("role") == "supplementary_reviewer_version", "human-narrated demo is not designated as supplementary")
    check(human_demo.get("meets_duration_requirement") is False, "human demo duration status is incorrect")
    check(human_demo.get("duration_seconds", 0) > 360, "supplementary human demo duration metadata is inconsistent")
    human_video_path = ROOT / human_demo.get("video_path", "missing")
    check(human_video_path.is_file(), "supplementary human-narrated demo file is missing")
    if human_video_path.is_file():
        human_digest = hashlib.sha256(human_video_path.read_bytes()).hexdigest()
        check(human_digest == human_demo.get("sha256"), "supplementary human demo SHA-256 does not match its manifest")

    links = load_json(FINAL_RUN / "package/publication_links.json")
    check(len(links) == 3, "publication link file does not contain three pairs")
    for record in links:
        expected = PUBLICATION_LINKS.get(record["piece_id"])
        check(expected == (record["substack_url"], record["youtube_url"]), f"publication links disagree for piece {record['piece_id']}")

    briefs = read_jsonl(FINAL_RUN / "briefs.jsonl")
    claim_ids = [claim["claim_id"] for brief in briefs for claim in brief["claims"]]
    check(len(claim_ids) == len(set(claim_ids)), "final briefs contain duplicate claim IDs")
    for claim_id in claim_ids:
        check(re.fullmatch(r"(01|02|03)-c[1-9][0-9]*", claim_id) is not None, f"invalid claim ID: {claim_id}")

    cjk = re.compile(r"[\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]")
    unfinished = re.compile(r"\b(?:pending|todo|tbd|fixme|placeholder)\b", re.IGNORECASE)
    for path in tracked_files():
        data = path.read_bytes()
        if b"\0" in data[:8192]:
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        relative = path.relative_to(ROOT).as_posix()
        check(cjk.search(text) is None, f"non-English CJK text found in {relative}")
        if relative in {"SUBMISSION.md", "docs/editorial_review.md", "docs/technical_demo_script.md"}:
            check(unfinished.search(text) is None, f"unfinished marker found in {relative}")

    for path in [ROOT / "SUBMISSION.md", *sorted((ROOT / "docs").glob("*.md"))]:
        for target in markdown_local_targets(path):
            check((path.parent / target).resolve().exists(), f"broken local link in {path.relative_to(ROOT)}: {target}")

    if failures:
        print(f"Submission audit failed ({len(failures)} of {checks} checks):", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print(f"Submission audit passed: {checks} checks; no remaining required action.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
