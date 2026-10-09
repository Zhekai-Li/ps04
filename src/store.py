from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import uuid
from pathlib import Path

from pydantic import ValidationError

from .common import InputError, ROOT, die_from_exception, emit_jsonl, iter_jsonl, utc_now, validate_run_dir, write_json, write_receipt
from .schemas import Item

DB_DIR = Path(os.environ.get("PS04_EVIDENCE_DIR", ROOT / "data" / "evidence"))
DB_PATH = DB_DIR / "evidence.db"


def _connect() -> sqlite3.Connection:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _global_receipt(stage: str, started: str, status: str, inputs: int | None, outputs: int | None, errors: list[str] | None = None) -> None:
    target = DB_DIR / "receipts" / f"{utc_now().replace(':', '')}-{stage}-{uuid.uuid4().hex[:8]}.json"
    write_json(target, {
        "stage": stage, "status": status, "input_count": inputs, "output_count": outputs,
        "started_at": started, "finished_at": utc_now(), "tools": ["sqlite3"], "models": [],
        "usage": None, "cost_usd": None, "cost_estimated": False, "errors": errors or [],
    })


def init_store() -> int:
    started = utc_now()
    with _connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS items (
                item_id TEXT PRIMARY KEY,
                latest_version_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS versions (
                item_id TEXT NOT NULL,
                version_id TEXT NOT NULL,
                record_json TEXT NOT NULL,
                first_seen_at TEXT NOT NULL,
                first_run_id TEXT,
                PRIMARY KEY (item_id, version_id),
                FOREIGN KEY (item_id) REFERENCES items(item_id)
            );
            CREATE TABLE IF NOT EXISTS observations (
                observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id TEXT NOT NULL,
                version_id TEXT NOT NULL,
                run_id TEXT,
                retrieved_at TEXT,
                observed_at TEXT NOT NULL,
                UNIQUE(item_id, version_id, run_id, retrieved_at)
            );
            CREATE INDEX IF NOT EXISTS versions_item_idx ON versions(item_id);
            CREATE INDEX IF NOT EXISTS observations_item_idx ON observations(item_id, version_id);
            """
        )
    _global_receipt("store_init", started, "completed", 0, 0)
    return 0


def upsert(run_dir_arg: str) -> int:
    stage = "store_upsert"
    started = utc_now()
    run_dir = None
    try:
        run_dir = validate_run_dir(run_dir_arg)
        run_id = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))["run_id"]
        raw_records = list(iter_jsonl(sys.stdin))
        records = []
        for raw in raw_records:
            try:
                records.append(Item.model_validate(raw).model_dump())
            except ValidationError as exc:
                raise InputError(f"invalid item record: {exc}") from exc
        changes = []
        with _connect() as connection:
            for record in records:
                item_id = record["item_id"]
                version_id = record["version_id"]
                now = utc_now()
                item_row = connection.execute("SELECT latest_version_id FROM items WHERE item_id = ?", (item_id,)).fetchone()
                version_row = connection.execute(
                    "SELECT 1 FROM versions WHERE item_id = ? AND version_id = ?", (item_id, version_id)
                ).fetchone()
                if version_row:
                    change = "unchanged"
                elif item_row is None:
                    connection.execute(
                        "INSERT INTO items(item_id, latest_version_id, created_at, updated_at) VALUES (?, ?, ?, ?)",
                        (item_id, version_id, now, now),
                    )
                    connection.execute(
                        "INSERT INTO versions(item_id, version_id, record_json, first_seen_at, first_run_id) VALUES (?, ?, ?, ?, ?)",
                        (item_id, version_id, json.dumps(record, ensure_ascii=False, separators=(",", ":")), now, run_id),
                    )
                    change = "new"
                else:
                    connection.execute(
                        "INSERT INTO versions(item_id, version_id, record_json, first_seen_at, first_run_id) VALUES (?, ?, ?, ?, ?)",
                        (item_id, version_id, json.dumps(record, ensure_ascii=False, separators=(",", ":")), now, run_id),
                    )
                    connection.execute(
                        "UPDATE items SET latest_version_id = ?, updated_at = ? WHERE item_id = ?",
                        (version_id, now, item_id),
                    )
                    change = "changed"
                connection.execute(
                    "INSERT OR IGNORE INTO observations(item_id, version_id, run_id, retrieved_at, observed_at) VALUES (?, ?, ?, ?, ?)",
                    (item_id, version_id, run_id, record.get("retrieved_at"), now),
                )
                changes.append({"item_id": item_id, "version_id": version_id, "change": change})
        emit_jsonl(changes)
        write_receipt(run_dir, stage, "completed", started, len(records), len(changes), tools=["sqlite3"])
        return 0
    except Exception as exc:
        return die_from_exception(stage, run_dir, started, exc)


def list_latest() -> int:
    started = utc_now()
    try:
        if not DB_PATH.is_file():
            raise InputError("evidence store is not initialized; run: bash data/store.sh init")
        with _connect() as connection:
            rows = connection.execute(
                """SELECT v.record_json FROM items i
                   JOIN versions v ON v.item_id = i.item_id AND v.version_id = i.latest_version_id
                   ORDER BY i.item_id"""
            ).fetchall()
        records = [json.loads(row["record_json"]) for row in rows]
        emit_jsonl(records)
        _global_receipt("store_list", started, "completed", 0, len(records))
        return 0
    except Exception as exc:
        print(f"store_list: {exc}", file=sys.stderr)
        _global_receipt("store_list", started, "invalid" if isinstance(exc, InputError) else "failed", None, None, [str(exc)])
        return 2 if isinstance(exc, InputError) else 1


def get_item(item_id: str, version_id: str | None) -> int:
    started = utc_now()
    try:
        if not DB_PATH.is_file():
            raise InputError("evidence store is not initialized")
        with _connect() as connection:
            if version_id is None:
                row = connection.execute(
                    """SELECT v.record_json FROM items i JOIN versions v
                       ON v.item_id = i.item_id AND v.version_id = i.latest_version_id WHERE i.item_id = ?""",
                    (item_id,),
                ).fetchone()
            else:
                row = connection.execute(
                    "SELECT record_json FROM versions WHERE item_id = ? AND version_id = ?", (item_id, version_id)
                ).fetchone()
        if row is None:
            print(f"store_get: item/version not found: {item_id} {version_id or '<latest>'}", file=sys.stderr)
            _global_receipt("store_get", started, "not_found", 1, 0, ["not found"])
            return 1
        print(row["record_json"])
        _global_receipt("store_get", started, "completed", 1, 1)
        return 0
    except InputError as exc:
        print(f"store_get: {exc}", file=sys.stderr)
        _global_receipt("store_get", started, "invalid", 1, None, [str(exc)])
        return 2
    except Exception as exc:
        print(f"store_get: {exc}", file=sys.stderr)
        _global_receipt("store_get", started, "failed", 1, None, [str(exc)])
        return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init")
    upsert_parser = sub.add_parser("upsert")
    upsert_parser.add_argument("run_dir")
    sub.add_parser("list")
    get_parser = sub.add_parser("get")
    get_parser.add_argument("item_id")
    get_parser.add_argument("version_id", nargs="?")
    args = parser.parse_args()
    if args.command == "init":
        return init_store()
    if args.command == "upsert":
        return upsert(args.run_dir)
    if args.command == "list":
        return list_latest()
    return get_item(args.item_id, args.version_id)


if __name__ == "__main__":
    raise SystemExit(main())

