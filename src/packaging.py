from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from .common import InputError, PipelineError, die_from_exception, load_json, read_jsonl, repo_path, utc_now, validate_run_dir, write_json, write_receipt
from .reviewing import _store_get, compute_review
from .schemas import Brief


def _timestamp(seconds: float) -> str:
    total = int(seconds)
    return f"{total // 60}:{total % 60:02d}"


def _source_notes(brief: dict[str, Any]) -> str:
    lines = [f"# Source notes — Piece {brief['piece_id']}: {brief['title']}", ""]
    seen: set[tuple[str, str, str]] = set()
    for claim in brief["claims"]:
        lines.extend([f"## {claim['claim_id']}", "", claim["statement"], ""])
        for reference in claim["evidence"]:
            locator = reference["locator"]
            identity = (reference["item_id"], reference["version_id"], json.dumps(locator, sort_keys=True))
            if identity in seen:
                continue
            seen.add(identity)
            item = _store_get(reference["item_id"], reference["version_id"])
            if locator["type"] == "text":
                location = f'Exact passage: “{locator["quote"]}”'
            else:
                segments = load_json(item["segments_path"])
                segment = next(value for value in segments if value["segment_id"] == locator["segment_id"])
                location = f"{locator['segment_id']} at {_timestamp(segment['start_seconds'])}–{_timestamp(segment['end_seconds'])}: “{segment['text']}”"
            lines.append(f"- [{item['title']}]({item['url']}) — {item['publisher_id']}, {item['published_at']}; version `{item['version_id']}`. {location}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def package(run_dir_arg: str) -> int:
    stage = "prepare_package"
    started = utc_now()
    run_dir = None
    try:
        run_dir = validate_run_dir(run_dir_arg)
        review_path = run_dir / "review.json"
        approval_path = run_dir / "approval.json"
        if not review_path.is_file():
            raise PipelineError("review.json is missing; run content checks first")
        saved_review = load_json(review_path)
        current_review = compute_review(run_dir)
        if current_review["review_id"] != saved_review.get("review_id"):
            raise PipelineError("review is stale: reviewed inputs have changed")
        if not current_review["passed"]:
            raise PipelineError("current review contains blocking errors")
        if not approval_path.is_file():
            raise PipelineError("approval.json is missing; only Zhekai Li may add human approval after review")
        approval = load_json(approval_path)
        required = {"review_id", "decision", "reviewer", "reviewed_at", "notes"}
        if not required.issubset(approval):
            raise InputError(f"approval.json is missing fields: {sorted(required - set(approval))}")
        if approval["review_id"] != current_review["review_id"]:
            raise PipelineError("approval is stale or refers to another review")
        if approval["decision"] != "approve":
            raise PipelineError("human decision is not approve")
        if not isinstance(approval["reviewer"], str) or not approval["reviewer"].strip():
            raise InputError("approval reviewer must be nonempty")
        try:
            datetime.fromisoformat(str(approval["reviewed_at"]).replace("Z", "+00:00"))
        except ValueError as exc:
            raise InputError("approval reviewed_at must be ISO 8601") from exc

        package_dir = run_dir / "package"
        article_dir = package_dir / "articles"
        script_dir = package_dir / "video_scripts"
        notes_dir = package_dir / "source_notes"
        for directory in (article_dir, script_dir, notes_dir):
            directory.mkdir(parents=True, exist_ok=True)
        articles = read_jsonl(run_dir / "articles.jsonl")
        scripts = read_jsonl(run_dir / "video_scripts.jsonl")
        briefs = [Brief.model_validate(value).model_dump() for value in read_jsonl(run_dir / "briefs.jsonl")]
        assets = []
        for manifest, destination_dir, asset_type in ((articles, article_dir, "article"), (scripts, script_dir, "video_script")):
            for record in manifest:
                source = repo_path(record["path"])
                destination = destination_dir / f"{record['piece_id']}.md"
                shutil.copy2(source, destination)
                assets.append({"piece_id": record["piece_id"], "type": asset_type, "path": destination.relative_to(repo_path(".")).as_posix(), "claim_ids": record["claim_ids"]})
        for brief in briefs:
            path = notes_dir / f"{brief['piece_id']}.md"
            path.write_text(_source_notes(brief), encoding="utf-8")
            assets.append({"piece_id": brief["piece_id"], "type": "source_notes", "path": path.relative_to(repo_path(".")).as_posix()})

        links_path = package_dir / "publication_links.json"
        if not links_path.is_file():
            write_json(links_path, [
                {"piece_id": piece_id, "substack_url": None, "youtube_url": None}
                for piece_id in ("01", "02", "03")
            ])
        handoff = package_dir / "PRODUCTION.md"
        if not handoff.is_file():
            handoff.write_text(
                "# Production handoff\n\n"
                "1. Review each article, script, and source-note file again.\n"
                "2. Build each 3–5 minute audience video in Google Vids from `video_scripts/`, including AI-presentation disclosure and its source slate.\n"
                "3. Publish each article on Scholar in the Loop with free, shareable access and link its corresponding video.\n"
                "4. Upload the three videos to YouTube as Unlisted; descriptions must link the article and source notes.\n"
                "5. Verify every link in a signed-out browser, then fill `publication_links.json`.\n"
                "6. Record and upload the separate 4–6 minute technical demonstration as Unlisted.\n\n"
                "Packaging does not mean that any video was rendered or anything was published.\n",
                encoding="utf-8",
            )
        assets.append({"piece_id": None, "type": "production_handoff", "path": handoff.relative_to(repo_path(".")).as_posix()})
        manifest = {
            "run_id": load_json(run_dir / "run.json")["run_id"],
            "review_id": current_review["review_id"],
            "approval": {"reviewer": approval["reviewer"], "reviewed_at": approval["reviewed_at"]},
            "assets": assets,
            "publication_links_path": links_path.relative_to(repo_path(".")).as_posix(),
            "manual_steps_complete": False,
        }
        write_json(package_dir / "manifest.json", manifest)
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        write_receipt(run_dir, stage, "completed", started, 6, len(assets), tools=["python-shutil"], details={"review_id": current_review["review_id"]})
        return 0
    except Exception as exc:
        return die_from_exception(stage, run_dir, started, exc)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir")
    args = parser.parse_args()
    return package(args.run_dir)


if __name__ == "__main__":
    raise SystemExit(main())

