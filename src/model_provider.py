from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from .common import InputError, PipelineError, load_json

T = TypeVar("T", bound=BaseModel)


def _estimate_cost(model_config: dict[str, Any], usage: dict[str, Any]) -> tuple[float | None, bool]:
    input_rate = model_config.get("usd_per_million_input_tokens")
    output_rate = model_config.get("usd_per_million_output_tokens")
    if input_rate is None or output_rate is None:
        return None, False
    value = (usage.get("input_tokens", 0) * float(input_rate) + usage.get("output_tokens", 0) * float(output_rate)) / 1_000_000
    return round(value, 6), True


def structured_response(
    *,
    run_dir: Path,
    stage: str,
    model_name: str,
    schema: type[T],
    instructions: str,
    payload: dict[str, Any],
    retries: int = 2,
) -> tuple[T, dict[str, Any]]:
    mock_dir = os.environ.get("PS04_MOCK_RESPONSES_DIR")
    if mock_dir:
        path = Path(mock_dir) / f"{stage}.json"
        if not path.is_file():
            raise PipelineError(f"mock response missing: {path}")
        try:
            parsed = schema.model_validate(load_json(path))
        except ValidationError as exc:
            raise InputError(f"invalid mock response for {stage}: {exc}") from exc
        return parsed, {"provider": "mock", "model": model_name, "usage": None, "cost_usd": 0.0, "cost_estimated": False}

    if not os.environ.get("OPENAI_API_KEY"):
        raise PipelineError("OPENAI_API_KEY is required (or set PS04_MOCK_RESPONSES_DIR for labeled offline tests)")

    from openai import OpenAI

    client = OpenAI()
    model_config = load_json(run_dir / "config" / "models.json")
    response_schema = schema.model_json_schema()
    request = {
        "model": model_name,
        "instructions": instructions,
        "input": json.dumps(payload, ensure_ascii=False),
        "text": {
            "format": {
                "type": "json_schema",
                "name": stage.replace("-", "_")[:64],
                "strict": True,
                "schema": response_schema,
            }
        },
    }
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            response = client.responses.create(**request)
            if not response.output_text:
                raise PipelineError("model returned no structured output (possible refusal)")
            parsed = schema.model_validate_json(response.output_text)
            usage_obj = getattr(response, "usage", None)
            usage = {
                "input_tokens": getattr(usage_obj, "input_tokens", 0),
                "output_tokens": getattr(usage_obj, "output_tokens", 0),
                "total_tokens": getattr(usage_obj, "total_tokens", 0),
            }
            cost, estimated = _estimate_cost(model_config, usage)
            return parsed, {
                "provider": "openai-responses",
                "model": getattr(response, "model", model_name),
                "response_id": getattr(response, "id", None),
                "usage": usage,
                "cost_usd": cost,
                "cost_estimated": estimated,
            }
        except (ValidationError, json.JSONDecodeError, PipelineError, Exception) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
                continue
    raise PipelineError(f"structured model call failed after {retries + 1} attempts: {last_error}")

