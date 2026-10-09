from __future__ import annotations

import json
from types import SimpleNamespace
from pathlib import Path

import openai

from src import model_provider
from src.schemas import DecisionBatch


def test_structured_response_retries_malformed_output(monkeypatch, tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    (run_dir / "config").mkdir(parents=True)
    (run_dir / "config" / "models.json").write_text(json.dumps({
        "usd_per_million_input_tokens": None,
        "usd_per_million_output_tokens": None,
    }), encoding="utf-8")
    valid = json.dumps({"decisions": [{
        "item_id": "feed:x", "version_id": "v1", "decision": "reject",
        "reason": "Not relevant.", "piece_ids": [],
    }]})
    responses = iter([
        SimpleNamespace(output_text="not json", usage=None, model="gpt-test", id="r1"),
        SimpleNamespace(output_text=valid, usage=SimpleNamespace(input_tokens=10, output_tokens=5, total_tokens=15), model="gpt-test", id="r2"),
    ])
    calls = []

    class FakeResponses:
        def create(self, **kwargs):
            calls.append(kwargs)
            return next(responses)

    class FakeClient:
        def __init__(self):
            self.responses = FakeResponses()

    monkeypatch.setenv("OPENAI_API_KEY", "test-only")
    monkeypatch.delenv("PS04_MOCK_RESPONSES_DIR", raising=False)
    monkeypatch.setattr(openai, "OpenAI", FakeClient)
    monkeypatch.setattr(model_provider.time, "sleep", lambda _: None)
    parsed, metadata = model_provider.structured_response(
        run_dir=run_dir, stage="select_items", model_name="gpt-test", schema=DecisionBatch,
        instructions="Return JSON.", payload={"items": []}, retries=2,
    )
    assert len(calls) == 2
    assert calls[0]["text"]["format"]["strict"] is True
    assert parsed.decisions[0].decision == "reject"
    assert metadata["usage"]["total_tokens"] == 15
    assert metadata["cost_usd"] is None

