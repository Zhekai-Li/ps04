from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .common import die_from_exception, load_json, read_jsonl, utc_now, validate_run_dir, write_receipt


def _records(path: Path) -> list[dict[str, Any]] | None:
    return read_jsonl(path) if path.is_file() else None


def _count(records: list[dict[str, Any]] | None) -> int | None:
    return None if records is None else len(records)


def summarize(run_dir_arg: str) -> int:
    stage = "summarize_run"
    started = utc_now()
    run_dir = None
    try:
        run_dir = validate_run_dir(run_dir_arg)
        run = load_json(run_dir / "run.json")
        candidates = _records(run_dir / "candidates.jsonl")
        items = _records(run_dir / "items.jsonl")
        changes = _records(run_dir / "changes.jsonl")
        eligible = _records(run_dir / "eligible.jsonl")
        exclusions = _records(run_dir / "exclusions.jsonl")
        decisions = _records(run_dir / "decisions.jsonl")
        articles = _records(run_dir / "articles.jsonl")
        scripts = _records(run_dir / "video_scripts.jsonl")
        review = load_json(run_dir / "review.json") if (run_dir / "review.json").is_file() else None
        receipts = []
        for path in sorted((run_dir / "logs").glob("*.json")) if (run_dir / "logs").is_dir() else []:
            try:
                receipts.append(load_json(path))
            except Exception:
                continue
        failed = [
            {"stage": receipt.get("stage"), "status": receipt.get("status"), "errors": receipt.get("errors", [])}
            for receipt in receipts if receipt.get("status") in {"failed", "incomplete", "invalid"}
        ]
        package_ready = (run_dir / "package" / "manifest.json").is_file()
        if package_ready:
            status = "ready_for_production"
        elif review and review.get("passed") and articles and scripts:
            status = "awaiting_review"
        else:
            status = "failed"
        change_counts = Counter(record.get("change") for record in changes or [])
        decision_counts = Counter(record.get("decision") for record in decisions or [])
        raw_kind_counts = Counter(record.get("kind") for record in candidates or [])
        eligible_kind_counts = Counter(record.get("kind") for record in eligible or [])
        raw_underlying = [record.get("underlying_id") or record.get("item_id") for record in candidates or []]
        duplicate_observations = len(raw_underlying) - len(set(raw_underlying))
        publishers = sorted({record.get("publisher_id") for record in eligible or [] if record.get("publisher_id")})
        tools = sorted({tool for receipt in receipts for tool in receipt.get("tools", [])})
        models = sorted({model for receipt in receipts for model in receipt.get("models", [])})
        known_cost = round(sum(float(receipt["cost_usd"]) for receipt in receipts if receipt.get("cost_usd") is not None), 6)
        unknown_cost_stages = sorted({receipt.get("stage") for receipt in receipts if receipt.get("models") and receipt.get("cost_usd") is None})
        finished_values = [receipt.get("finished_at") for receipt in receipts if receipt.get("finished_at")]
        finish = max(finished_values) if finished_values else utc_now()
        begin_dt = datetime.fromisoformat(run["started_at"].replace("Z", "+00:00"))
        finish_dt = datetime.fromisoformat(finish.replace("Z", "+00:00"))
        publication_links = None
        links_path = run_dir / "package" / "publication_links.json"
        if links_path.is_file():
            publication_links = load_json(links_path)
        remaining = []
        if status == "failed":
            remaining.append("Repair blocking collection, evidence, model, or review errors and rerun the affected stage.")
        if status == "awaiting_review":
            remaining.append("Zhekai Li must inspect the drafts and evidence, record corrections, and create approval.json personally.")
        if status == "ready_for_production":
            remaining.extend([
                "Create three 3–5 minute videos in Google Vids.",
                "Publish three free Substack articles and upload the videos plus technical demo to YouTube as Unlisted.",
                "Cross-link, verify signed-out access, and fill publication_links.json and SUBMISSION.md.",
            ])
        summary = {
            "run_id": run["run_id"],
            "mode": run["mode"],
            "as_of_date": run["as_of_date"],
            "status": status,
            "counts": {
                "discovered": _count(candidates), "extracted": _count(items),
                "new": None if changes is None else change_counts["new"],
                "changed": None if changes is None else change_counts["changed"],
                "unchanged": None if changes is None else change_counts["unchanged"],
                "eligible": _count(eligible), "excluded": _count(exclusions),
                "accepted": None if decisions is None else decision_counts["accept"],
                "rejected": None if decisions is None else decision_counts["reject"],
                "deferred": None if decisions is None else decision_counts["defer"],
                "articles": _count(articles), "video_scripts": _count(scripts),
            },
            "coverage": {
                "raw_by_kind": dict(raw_kind_counts),
                "eligible_by_kind": dict(eligible_kind_counts),
                "independent_publishers": len(publishers) if eligible is not None else None,
                "publisher_ids": publishers,
                "distinct_underlying_items": len(set(raw_underlying)) if candidates is not None else None,
                "duplicate_observations": duplicate_observations if candidates is not None else None,
            },
            "failed_or_incomplete_stages": failed,
            "elapsed_seconds": round((finish_dt - begin_dt).total_seconds(), 3),
            "tools": tools,
            "models": models,
            "cost": {"known_or_estimated_usd": known_cost, "unknown_cost_stages": unknown_cost_stages},
            "review": None if review is None else {"review_id": review.get("review_id"), "passed": review.get("passed")},
            "publication_links": publication_links,
            "remaining_manual_actions": remaining,
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        write_receipt(run_dir, stage, "completed", started, None, 1, tools=["python"])
        return 0
    except Exception as exc:
        return die_from_exception(stage, run_dir, started, exc)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir")
    args = parser.parse_args()
    return summarize(args.run_dir)


if __name__ == "__main__":
    raise SystemExit(main())

