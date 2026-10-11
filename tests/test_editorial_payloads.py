from __future__ import annotations

import json
from pathlib import Path

from src.editorial import _evidence_payload


def base_item(tmp_path: Path) -> dict:
    text_path = tmp_path / "evidence.txt"
    text_path.write_text("x" * 20000, encoding="utf-8")
    return {
        "item_id": "feed:test", "version_id": "v1", "text_path": str(text_path),
        "segments_path": None,
    }


def test_article_payload_is_capped_at_14000_characters(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    (run_dir / "logs").mkdir(parents=True)
    payload = _evidence_payload(run_dir, base_item(tmp_path), stage="select_items")
    assert len(payload["text"]) == 14000


def test_long_media_payload_is_capped_and_not_duplicated(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    (run_dir / "logs").mkdir(parents=True)
    item = base_item(tmp_path)
    item["item_id"] = "podcast:test"
    segment_path = tmp_path / "segments.json"
    segment_path.write_text(json.dumps([
        {"segment_id": f"s-{index:04d}", "start_seconds": index * 12.0, "end_seconds": (index + 1) * 12.0, "text": ("evidence topic " * 30) + str(index)}
        for index in range(300)
    ]), encoding="utf-8")
    item["segments_path"] = str(segment_path)
    payload = _evidence_payload(run_dir, item, stage="select_items", query="evidence topic")
    assert payload["text"] is None
    assert len(payload["segments"]) <= 120
    assert len(json.dumps(payload["segments"], ensure_ascii=False)) <= 30000
    manifests = list((run_dir / "logs" / "excerpt_manifests").glob("*.json"))
    assert len(manifests) == 1
