from __future__ import annotations

import json
import os
import shutil
import subprocess
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str], *, env: dict[str, str], input_text: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, env=env, input=input_text, text=True, capture_output=True, check=False)


def jsonl(values: list[dict]) -> str:
    return "".join(json.dumps(value, separators=(",", ":")) + "\n" for value in values)


def test_offline_editorial_review_and_approval_gate(tmp_path: Path) -> None:
    run_dir = ROOT / "runs" / f"pytest-{uuid.uuid4().hex[:10]}"
    try:
        for directory in ("config", "prompts", "logs", "articles", "video_scripts", "fixtures", "mock"):
            (run_dir / directory).mkdir(parents=True, exist_ok=True)
        metadata = {"run_id": run_dir.name, "started_at": "2026-10-08T00:00:00Z", "as_of_date": "2026-10-08", "mode": "example", "previous_run_id": None}
        (run_dir / "run.json").write_text(json.dumps(metadata), encoding="utf-8")
        for path in (ROOT / "config").iterdir():
            if path.is_file(): shutil.copy2(path, run_dir / "config" / path.name)
        for path in (ROOT / "prompts").iterdir():
            if path.is_file(): shutil.copy2(path, run_dir / "prompts" / path.name)

        items = []
        kinds = ["feed"] * 4 + ["youtube"] * 4 + ["podcast"] * 4
        for index, kind in enumerate(kinds):
            item_id = f"{kind}:test-{index}"
            version_id = f"v{index:02d}"
            quote = f"Exact supporting passage for test item {index}."
            text_path = run_dir / "fixtures" / f"{index}.txt"
            text_path.write_text(quote + " Additional substantive context for inspection.\n", encoding="utf-8")
            segments_path = None
            if kind != "feed":
                segment_path = run_dir / "fixtures" / f"{index}.segments.json"
                segment_path.write_text(json.dumps([{"segment_id": f"s-{index}", "start_seconds": 10.0, "end_seconds": 20.0, "text": quote}]), encoding="utf-8")
                segments_path = segment_path.relative_to(ROOT).as_posix()
            items.append({
                "item_id": item_id, "source_id": f"source-{index}", "publisher_id": f"publisher-{index}", "kind": kind,
                "title": f"Test evidence {index}", "url": f"https://example.test/{index}", "published_at": "2026-10-01T00:00:00Z",
                "retrieved_at": "2026-10-08T00:00:00Z", "media_url": None, "underlying_id": None, "native_id": f"native-{index}",
                "summary": None, "transcript_url": None, "identity_override": None, "version_id": version_id,
                "text_path": text_path.relative_to(ROOT).as_posix(), "segments_path": segments_path, "content_hash": f"hash-{index}", "cache_status": "fixture",
            })
        env = {**os.environ, "PS04_EVIDENCE_DIR": str(tmp_path / "evidence"), "PS04_MOCK_RESPONSES_DIR": str(run_dir / "mock")}
        assert run(["bash", "data/store.sh", "init"], env=env).returncode == 0
        stored = run(["bash", "data/store.sh", "upsert", str(run_dir)], env=env, input_text=jsonl(items))
        assert stored.returncode == 0, stored.stderr
        (run_dir / "eligible.jsonl").write_text(jsonl(items), encoding="utf-8")
        (run_dir / "changes.jsonl").write_text(stored.stdout, encoding="utf-8")

        decisions = [{"item_id": item["item_id"], "version_id": item["version_id"], "decision": "accept", "reason": "Test fixture supplies distinct evidence.", "piece_ids": ["01", "02", "03"]} for item in items]
        (run_dir / "mock" / "select_items.json").write_text(json.dumps({"decisions": decisions}), encoding="utf-8")
        selected = run(["bash", "editorial/select_items.sh", str(run_dir)], env=env, input_text=jsonl(items))
        assert selected.returncode == 0, selected.stderr
        (run_dir / "decisions.jsonl").write_text(selected.stdout, encoding="utf-8")

        briefs = []
        groups = [(0, 4, 8), (1, 5, 9), (2, 6, 10)]
        for piece_number, indexes in enumerate(groups, 1):
            piece_id = f"{piece_number:02d}"
            evidence = []
            for index in indexes:
                locator = {"type": "text", "quote": f"Exact supporting passage for test item {index}."} if items[index]["kind"] == "feed" else {"type": "segment", "segment_id": f"s-{index}"}
                evidence.append({"item_id": items[index]["item_id"], "version_id": items[index]["version_id"], "locator": locator})
            briefs.append({
                "piece_id": piece_id, "title": f"Fixture piece {piece_id}", "question": "What can the fixture establish?",
                "argument": "The fixture demonstrates contract validation.", "synthesis": "Three independent fixture publishers jointly support an inference.",
                "limitations": "The evidence is synthetic and is used only by tests.",
                "claims": [{"claim_id": f"{piece_id}-c1", "statement": "Three fixture sources support the test inference.", "type": "inference", "evidence": evidence}],
            })
        (run_dir / "mock" / "create_briefs.json").write_text(json.dumps({"briefs": briefs}), encoding="utf-8")
        brief_result = run(["bash", "editorial/create_briefs.sh", str(run_dir)], env=env, input_text=selected.stdout)
        assert brief_result.returncode == 0, brief_result.stderr
        (run_dir / "briefs.jsonl").write_text(brief_result.stdout, encoding="utf-8")

        article_pieces = [{"piece_id": brief["piece_id"], "markdown": f"# {brief['title']}\n\n<!-- claim:{brief['piece_id']}-c1 -->\nThis short fixture article exercises evidence consistency.\n\n## Sources\nSee the fixture source notes."} for brief in briefs]
        script_pieces = [{"piece_id": brief["piece_id"], "markdown": f"# {brief['title']}\n\n[claim:{brief['piece_id']}-c1]\nNarrate the fixture claim.\n\n[Visual: evidence trace]\n"} for brief in briefs]
        (run_dir / "mock" / "write_articles.json").write_text(json.dumps({"pieces": article_pieces}), encoding="utf-8")
        (run_dir / "mock" / "write_video_scripts.json").write_text(json.dumps({"pieces": script_pieces}), encoding="utf-8")
        article_result = run(["bash", "content/write_articles.sh", str(run_dir)], env=env, input_text=brief_result.stdout)
        script_result = run(["bash", "content/write_video_scripts.sh", str(run_dir)], env=env, input_text=brief_result.stdout)
        assert article_result.returncode == script_result.returncode == 0, article_result.stderr + script_result.stderr
        (run_dir / "articles.jsonl").write_text(article_result.stdout, encoding="utf-8")
        (run_dir / "video_scripts.jsonl").write_text(script_result.stdout, encoding="utf-8")

        review_result = run(["bash", "review/check_content.sh", str(run_dir)], env=env)
        assert review_result.returncode == 0, review_result.stderr
        review = json.loads(review_result.stdout)
        assert review["passed"] is True
        (run_dir / "review.json").write_text(review_result.stdout, encoding="utf-8")

        missing = run(["bash", "publishing/prepare_package.sh", str(run_dir)], env=env)
        assert missing.returncode == 1
        approval = {"review_id": review["review_id"], "decision": "approve", "reviewer": "Zhekai Li", "reviewed_at": "2026-10-08T12:00:00Z", "notes": "Test-only human fixture approval."}
        (run_dir / "approval.json").write_text(json.dumps(approval), encoding="utf-8")
        packaged = run(["bash", "publishing/prepare_package.sh", str(run_dir)], env=env)
        assert packaged.returncode == 0, packaged.stderr
        links_path = run_dir / "package" / "publication_links.json"
        links = json.loads(links_path.read_text())
        links[0]["substack_url"] = "https://example.test/article"
        links_path.write_text(json.dumps(links), encoding="utf-8")
        assert run(["bash", "publishing/prepare_package.sh", str(run_dir)], env=env).returncode == 0
        assert json.loads(links_path.read_text())[0]["substack_url"] == "https://example.test/article"

        original_id = review["review_id"]
        with (run_dir / "articles" / "01.md").open("a", encoding="utf-8") as handle:
            handle.write("\nEditorial change.\n")
        changed = run(["bash", "review/check_content.sh", str(run_dir)], env=env)
        assert json.loads(changed.stdout)["review_id"] != original_id
        assert run(["bash", "publishing/prepare_package.sh", str(run_dir)], env=env).returncode == 1
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)

