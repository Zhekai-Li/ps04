from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from dateutil import parser as date_parser

from .common import InputError, PipelineError, die_from_exception, load_json, normalized_text, read_jsonl, repo_path, utc_now, validate_run_dir, write_receipt
from .schemas import Brief, Item, Segment


def _issue(issues: list[dict[str, str]], artifact: str, severity: str, message: str) -> None:
    issues.append({"artifact": artifact, "severity": severity, "message": message})


def _store_get(item_id: str, version_id: str) -> dict[str, Any]:
    result = subprocess.run(
        ["bash", "data/store.sh", "get", item_id, version_id],
        cwd=repo_path("."), capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        raise PipelineError(result.stderr.strip() or f"store lookup failed for {item_id}@{version_id}")
    return json.loads(result.stdout)


def _word_count(markdown: str) -> int:
    without_urls = re.sub(r"https?://\S+", "", markdown)
    without_code = re.sub(r"<!--.*?-->|\[[^]]+\]\([^)]*\)", " ", without_urls, flags=re.S)
    return len(re.findall(r"\b[\w’'-]+\b", without_code))


def compute_review(run_dir: Path) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    required = ["briefs.jsonl", "articles.jsonl", "video_scripts.jsonl", "eligible.jsonl", "decisions.jsonl", "run.json"]
    for name in required:
        if not (run_dir / name).is_file():
            _issue(issues, name, "error", "required artifact is missing")
    if any(issue["severity"] == "error" for issue in issues):
        fingerprint = hashlib.sha256((str(run_dir) + json.dumps(issues, sort_keys=True)).encode()).hexdigest()
        return {"review_id": fingerprint, "passed": False, "issues": issues, "metrics": {}}

    try:
        briefs = [Brief.model_validate(value).model_dump() for value in read_jsonl(run_dir / "briefs.jsonl")]
        articles = read_jsonl(run_dir / "articles.jsonl")
        scripts = read_jsonl(run_dir / "video_scripts.jsonl")
        eligible = [Item.model_validate(value).model_dump() for value in read_jsonl(run_dir / "eligible.jsonl")]
    except Exception as exc:
        _issue(issues, "run artifacts", "error", f"schema/read failure: {exc}")
        fingerprint = hashlib.sha256(json.dumps(issues, sort_keys=True).encode()).hexdigest()
        return {"review_id": fingerprint, "passed": False, "issues": issues, "metrics": {}}

    expected_pieces = ["01", "02", "03"]
    for artifact, records in (("briefs.jsonl", briefs), ("articles.jsonl", articles), ("video_scripts.jsonl", scripts)):
        if [record.get("piece_id") for record in records] != expected_pieces:
            _issue(issues, artifact, "error", "must contain exactly pieces 01, 02, and 03 in order")

    run = load_json(run_dir / "run.json")
    as_of = date.fromisoformat(run["as_of_date"])
    window_start = as_of - timedelta(days=29)
    unique_underlying = {item.get("underlying_id") or item["item_id"] for item in eligible}
    publishers = {item["publisher_id"] for item in eligible}
    kinds = Counter(item["kind"] for item in eligible)
    if len(unique_underlying) < 12:
        _issue(issues, "eligible.jsonl", "error", f"only {len(unique_underlying)} distinct eligible substantive items; 12 required")
    if len(publishers) < 6:
        _issue(issues, "eligible.jsonl", "error", f"only {len(publishers)} independent publishers; 6 required")
    for kind in ("feed", "youtube", "podcast"):
        if kinds[kind] < 2:
            _issue(issues, "eligible.jsonl", "error", f"only {kinds[kind]} eligible {kind} items; 2 required")
    for item in eligible:
        try:
            published = date_parser.isoparse(item["published_at"]).date()
            if not window_start <= published <= as_of:
                _issue(issues, "eligible.jsonl", "error", f"{item['item_id']} is outside the inclusive 30-day window")
        except Exception:
            _issue(issues, "eligible.jsonl", "error", f"{item['item_id']} has an invalid publication date")

    reviewed_evidence: dict[tuple[str, str], dict[str, Any]] = {}
    piece_publishers: dict[str, set[str]] = {piece: set() for piece in expected_pieces}
    cited_kinds: set[str] = set()
    all_claim_ids: dict[str, list[str]] = {}
    for brief in briefs:
        piece_id = brief["piece_id"]
        claim_ids = [claim["claim_id"] for claim in brief["claims"]]
        all_claim_ids[piece_id] = claim_ids
        if not any(claim["type"] == "inference" and len({ref["item_id"] for ref in claim["evidence"]}) >= 2 for claim in brief["claims"]):
            _issue(issues, f"briefs:{piece_id}", "error", "piece lacks a multi-source inference")
        for claim in brief["claims"]:
            for reference in claim["evidence"]:
                key = (reference["item_id"], reference["version_id"])
                try:
                    item = reviewed_evidence.setdefault(key, _store_get(*key))
                    piece_publishers[piece_id].add(item["publisher_id"])
                    cited_kinds.add(item["kind"])
                    locator = reference["locator"]
                    if locator["type"] == "text":
                        text = repo_path(item["text_path"]).read_text(encoding="utf-8")
                        if locator["quote"] not in text:
                            _issue(issues, f"claim:{claim['claim_id']}", "error", f"exact quote does not resolve in {item['text_path']}")
                    else:
                        if not item.get("segments_path"):
                            _issue(issues, f"claim:{claim['claim_id']}", "error", "segment locator cites evidence without segments")
                        else:
                            segments = [Segment.model_validate(value).model_dump() for value in load_json(item["segments_path"])]
                            if locator["segment_id"] not in {segment["segment_id"] for segment in segments}:
                                _issue(issues, f"claim:{claim['claim_id']}", "error", f"segment {locator['segment_id']} does not resolve")
                except Exception as exc:
                    _issue(issues, f"claim:{claim['claim_id']}", "error", f"evidence lookup failed: {exc}")
        if len(piece_publishers[piece_id]) < 3:
            _issue(issues, f"briefs:{piece_id}", "error", f"piece uses only {len(piece_publishers[piece_id])} independent publishers")
    missing_kinds = {"feed", "youtube", "podcast"} - cited_kinds
    if missing_kinds:
        _issue(issues, "briefs.jsonl", "error", f"series claims do not use these required input kinds: {sorted(missing_kinds)}")

    article_counts: dict[str, int] = {}
    script_counts: dict[str, int] = {}
    for label, manifests, is_article in (("articles", articles, True), ("video_scripts", scripts, False)):
        for manifest in manifests:
            piece_id = manifest.get("piece_id")
            path_value = manifest.get("path")
            if piece_id not in expected_pieces or not isinstance(path_value, str):
                _issue(issues, f"{label}.jsonl", "error", "manifest has invalid piece_id or path")
                continue
            path = repo_path(path_value)
            if not path.is_file():
                _issue(issues, path_value, "error", "manifest path does not exist")
                continue
            markdown = path.read_text(encoding="utf-8")
            expected_claims = all_claim_ids.get(piece_id, [])
            if manifest.get("claim_ids") != expected_claims:
                _issue(issues, path_value, "error", "manifest claim IDs do not match the brief")
            for claim_id in expected_claims:
                marker = f"<!-- claim:{claim_id} -->" if is_article else f"[claim:{claim_id}]"
                if marker not in markdown:
                    _issue(issues, path_value, "error", f"missing claim marker {claim_id}")
            count = _word_count(markdown)
            if is_article:
                article_counts[piece_id] = count
                if not 600 <= count <= 900:
                    _issue(issues, path_value, "warning", f"approximately {count} words; target is 600–900 excluding references")
            else:
                script_counts[piece_id] = count
                if not 390 <= count <= 750:
                    _issue(issues, path_value, "warning", f"approximately {count} words; expected 3–5 minutes at 130–150 wpm")

    _issue(issues, "human_review", "warning", "A machine check cannot establish sound interpretation; Zhekai Li must review the evidence, corrections, and final prose before approval.")

    digest = hashlib.sha256()
    digest.update(run["as_of_date"].encode())
    fingerprint_paths = [run_dir / "briefs.jsonl", run_dir / "articles.jsonl", run_dir / "video_scripts.jsonl"]
    fingerprint_paths += [repo_path(record["path"]) for record in articles + scripts if isinstance(record.get("path"), str) and repo_path(record["path"]).is_file()]
    for path in sorted(fingerprint_paths, key=lambda value: str(value)):
        digest.update(str(path.relative_to(repo_path("."))).encode())
        digest.update(path.read_bytes())
    for key, record in sorted(reviewed_evidence.items()):
        digest.update(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode())
        digest.update(repo_path(record["text_path"]).read_bytes())
        if record.get("segments_path"):
            digest.update(repo_path(record["segments_path"]).read_bytes())
    passed = not any(issue["severity"] == "error" for issue in issues)
    return {
        "review_id": digest.hexdigest(),
        "passed": passed,
        "issues": issues,
        "metrics": {
            "distinct_eligible_items": len(unique_underlying),
            "independent_publishers": len(publishers),
            "eligible_by_kind": dict(kinds),
            "cited_kinds": sorted(cited_kinds),
            "article_word_counts": article_counts,
            "video_script_word_counts": script_counts,
        },
    }


def check(run_dir_arg: str) -> int:
    stage = "check_content"
    started = utc_now()
    run_dir = None
    try:
        run_dir = validate_run_dir(run_dir_arg)
        review = compute_review(run_dir)
        print(json.dumps(review, ensure_ascii=False, indent=2))
        write_receipt(run_dir, stage, "completed", started, None, 1, tools=["pydantic", "sqlite3-store-interface"], details={"review_id": review["review_id"], "passed": review["passed"]})
        return 0
    except Exception as exc:
        return die_from_exception(stage, run_dir, started, exc)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir")
    args = parser.parse_args()
    return check(args.run_dir)


if __name__ == "__main__":
    raise SystemExit(main())

