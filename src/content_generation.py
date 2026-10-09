from __future__ import annotations

import argparse
import sys
from typing import Any

from pydantic import ValidationError

from .common import InputError, PipelineError, die_from_exception, emit_jsonl, iter_jsonl, load_json, progress, read_jsonl, repo_path, utc_now, validate_run_dir, write_receipt
from .model_provider import structured_response
from .schemas import Brief, Item, WrittenBatch


def generate(kind: str, run_dir_arg: str) -> int:
    stage = "write_articles" if kind == "articles" else "write_video_scripts"
    started = utc_now()
    run_dir = None
    try:
        run_dir = validate_run_dir(run_dir_arg)
        raw_briefs = list(iter_jsonl(sys.stdin))
        try:
            briefs = [Brief.model_validate(value).model_dump() for value in raw_briefs]
        except ValidationError as exc:
            raise InputError(f"invalid brief: {exc}") from exc
        if [brief["piece_id"] for brief in briefs] != ["01", "02", "03"]:
            raise InputError("expected exactly three briefs ordered 01, 02, 03")
        evidence_keys = {
            (reference["item_id"], reference["version_id"])
            for brief in briefs for claim in brief["claims"] for reference in claim["evidence"]
        }
        eligible = [Item.model_validate(item).model_dump() for item in read_jsonl(run_dir / "eligible.jsonl")]
        index = {(item["item_id"], item["version_id"]): item for item in eligible}
        if not evidence_keys.issubset(index):
            raise InputError(f"brief references missing eligible evidence: {sorted(evidence_keys - set(index))}")
        evidence = []
        for key in sorted(evidence_keys):
            item = index[key]
            evidence.append({
                "item_id": item["item_id"], "version_id": item["version_id"], "kind": item["kind"],
                "title": item["title"], "url": item["url"], "publisher_id": item["publisher_id"],
                "published_at": item["published_at"],
                "segments": load_json(item["segments_path"]) if item.get("segments_path") else None,
            })
        prompt_name = "write_articles.md" if kind == "articles" else "write_video_scripts.md"
        prompt = (run_dir / "prompts" / prompt_name).read_text(encoding="utf-8")
        models = load_json(run_dir / "config" / "models.json")
        progress(stage, f"Generating 3 {kind.replace('_', ' ')} from {len(evidence_keys)} exact evidence versions", status="info")
        result, meta = structured_response(
            run_dir=run_dir,
            stage=stage,
            model_name=models["writing_model"],
            schema=WrittenBatch,
            instructions=prompt,
            payload={
                "project": load_json(run_dir / "config" / "project.json"),
                "as_of_date": load_json(run_dir / "run.json")["as_of_date"],
                "briefs": briefs,
                "evidence_metadata": evidence,
            },
        )
        pieces = [piece.model_dump() for piece in result.pieces]
        if [piece["piece_id"] for piece in pieces] != ["01", "02", "03"]:
            raise PipelineError("model must return exactly one piece for each ID in order 01, 02, 03")
        output_dir = run_dir / kind
        output_dir.mkdir(parents=True, exist_ok=True)
        manifests = []
        brief_index = {brief["piece_id"]: brief for brief in briefs}
        marker = "<!-- claim:{claim} -->" if kind == "articles" else "[claim:{claim}]"
        for piece in pieces:
            piece_id = piece["piece_id"]
            claims = [claim["claim_id"] for claim in brief_index[piece_id]["claims"]]
            missing = [claim for claim in claims if marker.format(claim=claim) not in piece["markdown"]]
            if missing:
                raise PipelineError(f"{kind} piece {piece_id} is missing claim markers: {missing}")
            path = output_dir / f"{piece_id}.md"
            path.write_text(piece["markdown"].rstrip() + "\n", encoding="utf-8")
            manifests.append({"piece_id": piece_id, "path": path.relative_to(repo_path(".")).as_posix(), "claim_ids": claims})
            progress(stage, f"Saved piece {piece_id} with {len(claims)} claim markers", current=int(piece_id), total=3, status="ok")
        emit_jsonl(manifests)
        write_receipt(
            run_dir, stage, "completed", started, len(briefs), len(manifests), tools=[meta["provider"]],
            models=[meta["model"]], usage=meta["usage"], cost_usd=meta["cost_usd"], cost_estimated=meta["cost_estimated"],
        )
        return 0
    except Exception as exc:
        return die_from_exception(stage, run_dir, started, exc)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("kind", choices=["articles", "video_scripts"])
    parser.add_argument("run_dir")
    args = parser.parse_args()
    return generate(args.kind, args.run_dir)


if __name__ == "__main__":
    raise SystemExit(main())

