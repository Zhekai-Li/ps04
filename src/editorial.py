from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .common import InputError, PipelineError, die_from_exception, emit_jsonl, iter_jsonl, load_json, progress, read_jsonl, repo_path, sha256_text, utc_now, validate_run_dir, write_json, write_receipt
from .model_provider import structured_response
from .schemas import BriefBatch, Decision, DecisionBatch, Item


def _media_excerpt(segments: list[dict[str, Any]], query: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if len(segments) <= 120 and len(json.dumps(segments, ensure_ascii=False)) <= 30000:
        return segments, {"strategy": "full-short-media", "total_segments": len(segments), "selected_segment_ids": [s["segment_id"] for s in segments]}
    terms = {word for word in re.findall(r"[a-z0-9]{4,}", query.lower()) if word not in {"that", "this", "with", "from", "what", "which", "their"}}
    scored = sorted(range(len(segments)), key=lambda index: (-sum(segments[index]["text"].lower().count(term) for term in terms), index))
    priority: list[int] = [0, len(segments) - 1] if segments else []
    if segments:
        priority.extend(round(position * (len(segments) - 1) / 23) for position in range(24))
    priority.extend(range(min(8, len(segments))))
    priority.extend(range(max(0, len(segments) - 8), len(segments)))
    for index in scored[:50]:
        priority.extend((index - 1, index, index + 1))
    selected: list[int] = []
    used_chars = 2
    for index in priority:
        if index < 0 or index >= len(segments) or index in selected:
            continue
        size = len(json.dumps(segments[index], ensure_ascii=False)) + 1
        if len(selected) >= 120 or used_chars + size > 30000:
            continue
        selected.append(index)
        used_chars += size
    selected.sort()
    excerpt = [segments[index] for index in selected]
    return excerpt, {
        "strategy": "opening-ending-uniform-relevance", "total_segments": len(segments),
        "selected_segment_ids": [segment["segment_id"] for segment in excerpt],
        "query_terms": sorted(terms), "serialized_chars": used_chars,
    }


def _evidence_payload(run_dir: Path, item: dict[str, Any], *, stage: str, query: str = "") -> dict[str, Any]:
    try:
        full_text = repo_path(item["text_path"]).read_text(encoding="utf-8")
    except OSError as exc:
        raise InputError(f"cannot read evidence text {item['text_path']}: {exc}") from exc
    segments = None
    if item.get("segments_path"):
        segments, manifest = _media_excerpt(load_json(item["segments_path"]), query)
        if manifest["strategy"] != "full-short-media":
            manifest.update({"item_id": item["item_id"], "version_id": item["version_id"], "stage": stage})
            manifest_dir = run_dir / "logs" / "excerpt_manifests"
            manifest_dir.mkdir(parents=True, exist_ok=True)
            write_json(manifest_dir / f"{stage}-{sha256_text(item['item_id'])[:16]}.json", manifest)
        # Do not duplicate transcript text alongside the structured segments in the model input.
        text = None
    else:
        text = full_text[:14000]
    return {**item, "text": text, "segments": segments}


def select(run_dir_arg: str) -> int:
    stage = "select_items"
    started = utc_now()
    run_dir = None
    try:
        run_dir = validate_run_dir(run_dir_arg)
        raw_items = list(iter_jsonl(sys.stdin))
        try:
            items = [Item.model_validate(item).model_dump() for item in raw_items]
        except ValidationError as exc:
            raise InputError(f"invalid eligible item: {exc}") from exc
        if not items:
            raise PipelineError("no eligible evidence; editorial selection cannot run")
        progress(stage, f"Preparing {len(items)} eligible evidence items for policy-constrained selection", status="info")
        prompt = (run_dir / "prompts" / "select_items.md").read_text(encoding="utf-8")
        policy = (run_dir / "config" / "editorial_policy.md").read_text(encoding="utf-8")
        project = load_json(run_dir / "config" / "project.json")
        models = load_json(run_dir / "config" / "models.json")
        expected = [(item["item_id"], item["version_id"]) for item in items]
        item_index = {(item["item_id"], item["version_id"]): item for item in items}

        def validate_selection(batch: DecisionBatch) -> None:
            proposed = [decision.model_dump() for decision in batch.decisions]
            actual_keys = [(item["item_id"], item["version_id"]) for item in proposed]
            if len(actual_keys) != len(set(actual_keys)) or set(actual_keys) != set(expected):
                raise PipelineError("model decisions must cover every eligible item exactly once using the supplied versions")
            accepted_kinds = {item_index[key]["kind"] for key, decision in zip(actual_keys, proposed) if decision["decision"] == "accept"}
            missing = {"feed", "youtube", "podcast"} - accepted_kinds
            if missing:
                raise PipelineError(f"coverage error: no credible accepted evidence for input types {sorted(missing)}")

        result, meta = structured_response(
            run_dir=run_dir,
            stage=stage,
            model_name=models["editorial_model"],
            schema=DecisionBatch,
            instructions=f"{prompt}\n\nEDITORIAL POLICY\n{policy}",
            payload={"project": project, "as_of_date": load_json(run_dir / "run.json")["as_of_date"], "items": [_evidence_payload(run_dir, item, stage=stage, query=project["central_question"]) for item in items]},
            semantic_validator=validate_selection,
        )
        decisions = [decision.model_dump() for decision in result.decisions]
        actual = [(item["item_id"], item["version_id"]) for item in decisions]
        ordered = {key: value for key, value in zip(actual, decisions)}
        decisions = [ordered[key] for key in expected]
        decision_counts = {name: sum(value["decision"] == name for value in decisions) for name in ("accept", "reject", "defer")}
        progress(stage, f"accept={decision_counts['accept']} · reject={decision_counts['reject']} · defer={decision_counts['defer']}", status="ok")
        emit_jsonl(decisions)
        write_receipt(
            run_dir, stage, "completed", started, len(items), len(decisions), tools=[meta["provider"]],
            models=[meta["model"]], usage=meta["usage"], cost_usd=meta["cost_usd"], cost_estimated=meta["cost_estimated"],
            details={"billing_mode": meta.get("billing_mode"), "response_id": meta.get("response_id"), "audit_path": meta.get("audit_path")},
        )
        return 0
    except Exception as exc:
        return die_from_exception(stage, run_dir, started, exc)


def _validate_brief_support(
    briefs: list[dict[str, Any]], accepted: dict[tuple[str, str], dict[str, Any]],
    evidence_index: dict[tuple[str, str], dict[str, Any]],
) -> None:
    if [brief["piece_id"] for brief in briefs] != ["01", "02", "03"]:
        raise PipelineError("briefs must be ordered exactly as piece IDs 01, 02, 03")
    seen_claims: set[str] = set()
    for brief in briefs:
        publishers: set[str] = set()
        for claim in brief["claims"]:
            if claim["claim_id"] in seen_claims or not claim["claim_id"].startswith(f"{brief['piece_id']}-c"):
                raise PipelineError(f"duplicate or invalid claim ID: {claim['claim_id']}")
            seen_claims.add(claim["claim_id"])
            for evidence in claim["evidence"]:
                key = (evidence["item_id"], evidence["version_id"])
                if key not in accepted:
                    raise PipelineError(f"claim {claim['claim_id']} cites evidence that was not accepted at that version: {key}")
                if brief["piece_id"] not in accepted[key]["piece_ids"]:
                    raise PipelineError(f"claim {claim['claim_id']} cites an item not assigned to piece {brief['piece_id']}")
                item = evidence_index[key]
                locator = evidence["locator"]
                if locator["type"] == "text":
                    if locator["quote"] not in repo_path(item["text_path"]).read_text(encoding="utf-8"):
                        raise PipelineError(f"claim {claim['claim_id']} has an unresolved text quote")
                else:
                    segment_ids = {segment["segment_id"] for segment in load_json(item["segments_path"])} if item.get("segments_path") else set()
                    if locator["segment_id"] not in segment_ids:
                        raise PipelineError(f"claim {claim['claim_id']} has an unresolved segment locator")
                publishers.add(accepted[key]["publisher_id"])
        if len(publishers) < 3:
            raise PipelineError(f"piece {brief['piece_id']} has only {len(publishers)} independent publishers; at least 3 are required")
    cited_kinds = {
        evidence_index[(reference["item_id"], reference["version_id"])]["kind"]
        for brief in briefs for claim in brief["claims"] for reference in claim["evidence"]
    }
    missing = {"feed", "youtube", "podcast"} - cited_kinds
    if missing:
        raise PipelineError(f"brief coverage error: final briefs do not cite input types {sorted(missing)}")


def create_briefs(run_dir_arg: str) -> int:
    stage = "create_briefs"
    started = utc_now()
    run_dir = None
    try:
        run_dir = validate_run_dir(run_dir_arg)
        raw_decisions = list(iter_jsonl(sys.stdin))
        try:
            decisions = [Decision.model_validate(item).model_dump() for item in raw_decisions]
        except ValidationError as exc:
            raise InputError(f"invalid decision: {exc}") from exc
        eligible = [Item.model_validate(item).model_dump() for item in read_jsonl(run_dir / "eligible.jsonl")]
        evidence_index = {(item["item_id"], item["version_id"]): item for item in eligible}
        accepted: dict[tuple[str, str], dict[str, Any]] = {}
        for decision in decisions:
            key = (decision["item_id"], decision["version_id"])
            if decision["decision"] == "accept":
                if key not in evidence_index:
                    raise InputError(f"decision references missing eligible evidence: {key}")
                accepted[key] = {**decision, "publisher_id": evidence_index[key]["publisher_id"]}
        if len({entry["publisher_id"] for entry in accepted.values()}) < 3:
            raise PipelineError("fewer than three independent publishers were accepted; cannot support the series")
        for piece_id in ("01", "02", "03"):
            publishers = {entry["publisher_id"] for entry in accepted.values() if piece_id in entry["piece_ids"]}
            if len(publishers) < 3:
                raise PipelineError(f"piece {piece_id} has fewer than three assigned independent publishers")
        progress(stage, f"Building briefs from {len(accepted)} accepted evidence versions", status="info")
        prompt = (run_dir / "prompts" / "create_briefs.md").read_text(encoding="utf-8")
        policy = (run_dir / "config" / "editorial_policy.md").read_text(encoding="utf-8")
        models = load_json(run_dir / "config" / "models.json")
        project = load_json(run_dir / "config" / "project.json")
        query = " ".join([project["central_question"]] + [entry["reason"] for entry in accepted.values()])
        evidence = [_evidence_payload(run_dir, evidence_index[key], stage=stage, query=query) for key in accepted]

        def validate_briefs(batch: BriefBatch) -> None:
            _validate_brief_support([brief.model_dump() for brief in batch.briefs], accepted, evidence_index)

        result, meta = structured_response(
            run_dir=run_dir,
            stage=stage,
            model_name=models["editorial_model"],
            schema=BriefBatch,
            instructions=f"{prompt}\n\nEDITORIAL POLICY\n{policy}",
            payload={
                "project": project,
                "as_of_date": load_json(run_dir / "run.json")["as_of_date"],
                "accepted_decisions": [value for value in decisions if value["decision"] == "accept"],
                "evidence": evidence,
            },
            semantic_validator=validate_briefs,
        )
        briefs = [brief.model_dump() for brief in result.briefs]
        progress(stage, "Validated three briefs and their publisher coverage", status="ok")
        emit_jsonl(briefs)
        write_receipt(
            run_dir, stage, "completed", started, len(decisions), len(briefs), tools=[meta["provider"]],
            models=[meta["model"]], usage=meta["usage"], cost_usd=meta["cost_usd"], cost_estimated=meta["cost_estimated"],
            details={"billing_mode": meta.get("billing_mode"), "response_id": meta.get("response_id"), "audit_path": meta.get("audit_path")},
        )
        return 0
    except Exception as exc:
        return die_from_exception(stage, run_dir, started, exc)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["select", "briefs"])
    parser.add_argument("run_dir")
    args = parser.parse_args()
    return select(args.run_dir) if args.stage == "select" else create_briefs(args.run_dir)


if __name__ == "__main__":
    raise SystemExit(main())

