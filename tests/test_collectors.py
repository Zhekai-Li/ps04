from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def make_run(tmp_path: Path, sources: list[dict]) -> Path:
    run = tmp_path / "run"
    (run / "config").mkdir(parents=True)
    (run / "logs").mkdir()
    (run / "run.json").write_text(json.dumps({"run_id":"x","started_at":"2026-10-08T00:00:00Z","as_of_date":"2026-10-08","mode":"example","previous_run_id":None}))
    (run / "config" / "sources.json").write_text(json.dumps(sources))
    return run


def test_empty_success_differs_from_simulated_failure(tmp_path: Path) -> None:
    run = make_run(tmp_path, [])
    success = subprocess.run(["bash", "collectors/fetch_feeds.sh", str(run)], cwd=ROOT, text=True, capture_output=True)
    assert success.returncode == 0 and success.stdout == ""
    failure = subprocess.run(
        ["bash", "collectors/fetch_feeds.sh", str(run)], cwd=ROOT, text=True, capture_output=True,
        env={**os.environ, "PS04_FAIL_COLLECTOR": "feeds"},
    )
    assert failure.returncode == 1 and failure.stdout == ""
    receipts = [json.loads(path.read_text()) for path in (run / "logs").glob("*.json")]
    assert {receipt["status"] for receipt in receipts} == {"completed", "failed"}

