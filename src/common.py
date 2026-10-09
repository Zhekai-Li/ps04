from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]


class PipelineError(Exception):
    """Operational pipeline failure (exit 1)."""


class InputError(Exception):
    """Invalid arguments, configuration, or input (exit 2)."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def repo_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def load_json(path: str | Path) -> Any:
    try:
        with repo_path(path).open(encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise InputError(f"cannot read valid JSON from {path}: {exc}") from exc


def write_json(path: str | Path, value: Any) -> None:
    target = repo_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + f".{uuid.uuid4().hex}.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=False)
        handle.write("\n")
    os.replace(temporary, target)


def iter_jsonl(handle: Iterable[str], label: str = "stdin") -> Iterator[dict[str, Any]]:
    for line_number, raw in enumerate(handle, 1):
        if not raw.strip():
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise InputError(f"{label}:{line_number}: malformed JSON: {exc.msg}") from exc
        if not isinstance(value, dict):
            raise InputError(f"{label}:{line_number}: expected a JSON object")
        yield value


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    target = repo_path(path)
    try:
        with target.open(encoding="utf-8") as handle:
            return list(iter_jsonl(handle, str(path)))
    except OSError as exc:
        raise InputError(f"cannot read {path}: {exc}") from exc


def emit_jsonl(records: Iterable[dict[str, Any]]) -> int:
    count = 0
    for record in records:
        print(json.dumps(record, ensure_ascii=False))
        count += 1
    return count


def canonical_url(url: str) -> str:
    parts = urlsplit(url.strip())
    query = [(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True)
             if not key.lower().startswith("utm_") and key.lower() not in {"fbclid", "gclid"}]
    path = re.sub(r"/{2,}", "/", parts.path).rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), ""))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def stable_item_id(kind: str, url: str, native_id: str | None = None) -> str:
    if native_id:
        return f"{kind}:{native_id}"
    return f"{kind}:{sha256_text(canonical_url(url))[:24]}"


def normalized_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def compute_version_id(record: dict[str, Any], text: str, segments: list[dict[str, Any]] | None) -> str:
    evidence = {
        "item_id": record["item_id"],
        "source_id": record["source_id"],
        "publisher_id": record["publisher_id"],
        "kind": record["kind"],
        "title": normalized_text(record["title"]),
        "url": canonical_url(record["url"]),
        "published_at": record.get("published_at"),
        "media_url": record.get("media_url"),
        "underlying_id": record.get("underlying_id"),
        "text": normalized_text(text),
        "segments": segments,
    }
    payload = json.dumps(evidence, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256_text(payload)


def validate_run_dir(argument: str) -> Path:
    run_dir = repo_path(argument)
    if not run_dir.is_dir() or not (run_dir / "run.json").is_file():
        raise InputError(f"invalid run directory: {argument}")
    return run_dir


def write_receipt(
    run_dir: Path,
    stage: str,
    status: str,
    started_at: str,
    input_count: int | None,
    output_count: int | None,
    *,
    tools: list[str] | None = None,
    models: list[str] | None = None,
    cost_usd: float | None = None,
    cost_estimated: bool = False,
    usage: dict[str, Any] | None = None,
    errors: list[str] | None = None,
    details: dict[str, Any] | None = None,
) -> Path:
    finished_at = utc_now()
    started = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
    finished = datetime.fromisoformat(finished_at.replace("Z", "+00:00"))
    receipt = {
        "stage": stage,
        "status": status,
        "input_count": input_count,
        "output_count": output_count,
        "started_at": started_at,
        "finished_at": finished_at,
        "elapsed_seconds": round((finished - started).total_seconds(), 3),
        "tools": tools or [],
        "models": models or [],
        "usage": usage,
        "cost_usd": cost_usd,
        "cost_estimated": cost_estimated,
        "errors": errors or [],
    }
    if details:
        receipt["details"] = details
    logs = run_dir / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    safe_stage = re.sub(r"[^a-zA-Z0-9_.-]", "_", stage)
    target = logs / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')}-{safe_stage}-{uuid.uuid4().hex[:8]}.json"
    write_json(target, receipt)
    return target


def die_from_exception(stage: str, run_dir: Path | None, started_at: str, exc: Exception) -> int:
    code = 2 if isinstance(exc, InputError) else 1
    print(f"{stage}: {exc}", file=sys.stderr)
    if run_dir is not None:
        write_receipt(run_dir, stage, "invalid" if code == 2 else "failed", started_at, None, None, errors=[str(exc)])
    return code


def monotonic_seconds() -> float:
    return time.monotonic()

