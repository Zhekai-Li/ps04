from __future__ import annotations

import argparse
import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .common import InputError, ROOT, load_json, utc_now, write_json, write_receipt


def validate_config() -> None:
    project = load_json("config/project.json")
    for key in ("publication_name", "topic", "audience", "central_question"):
        if not isinstance(project.get(key), str) or not project[key].strip():
            raise InputError(f"config/project.json: {key} must be a nonempty string")
    sources = load_json("config/sources.json")
    if not isinstance(sources, list):
        raise InputError("config/sources.json must be an array")
    kinds = set()
    source_ids = set()
    for index, source in enumerate(sources):
        for key in ("source_id", "publisher_id", "kind", "url"):
            if not isinstance(source.get(key), str) or not source[key].strip():
                raise InputError(f"config/sources.json[{index}].{key} must be a nonempty string")
        if source["kind"] not in {"feed", "youtube", "podcast"}:
            raise InputError(f"config/sources.json[{index}].kind is invalid")
        if source["source_id"] in source_ids:
            raise InputError(f"duplicate source_id: {source['source_id']}")
        source_ids.add(source["source_id"])
        kinds.add(source["kind"])
    if kinds != {"feed", "youtube", "podcast"}:
        raise InputError("sources must include feed, youtube, and podcast definitions")
    for path in (
        "config/editorial_policy.md", "config/models.json", "prompts/select_items.md",
        "prompts/create_briefs.md", "prompts/write_articles.md", "prompts/write_video_scripts.md",
    ):
        if not (ROOT / path).is_file() or not (ROOT / path).read_text(encoding="utf-8").strip():
            raise InputError(f"required configuration is empty or missing: {path}")
    models = load_json("config/models.json")
    for key in ("editorial_model", "writing_model", "transcription_model"):
        if not isinstance(models.get(key), str) or not models[key]:
            raise InputError(f"config/models.json: {key} must be nonempty")


def _previous_live_run() -> str | None:
    candidates: list[tuple[str, str]] = []
    runs_dir = ROOT / "runs"
    if not runs_dir.is_dir():
        return None
    for metadata_path in runs_dir.glob("*/run.json"):
        try:
            value = json.loads(metadata_path.read_text(encoding="utf-8"))
            if value.get("mode") == "live":
                candidates.append((value["started_at"], value["run_id"]))
        except Exception:
            continue
    return max(candidates)[1] if candidates else None


def create(mode: str, as_of_override: str | None) -> Path:
    validate_config()
    now = datetime.now(timezone.utc).replace(microsecond=0)
    if mode == "live" and as_of_override is not None:
        raise InputError("live runs must use the actual UTC execution date")
    as_of_date = as_of_override or now.date().isoformat()
    if as_of_override:
        datetime.strptime(as_of_override, "%Y-%m-%d")
    run_id = f"{mode}-{now.strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    run_dir = ROOT / "runs" / run_id
    for path in ("config", "prompts", "logs", "candidates", "articles", "video_scripts"):
        (run_dir / path).mkdir(parents=True, exist_ok=True)
    previous = _previous_live_run()
    write_json(run_dir / "run.json", {
        "run_id": run_id,
        "started_at": now.isoformat().replace("+00:00", "Z"),
        "as_of_date": as_of_date,
        "mode": mode,
        "previous_run_id": previous,
    })
    for name in ("project.json", "sources.json", "editorial_policy.md", "models.json"):
        shutil.copy2(ROOT / "config" / name, run_dir / "config" / name)
    for name in ("select_items.md", "create_briefs.md", "write_articles.md", "write_video_scripts.md"):
        shutil.copy2(ROOT / "prompts" / name, run_dir / "prompts" / name)
    write_receipt(run_dir, "run_setup", "completed", utc_now(), 0, 1, tools=["python"], details={"mode": mode})
    return run_dir


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    create_parser = sub.add_parser("create")
    create_parser.add_argument("mode", choices=["live", "replay", "example", "failure-demo"])
    create_parser.add_argument("--as-of-date")
    args = parser.parse_args()
    try:
        if args.command == "validate":
            validate_config()
            return 0
        print(create(args.mode, args.as_of_date).relative_to(ROOT).as_posix())
        return 0
    except Exception as exc:
        print(f"run_setup: {exc}", file=__import__("sys").stderr)
        return 2 if isinstance(exc, (InputError, ValueError)) else 1


if __name__ == "__main__":
    raise SystemExit(main())

