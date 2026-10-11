from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from src import model_provider
from src.editorial import _validate_brief_support
from src.common import PipelineError, die_from_exception
from src.schemas import Claim, DecisionBatch


def make_run(tmp_path: Path, attempts: int = 2) -> Path:
    run_dir = tmp_path / "run"
    (run_dir / "config").mkdir(parents=True)
    (run_dir / "config" / "models.json").write_text(json.dumps({
        "text_backend": "codex-cli", "reasoning_effort": "high", "max_model_attempts": attempts,
        "usd_per_million_input_tokens": None, "usd_per_million_output_tokens": None,
    }), encoding="utf-8")
    return run_dir


def decision_json(item_id: str = "feed:x") -> str:
    return json.dumps({"decisions": [{
        "item_id": item_id, "version_id": "v1", "decision": "reject",
        "reason": "Not relevant.", "piece_ids": [],
    }]})


def fake_codex(monkeypatch: pytest.MonkeyPatch, outputs: list[str], *, returncodes: list[int] | None = None, event_type: str = "agent_message") -> list[list[str]]:
    calls: list[list[str]] = []
    queue = iter(outputs)
    codes = iter(returncodes or [0] * len(outputs))

    def run(command, **kwargs):
        if command == ["codex", "--version"]:
            return subprocess.CompletedProcess(command, 0, "codex-cli test\n", "")
        calls.append(command)
        output = next(queue)
        response_path = Path(command[command.index("--output-last-message") + 1])
        response_path.write_text(output, encoding="utf-8")
        events = [
            {"type": "thread.started", "thread_id": f"thread-{len(calls)}"},
            {"type": "item.completed", "item": {"type": event_type, "id": "item-1"}},
            {"type": "turn.completed", "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}},
        ]
        code = next(codes)
        return subprocess.CompletedProcess(command, code, "\n".join(json.dumps(event) for event in events), "quota exceeded" if code else "")

    monkeypatch.setattr(model_provider.subprocess, "run", run)
    return calls


def test_codex_retries_invalid_json_and_audits(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    run_dir = make_run(tmp_path)
    calls = fake_codex(monkeypatch, ["not json", decision_json()])
    parsed, metadata = model_provider.structured_response(
        run_dir=run_dir, stage="select_items", model_name="gpt-test", schema=DecisionBatch,
        instructions="Return JSON.", payload={"items": []},
    )
    assert len(calls) == 2
    assert "--ephemeral" in calls[0] and "read-only" in calls[0]
    assert parsed.decisions[0].decision == "reject"
    assert metadata["usage"]["total_tokens"] == 15
    assert metadata["cost_usd"] is None
    audit = run_dir / metadata["audit_path"]
    assert json.loads((audit / "attempt-1" / "validation.json").read_text())["valid"] is False
    assert json.loads((audit / "attempt-2" / "validation.json").read_text())["valid"] is True


def test_semantic_error_enters_repair_loop(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    run_dir = make_run(tmp_path)
    fake_codex(monkeypatch, [decision_json("feed:bad"), decision_json("feed:good")])

    def validate(batch: DecisionBatch) -> None:
        if batch.decisions[0].item_id != "feed:good":
            raise PipelineError("wrong evidence version")

    parsed, _ = model_provider.structured_response(
        run_dir=run_dir, stage="select_items", model_name="gpt-test", schema=DecisionBatch,
        instructions="Return JSON.", payload={}, semantic_validator=validate,
    )
    assert parsed.decisions[0].item_id == "feed:good"


@pytest.mark.parametrize("returncode, event_type, message", [
    (1, "agent_message", "quota exceeded"),
    (0, "command_execution", "invoked a tool"),
])
def test_codex_failures_preserve_usage_and_never_pay_by_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, returncode: int, event_type: str, message: str,
) -> None:
    run_dir = make_run(tmp_path, attempts=1)
    fake_codex(monkeypatch, [decision_json()], returncodes=[returncode], event_type=event_type)
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-be-used")
    monkeypatch.delenv("PS04_ALLOW_PAID_FALLBACK", raising=False)
    monkeypatch.setattr(model_provider, "_paid_api_attempt", lambda **kwargs: pytest.fail("paid API was called"))
    with pytest.raises(model_provider.ModelCallError, match=message) as raised:
        model_provider.structured_response(
            run_dir=run_dir, stage="select_items", model_name="gpt-test", schema=DecisionBatch,
            instructions="Return JSON.", payload={},
        )
    details = raised.value.receipt_metadata["details"]["model_call"]
    assert details["usage"]["total_tokens"] == 15
    assert details["response_id"] == "thread-1"


def test_timeout_and_malformed_events(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    run_dir = make_run(tmp_path, attempts=1)

    def timeout(command, **kwargs):
        if command == ["codex", "--version"]:
            return subprocess.CompletedProcess(command, 0, "codex-cli test", "")
        raise subprocess.TimeoutExpired(command, 1)

    monkeypatch.setattr(model_provider.subprocess, "run", timeout)
    with pytest.raises(model_provider.ModelCallError, match="timed out"):
        model_provider.structured_response(
            run_dir=run_dir, stage="x", model_name="gpt-test", schema=DecisionBatch,
            instructions="x", payload={},
        )


def test_failed_model_call_writes_usage_to_receipt(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    run_dir = make_run(tmp_path, attempts=1)
    (run_dir / "logs").mkdir()
    fake_codex(monkeypatch, [decision_json()], returncodes=[1])
    with pytest.raises(model_provider.ModelCallError) as raised:
        model_provider.structured_response(
            run_dir=run_dir, stage="select_items", model_name="gpt-test", schema=DecisionBatch,
            instructions="x", payload={},
        )
    assert die_from_exception("select_items", run_dir, "2026-10-09T00:00:00Z", raised.value) == 1
    receipt = json.loads(next((run_dir / "logs").glob("*.json")).read_text())
    assert receipt["models"] == ["gpt-test"]
    assert receipt["usage"]["total_tokens"] == 15
    assert receipt["details"]["model_call"]["response_id"] == "thread-1"


def test_claim_id_schema_is_lowercase_and_nonzero() -> None:
    reference = {"item_id": "x", "version_id": "v", "locator": {"type": "text", "quote": "q"}}
    assert Claim.model_validate({"claim_id": "01-c1", "statement": "s", "type": "reported_fact", "evidence": [reference]})
    with pytest.raises(ValueError):
        Claim.model_validate({"claim_id": "01-C1", "statement": "s", "type": "reported_fact", "evidence": [reference]})
    with pytest.raises(ValueError):
        Claim.model_validate({"claim_id": "01-c0", "statement": "s", "type": "reported_fact", "evidence": [reference]})


def test_duplicate_claim_id_still_fails_semantic_validation(tmp_path: Path) -> None:
    evidence_index = {}
    accepted = {}
    references = []
    for index, kind in enumerate(("feed", "youtube", "podcast"), 1):
        path = tmp_path / f"{index}.txt"
        path.write_text("exact quote", encoding="utf-8")
        key = (f"item-{index}", f"v{index}")
        evidence_index[key] = {"publisher_id": f"publisher-{index}", "kind": kind, "text_path": str(path), "segments_path": None}
        accepted[key] = {"publisher_id": f"publisher-{index}", "piece_ids": ["01", "02", "03"]}
        references.append({"item_id": key[0], "version_id": key[1], "locator": {"type": "text", "quote": "exact quote"}})
    briefs = []
    for piece_id in ("01", "02", "03"):
        claims = [{"claim_id": f"{piece_id}-c1", "evidence": references}]
        if piece_id == "01":
            claims.append({"claim_id": "01-c1", "evidence": references})
        briefs.append({"piece_id": piece_id, "claims": claims})
    with pytest.raises(PipelineError, match="duplicate"):
        _validate_brief_support(briefs, accepted, evidence_index)
