from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_inclusive_window_and_all_exclusions(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    (run_dir / "logs").mkdir(parents=True)
    (run_dir / "run.json").write_text(json.dumps({
        "run_id": "filter-test", "started_at": "2026-10-08T12:00:00Z", "as_of_date": "2026-10-08",
        "mode": "example", "previous_run_id": None,
    }), encoding="utf-8")
    result = subprocess.run(
        ["bash", "processing/filter_items.sh", str(run_dir)], cwd=ROOT,
        input=(ROOT / "examples/filter_input.jsonl").read_text(encoding="utf-8"),
        text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    eligible = [json.loads(line)["item_id"] for line in result.stdout.splitlines()]
    exclusions = [json.loads(line) for line in (run_dir / "exclusions.jsonl").read_text().splitlines()]
    expected = json.loads((ROOT / "examples/filter_expected.json").read_text())
    assert eligible == expected["eligible_item_ids"]
    assert [{"item_id": item["item_id"], "reason": item["reason"]} for item in exclusions] == expected["exclusions"]

