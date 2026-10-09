from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def command(arguments: list[str], *, input_text: str = "", env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(arguments, cwd=ROOT, input=input_text, text=True, capture_output=True, env=env, check=False)


def test_store_examples_and_history(tmp_path: Path) -> None:
    env = {**os.environ, "PS04_EVIDENCE_DIR": str(tmp_path / "evidence")}
    assert command(["bash", "data/store.sh", "init"], env=env).returncode == 0
    run_dir = tmp_path / "run"
    (run_dir / "logs").mkdir(parents=True)
    (run_dir / "run.json").write_text(json.dumps({
        "run_id": "test", "started_at": "2026-10-08T00:00:00Z", "as_of_date": "2026-10-08",
        "mode": "example", "previous_run_id": None,
    }), encoding="utf-8")
    initial = (ROOT / "examples/items.jsonl").read_text(encoding="utf-8")
    result = command(["bash", "data/store.sh", "upsert", str(run_dir)], input_text=initial, env=env)
    assert result.returncode == 0, result.stderr
    assert result.stdout == (ROOT / "examples/initial_changes_expected.jsonl").read_text(encoding="utf-8")

    replay = (ROOT / "examples/replay_items.jsonl").read_text(encoding="utf-8")
    result = command(["bash", "data/store.sh", "upsert", str(run_dir)], input_text=replay, env=env)
    assert result.returncode == 0, result.stderr
    assert result.stdout == (ROOT / "examples/replay_changes_expected.jsonl").read_text(encoding="utf-8")

    latest = command(["bash", "data/store.sh", "get", "podcast:fictional-episode"], env=env)
    old = command([
        "bash", "data/store.sh", "get", "podcast:fictional-episode",
        "8f4fc03210022af1be3798fa7355ae3fa40297873b3ed037420ded36c5849bd5",
    ], env=env)
    assert latest.returncode == old.returncode == 0
    assert json.loads(latest.stdout)["version_id"] == "ed221b9c9d6af72c61b3881e7ef697bf8c4a36bfe6fcffb8e6542953118979c5"
    assert json.loads(old.stdout)["version_id"] == "8f4fc03210022af1be3798fa7355ae3fa40297873b3ed037420ded36c5849bd5"


def test_store_malformed_input_is_exit_two(tmp_path: Path) -> None:
    env = {**os.environ, "PS04_EVIDENCE_DIR": str(tmp_path / "evidence")}
    command(["bash", "data/store.sh", "init"], env=env)
    run_dir = tmp_path / "run"
    (run_dir / "logs").mkdir(parents=True)
    (run_dir / "run.json").write_text('{"run_id":"x"}', encoding="utf-8")
    result = command(["bash", "data/store.sh", "upsert", str(run_dir)], input_text="{bad\n", env=env)
    assert result.returncode == 2

