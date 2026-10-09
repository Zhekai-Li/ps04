from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta, timezone

from dateutil import parser as date_parser
from pydantic import ValidationError

from .common import InputError, die_from_exception, emit_jsonl, iter_jsonl, load_json, utc_now, validate_run_dir, write_receipt
from .schemas import Item


def _published_date(value: str | None) -> tuple[date | None, str | None]:
    if value is None:
        return None, "unknown_date"
    try:
        parsed = date_parser.isoparse(value)
        if isinstance(parsed, datetime):
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc).date(), None
        return parsed, None
    except (ValueError, TypeError, OverflowError):
        return None, "invalid_date"


def filter_records(run_dir_arg: str) -> int:
    stage = "filter_items"
    started = utc_now()
    run_dir = None
    try:
        run_dir = validate_run_dir(run_dir_arg)
        run = load_json(run_dir / "run.json")
        try:
            as_of = date.fromisoformat(run["as_of_date"])
        except (KeyError, ValueError, TypeError) as exc:
            raise InputError(f"run.json has invalid as_of_date: {exc}") from exc
        window_start = as_of - timedelta(days=29)
        inputs = []
        for raw in iter_jsonl(sys.stdin):
            try:
                inputs.append(Item.model_validate(raw).model_dump())
            except ValidationError as exc:
                raise InputError(f"invalid item record: {exc}") from exc
        eligible = []
        exclusions = []
        for item in inputs:
            published, invalid_reason = _published_date(item["published_at"])
            reason = invalid_reason
            detail = None
            if reason == "unknown_date":
                detail = "publication date is absent; undated evidence cannot support a publication"
            elif reason == "invalid_date":
                detail = f"publication date is not valid ISO 8601: {item['published_at']}"
            elif published > as_of:
                reason = "future_date"
                detail = f"published {published.isoformat()} after as-of date {as_of.isoformat()}"
            elif published < window_start:
                reason = "outside_window"
                detail = f"published {published.isoformat()} before inclusive window start {window_start.isoformat()}"
            if reason:
                exclusions.append({"item_id": item["item_id"], "version_id": item["version_id"], "reason": reason, "detail": detail})
            else:
                eligible.append(item)
        from .common import write_json
        # JSON Lines is required; write atomically without converting it to a JSON document.
        target = run_dir / "exclusions.jsonl"
        temporary = target.with_suffix(".jsonl.tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            import json
            for exclusion in exclusions:
                handle.write(json.dumps(exclusion, ensure_ascii=False, separators=(",", ":")) + "\n")
        temporary.replace(target)
        emit_jsonl(eligible)
        write_receipt(run_dir, stage, "completed", started, len(inputs), len(eligible), tools=["python-dateutil"], details={
            "as_of_date": as_of.isoformat(),
            "window_start": window_start.isoformat(),
            "window_end": as_of.isoformat(),
            "excluded": len(exclusions),
        })
        return 0
    except Exception as exc:
        return die_from_exception(stage, run_dir, started, exc)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir")
    args = parser.parse_args()
    return filter_records(args.run_dir)


if __name__ == "__main__":
    raise SystemExit(main())

