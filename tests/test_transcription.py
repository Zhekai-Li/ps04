from __future__ import annotations

import sys
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import openai

from src import extraction
from src.common import PipelineError
from src.schemas import Candidate


def candidate() -> Candidate:
    return Candidate.model_validate({
        "item_id": "podcast:test", "source_id": "source", "publisher_id": "publisher",
        "kind": "podcast", "title": "Test", "url": "https://example.test/episode",
        "published_at": "2026-10-01T00:00:00Z", "retrieved_at": "2026-10-09T00:00:00Z",
        "media_url": "https://example.test/audio.mp3", "underlying_id": None, "native_id": "episode-1",
    })


def test_group_words_uses_global_timestamps_and_stable_ids() -> None:
    words = [{"word": f"word{index}", "start": 100.0 + index, "end": 100.8 + index} for index in range(26)]
    segments = extraction._group_words(words)
    assert segments[0]["segment_id"] == "tr-00001"
    assert segments[0]["start_seconds"] == 100.0
    assert 11.0 <= segments[0]["end_seconds"] - segments[0]["start_seconds"] <= 13.0
    assert segments[-1]["end_seconds"] == 125.8


def test_mlx_transcription_requests_word_timestamps(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    captured = {}

    def transcribe(path, **kwargs):
        print("third-party progress that must not reach JSONL stdout")
        captured.update(kwargs)
        return {"segments": [{"words": [
            {"word": "hello", "start": 0.0, "end": 6.1},
            {"word": "world.", "start": 6.1, "end": 12.0},
        ]}]}

    monkeypatch.setitem(sys.modules, "mlx_whisper", SimpleNamespace(transcribe=transcribe))
    monkeypatch.setattr(extraction, "_media_duration", lambda path: 120.0)
    monkeypatch.setattr(extraction, "_model_revision", lambda model: "revision-123")
    segments, metadata = extraction._transcribe_mlx(tmp_path / "audio.mp3", "mlx-community/whisper-turbo")
    assert captured["word_timestamps"] is True
    assert segments[0]["start_seconds"] == 0.0 and segments[-1]["end_seconds"] == 12.0
    assert metadata["model_revision"] == "revision-123"
    assert metadata["audio_minutes"] == 2.0
    assert capsys.readouterr().out == ""


def test_model_revision_changes_transcript_cache_key() -> None:
    item = candidate()
    first = extraction._transcript_cache_key(item, "mlx-whisper", "model-a", "rev-1")
    assert first != extraction._transcript_cache_key(item, "mlx-whisper", "model-a", "rev-2")
    assert first != extraction._transcript_cache_key(item, "mlx-whisper", "model-b", "rev-1")


def test_paid_audio_fallback_requires_explicit_switch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(extraction, "_ensure_media", lambda item: tmp_path / "audio.mp3")
    monkeypatch.setattr(extraction, "_transcribe_mlx", lambda path, model: (_ for _ in ()).throw(RuntimeError("mlx failed")))
    monkeypatch.setattr(extraction, "_transcribe_paid_chunks", lambda path: pytest.fail("paid audio API was called"))
    monkeypatch.setenv("OPENAI_API_KEY", "present-but-insufficient")
    monkeypatch.delenv("PS04_ALLOW_PAID_FALLBACK", raising=False)
    with pytest.raises(PipelineError, match="paid fallback is disabled"):
        extraction._transcribe(candidate(), "mlx-community/whisper-turbo")


def test_extract_loads_snapshotted_transcription_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    (run_dir / "config").mkdir(parents=True)
    (run_dir / "logs").mkdir()
    (run_dir / "run.json").write_text(json.dumps({"run_id": "test"}), encoding="utf-8")
    (run_dir / "config" / "models.json").write_text(json.dumps({
        "transcription_model": "mlx-community/whisper-turbo",
    }), encoding="utf-8")
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    assert extraction.extract(str(run_dir)) == 0


def test_paid_chunk_fallback_offsets_time_and_deduplicates_overlap(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    media = tmp_path / "long.mp3"
    media.write_bytes(b"fixture")
    monkeypatch.setattr(extraction, "_media_duration", lambda path: 2500.0)

    def fake_run(command, **kwargs):
        Path(command[-1]).write_bytes(b"chunk")
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(extraction.subprocess, "run", fake_run)

    class Transcriptions:
        def create(self, **kwargs):
            return SimpleNamespace(words=[
                {"word": "overlap", "start": 0.0, "end": 5.0},
                {"word": "kept.", "start": 16.0, "end": 20.0},
            ])

    class Client:
        def __init__(self):
            self.audio = SimpleNamespace(transcriptions=Transcriptions())

    monkeypatch.setattr(openai, "OpenAI", Client)
    segments, metadata = extraction._transcribe_paid_chunks(media, 0.01)
    combined = " ".join(segment["text"] for segment in segments)
    assert combined.count("overlap") == 1
    assert max(segment["end_seconds"] for segment in segments) == 2420.0
    assert metadata["chunk_count"] == 3
    assert metadata["cost_usd"] == pytest.approx(0.416667)
