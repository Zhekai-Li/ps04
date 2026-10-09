from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .common import InputError, PipelineError, die_from_exception, emit_jsonl, iter_jsonl, load_json, read_jsonl, repo_path, utc_now, validate_run_dir, write_receipt
from .model_provider import structured_response
from .schemas import BriefBatch, Decision, DecisionBatch, Item


def _evidence_payload(item: dict[str, Any], max_chars: int = 14000) -> dict[str, Any]:
    try:
        text = repo_path(item["text_path"]).read_text(encoding="utf-8")[:max_chars]
    except OSError as exc:
        raise InputError(f"cannot read evidence text {item['text_path']}: {exc}") from exc
    segments = None
    if item.get("segments_path"):
        segments = load_json(item["segments_path"])
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
        prompt = (run_dir / "prompts" / "select_items.md").read_text(encoding="utf-8")
        policy = (run_dir / "config" / "editorial_policy.md").read_text(encoding="utf-8")
        project = load_json(run_dir / "config" / "project.json")
        models = load_json(run_dir / "config" / "models.json")
        result, meta = structured_response(
            run_dir=run_dir,
            stage=stage,
            model_name=models["editorial_model"],
            schema=DecisionBatch,
            instructions=f"{prompt}\n\nEDITORIAL POLICY\n{policy}",
            payload={"project": project, "as_of_date": load_json(run_dir / "run.json")["as_of_date"], "items": [_evidence_payload(item) for item in items]},
        )
        decisions = [decision.model_dump() for decision in result.decisions]
        expected = [(item["item_id"], item["version_id"]) for item in items]
        actual = [(item["item_id"], item["version_id"]) for item in decisions]
        if len(actual) != len(set(actual)) or set(actual) != set(expected):
            raise PipelineError("model decisions must cover every eligible item exactly once using the supplied versions")
        ordered = {key: value for key, value in zip(actual, decisions)}
        decisions = [ordered[key] for key in expected]
        emit_jsonl(decisions)
        write_receipt(
            run_dir, stage, "completed", started, len(items), len(decisions), tools=[meta["provider"]],
            models=[meta["model"]], usage=meta["usage"], cost_usd=meta["cost_usd"], cost_estimated=meta["cost_estimated"],
        )
        return 0
    except Exception as exc:
        return die_from_exception(stage, run_dir, started, exc)


def _validate_brief_support(briefs: list[dict[str, Any]], accepted: dict[tuple[str, str], dict[str, Any]]) -> None:
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
                publishers.add(accepted[key]["publisher_id"])
        if len(publishers) < 3:
            raise PipelineError(f"piece {brief['piece_id']} has only {len(publishers)} independent publishers; at least 3 are required")


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
        prompt = (run_dir / "prompts" / "create_briefs.md").read_text(encoding="utf-8")
        policy = (run_dir / "config" / "editorial_policy.md").read_text(encoding="utf-8")
        models = load_json(run_dir / "config" / "models.json")
        evidence = [_evidence_payload(evidence_index[key]) for key in accepted]
        result, meta = structured_response(
            run_dir=run_dir,
            stage=stage,
            model_name=models["editorial_model"],
            schema=BriefBatch,
            instructions=f"{prompt}\n\nEDITORIAL POLICY\n{policy}",
            payload={
                "project": load_json(run_dir / "config" / "project.json"),
                "as_of_date": load_json(run_dir / "run.json")["as_of_date"],
                "accepted_decisions": [value for value in decisions if value["decision"] == "accept"],
                "evidence": evidence,
            },
        )
        briefs = [brief.model_dump() for brief in result.briefs]
        _validate_brief_support(briefs, accepted)
        emit_jsonl(briefs)
        write_receipt(
            run_dir, stage, "completed", started, len(decisions), len(briefs), tools=[meta["provider"]],
            models=[meta["model"]], usage=meta["usage"], cost_usd=meta["cost_usd"], cost_estimated=meta["cost_estimated"],
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

