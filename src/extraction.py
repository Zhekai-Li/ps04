from __future__ import annotations

import argparse
import contextlib
import html
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import requests
import trafilatura

from .common import InputError, PipelineError, compute_version_id, die_from_exception, iter_jsonl, load_json, normalized_text, progress, relative, repo_path, sha256_text, utc_now, validate_run_dir, write_json, write_receipt
from .schemas import Candidate, Item, Segment

USER_AGENT = "ScholarInTheLoop/1.0 (+https://github.com/Zhekai-Li/ps04)"


def _plain_summary(value: str | None) -> str:
    if not value:
        return ""
    extracted = trafilatura.extract(value, include_comments=False, include_tables=False)
    if extracted:
        return extracted
    return normalized_text(html.unescape(re.sub(r"<[^>]+>", " ", value)))


def _article_text(candidate: Candidate) -> tuple[str, str]:
    cache_dir = repo_path("data/cache/http")
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{sha256_text(candidate.url)}.json"
    cached: dict[str, Any] = {}
    if cache_path.is_file():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            cached = {}
    headers = {"User-Agent": USER_AGENT}
    if cached.get("etag"):
        headers["If-None-Match"] = cached["etag"]
    if cached.get("last_modified"):
        headers["If-Modified-Since"] = cached["last_modified"]
    try:
        response = requests.get(candidate.url, headers=headers, timeout=30)
        if response.status_code == 304 and cached.get("text"):
            return cached["text"], "http-304"
        response.raise_for_status()
        text = trafilatura.extract(
            response.text,
            url=candidate.url,
            include_comments=False,
            include_tables=True,
            favor_precision=True,
        ) or _plain_summary(candidate.summary)
        if len(normalized_text(text)) < 120:
            raise PipelineError("retrieved page did not yield substantive text")
        write_json(cache_path, {
            "url": candidate.url,
            "etag": response.headers.get("ETag"),
            "last_modified": response.headers.get("Last-Modified"),
            "text": text,
        })
        return text, "http-200"
    except (requests.RequestException, PipelineError) as exc:
        fallback = cached.get("text") or _plain_summary(candidate.summary)
        if len(normalized_text(fallback)) >= 120:
            return fallback, "cached-fallback"
        raise PipelineError(f"article extraction failed for {candidate.url}: {exc}") from exc


def _youtube_segments(video_id: str) -> list[dict[str, Any]]:
    from youtube_transcript_api import YouTubeTranscriptApi

    transcript = YouTubeTranscriptApi().fetch(video_id, languages=["en", "en-US", "en-GB"])
    segments = []
    for index, snippet in enumerate(transcript, 1):
        start = float(snippet.start)
        duration = float(snippet.duration)
        segments.append(Segment(
            segment_id=f"yt-{index:05d}",
            start_seconds=round(start, 3),
            end_seconds=round(start + duration, 3),
            text=normalized_text(snippet.text),
        ).model_dump())
    if not segments:
        raise PipelineError(f"no captions returned for YouTube video {video_id}")
    return segments


def _download(url: str, target: Path) -> None:
    progress("media", f"Downloading audio to {relative(target)}", status="wait")
    target.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, headers={"User-Agent": USER_AGENT}, stream=True, timeout=(20, 120)) as response:
        response.raise_for_status()
        with target.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    handle.write(chunk)


def _youtube_audio(candidate: Candidate, target: Path) -> None:
    command = [
        sys.executable, "-m", "yt_dlp", "--no-playlist", "-x", "--audio-format", "mp3", "--audio-quality", "7",
        "-o", str(target.with_suffix(".%(ext)s")), candidate.url,
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    produced = target.with_suffix(".mp3")
    if completed.returncode != 0 or not produced.is_file():
        raise PipelineError(f"yt-dlp audio retrieval failed: {completed.stderr[-500:]}")
    if produced != target:
        produced.replace(target)


def _word_value(word: Any, key: str, default: Any) -> Any:
    if isinstance(word, dict):
        return word.get(key, default)
    return getattr(word, key, default)


def _group_words(words: Any) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    group: list[Any] = []
    start = 0.0
    for word in words:
        word_start = float(_word_value(word, "start", 0.0))
        word_end = float(_word_value(word, "end", word_start))
        word_text = str(_word_value(word, "word", _word_value(word, "text", "")))
        if not group:
            start = word_start
        group.append((word_text, word_start, word_end))
        if word_end - start >= 12.0 or (word_end - start >= 6.0 and word_text.rstrip().endswith((".", "?", "!"))):
            result.append(Segment(
                segment_id=f"tr-{len(result) + 1:05d}",
                start_seconds=round(start, 3),
                end_seconds=round(word_end, 3),
                text=normalized_text(" ".join(item[0] for item in group)),
            ).model_dump())
            group = []
    if group:
        result.append(Segment(
            segment_id=f"tr-{len(result) + 1:05d}",
            start_seconds=round(start, 3),
            end_seconds=round(group[-1][2], 3),
            text=normalized_text(" ".join(item[0] for item in group)),
        ).model_dump())
    return result


def _model_revision(model_name: str) -> str:
    cache_root = Path.home() / ".cache" / "huggingface" / "hub" / f"models--{model_name.replace('/', '--')}"
    ref = cache_root / "refs" / "main"
    if ref.is_file():
        try:
            return ref.read_text(encoding="utf-8").strip() or "unknown"
        except OSError:
            pass
    snapshots = sorted((cache_root / "snapshots").glob("*"), key=lambda path: path.stat().st_mtime, reverse=True) if (cache_root / "snapshots").is_dir() else []
    return snapshots[0].name if snapshots else "not-cached"


def _media_duration(path: Path) -> float:
    completed = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        check=False, capture_output=True, text=True,
    )
    if completed.returncode != 0:
        raise PipelineError(f"ffprobe could not determine duration for {path.name}")
    return float(completed.stdout.strip())


def _ensure_media(candidate: Candidate) -> Path:
    media_dir = repo_path("data/media")
    media_dir.mkdir(parents=True, exist_ok=True)
    safe = sha256_text(candidate.item_id)[:24]
    media_path = media_dir / f"{safe}.mp3"
    if not media_path.is_file():
        if candidate.kind == "youtube":
            _youtube_audio(candidate, media_path)
        elif candidate.media_url:
            _download(candidate.media_url, media_path)
        else:
            raise PipelineError(f"no media URL for {candidate.item_id}")
    return media_path


def _mlx_words(result: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(result.get("words"), list):
        return result["words"]
    words: list[dict[str, Any]] = []
    for segment in result.get("segments", []):
        words.extend(segment.get("words") or [])
    return words


def _transcribe_mlx(media_path: Path, model_name: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        import mlx_whisper
    except ImportError as exc:
        raise PipelineError("mlx-whisper is not installed; run bash scripts/setup.sh") from exc
    duration = _media_duration(media_path)
    progress("transcription", f"Transcribing {duration / 60:.1f} minutes locally with {model_name}", status="wait")
    started = time.monotonic()
    with Path(os.devnull).open("w", encoding="utf-8") as sink:
        with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            result = mlx_whisper.transcribe(
                str(media_path), path_or_hf_repo=model_name, word_timestamps=True, verbose=False,
            )
    compute_seconds = round(time.monotonic() - started, 3)
    segments = _group_words(_mlx_words(result))
    if not segments:
        raise PipelineError("MLX transcription returned no timestamped words")
    revision = _model_revision(model_name)
    return segments, {
        "backend": "mlx-whisper", "model": model_name, "model_revision": revision,
        "audio_minutes": round(duration / 60, 3), "compute_seconds": compute_seconds,
        "billing_mode": "local_compute", "cost_usd": 0.0,
    }


def _transcribe_paid_chunks(media_path: Path, usd_per_audio_minute: float | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    from openai import OpenAI

    duration = _media_duration(media_path)
    chunk_seconds = 1200.0
    overlap_seconds = 15.0
    offset = 0.0
    merged_words: list[dict[str, Any]] = []
    last_end = -1.0
    chunk_count = 0
    with tempfile.TemporaryDirectory(prefix="ps04-whisper-chunks-") as temp_dir:
        while offset < duration:
            chunk_count += 1
            chunk_path = Path(temp_dir) / f"chunk-{chunk_count:04d}.m4a"
            length = min(chunk_seconds + overlap_seconds, duration - offset)
            completed = subprocess.run(
                ["ffmpeg", "-y", "-ss", str(offset), "-i", str(media_path), "-t", str(length), "-vn", "-ac", "1", "-b:a", "48k", str(chunk_path)],
                check=False, capture_output=True, text=True,
            )
            if completed.returncode != 0 or not chunk_path.is_file() or chunk_path.stat().st_size >= 25_000_000:
                raise PipelineError(f"could not prepare paid transcription chunk {chunk_count} below 25 MB")
            progress("transcription", f"Paid fallback chunk {chunk_count} at {offset / 60:.1f} minutes", status="wait")
            with chunk_path.open("rb") as audio:
                transcript = OpenAI().audio.transcriptions.create(
                    file=audio, model="whisper-1", response_format="verbose_json",
                    timestamp_granularities=["word"],
                    prompt="Academic research, artificial intelligence, operations research, scholarly writing, citations.",
                )
            for word in transcript.words or []:
                local_start = float(_word_value(word, "start", 0.0))
                local_end = float(_word_value(word, "end", local_start))
                if chunk_count > 1 and local_end <= overlap_seconds:
                    continue
                start = local_start + offset
                end = local_end + offset
                if end <= last_end + 0.01:
                    continue
                merged_words.append({"word": str(_word_value(word, "word", "")), "start": start, "end": end})
                last_end = end
            if offset + length >= duration:
                break
            offset += chunk_seconds
    segments = _group_words(merged_words)
    if not segments:
        raise PipelineError("paid fallback transcription returned no timestamped words")
    return segments, {
        "backend": "openai-audio", "model": "whisper-1", "model_revision": None,
        "audio_minutes": round(duration / 60, 3), "chunk_count": chunk_count,
        "billing_mode": "paid_api_fallback",
        "cost_usd": None if usd_per_audio_minute is None else round(duration / 60 * usd_per_audio_minute, 6),
    }


def _transcribe(candidate: Candidate, model_name: str, usd_per_audio_minute: float | None = None) -> tuple[list[dict[str, Any]], str, dict[str, Any]]:
    media_path = _ensure_media(candidate)
    try:
        segments, metadata = _transcribe_mlx(media_path, model_name)
        method = "mlx-whisper"
    except Exception as mlx_error:
        allow_paid = os.environ.get("PS04_ALLOW_PAID_FALLBACK") == "1" and bool(os.environ.get("OPENAI_API_KEY"))
        if not allow_paid:
            raise PipelineError(f"local MLX transcription failed and paid fallback is disabled: {mlx_error}") from mlx_error
        progress("transcription", f"Local MLX failed ({mlx_error}); using explicitly enabled paid fallback", status="warn")
        segments, metadata = _transcribe_paid_chunks(media_path, usd_per_audio_minute)
        method = "whisper-1-chunked-fallback"
    progress("transcription", f"Created {len(segments)} timestamped segments for {candidate.item_id}", status="ok")
    metadata["method"] = method
    return segments, relative(media_path), metadata


def _transcript_url_segments(url: str) -> list[dict[str, Any]]:
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    response.raise_for_status()
    text = response.text
    segments: list[dict[str, Any]] = []
    try:
        value = response.json()
        candidates = value.get("segments", value) if isinstance(value, dict) else value
        for index, item in enumerate(candidates, 1):
            start = float(item.get("start", item.get("startTime", 0)))
            end = float(item.get("end", item.get("endTime", start)))
            body = item.get("text") or item.get("body")
            if body:
                segments.append(Segment(segment_id=f"pub-{index:05d}", start_seconds=start, end_seconds=end, text=normalized_text(body)).model_dump())
    except (ValueError, TypeError, AttributeError):
        pass
    if not segments and "-->" in text:
        def seconds(value: str) -> float:
            parts = value.strip().replace(",", ".").split(":")
            if len(parts) == 2:
                hours, minutes, secs = 0, int(parts[0]), float(parts[1])
            else:
                hours, minutes, secs = int(parts[-3]), int(parts[-2]), float(parts[-1])
            return hours * 3600 + minutes * 60 + secs

        blocks = re.split(r"\r?\n\s*\r?\n", text.strip())
        for block in blocks:
            lines = [line.strip() for line in block.splitlines() if line.strip()]
            timing_index = next((index for index, line in enumerate(lines) if "-->" in line), None)
            if timing_index is None:
                continue
            match = re.match(r"([^ ]+)\s+-->\s+([^ ]+)", lines[timing_index])
            body = normalized_text(" ".join(lines[timing_index + 1:]))
            if match and body:
                segments.append(Segment(
                    segment_id=f"pub-{len(segments) + 1:05d}",
                    start_seconds=round(seconds(match.group(1)), 3),
                    end_seconds=round(seconds(match.group(2)), 3),
                    text=body,
                ).model_dump())
    if not segments:
        # A transcript without timestamps cannot support the required media locator.
        raise PipelineError(f"publisher transcript at {url} has no machine-readable timestamps")
    return segments


def _transcript_cache_key(candidate: Candidate, backend: str, model: str, revision: str) -> str:
    identity = candidate.native_id or candidate.media_url or candidate.url
    return sha256_text(f"{candidate.kind}:{identity}:{backend}:{model}:{revision}")


def _media_segments(
    candidate: Candidate, model_name: str, usd_per_audio_minute: float | None = None,
) -> tuple[list[dict[str, Any]], str | None, str, dict[str, Any]]:
    cache_dir = repo_path("data/cache/transcripts")
    cache_dir.mkdir(parents=True, exist_ok=True)
    revision = _model_revision(model_name)
    mlx_cache_path = cache_dir / f"{_transcript_cache_key(candidate, 'mlx-whisper', model_name, revision)}.json"
    if revision != "not-cached" and mlx_cache_path.is_file():
        value = json.loads(mlx_cache_path.read_text(encoding="utf-8"))
        progress("transcript", f"MLX cache hit for {candidate.item_id} ({revision[:12]})", status="ok")
        metadata = {**value.get("metadata", {}), "cache_hit": True, "compute_seconds_this_run": 0.0}
        return value["segments"], value.get("media_path"), "mlx-transcript-cache", metadata
    direct_backend = "youtube-captions" if candidate.kind == "youtube" and candidate.native_id else "publisher-transcript" if candidate.transcript_url else None
    if direct_backend:
        direct_path = cache_dir / f"{_transcript_cache_key(candidate, direct_backend, 'none', 'none')}.json"
        if direct_path.is_file():
            value = json.loads(direct_path.read_text(encoding="utf-8"))
            progress("transcript", f"Public transcript cache hit for {candidate.item_id}", status="ok")
            return value["segments"], value.get("media_path"), "transcript-cache", value.get("metadata", {})
    legacy_key = sha256_text(f"{candidate.kind}:{candidate.native_id or candidate.media_url or candidate.url}")
    legacy_path = cache_dir / f"{legacy_key}.json"
    if legacy_path.is_file():
        value = json.loads(legacy_path.read_text(encoding="utf-8"))
        progress("transcript", f"Compatible legacy transcript cache hit for {candidate.item_id}", status="ok")
        metadata = {"backend": value.get("method", "legacy"), "model_revision": "legacy-unknown", "legacy_cache": True}
        return value["segments"], value.get("media_path"), "legacy-transcript-cache", metadata
    media_path = None
    metadata: dict[str, Any] = {"backend": "publisher", "model_revision": None, "cost_usd": 0.0}
    if candidate.kind == "youtube" and candidate.native_id:
        try:
            progress("transcript", f"Requesting YouTube captions for {candidate.native_id}", status="wait")
            segments = _youtube_segments(candidate.native_id)
            method = "youtube-captions"
            metadata = {"backend": method, "model": None, "model_revision": None, "cost_usd": 0.0}
        except Exception:
            progress("transcript", f"Captions unavailable for {candidate.native_id}; falling back to audio transcription", status="warn")
            segments, media_path, metadata = _transcribe(candidate, model_name, usd_per_audio_minute)
            method = metadata["method"]
    elif candidate.transcript_url:
        try:
            progress("transcript", f"Requesting publisher transcript for {candidate.item_id}", status="wait")
            segments = _transcript_url_segments(candidate.transcript_url)
            method = "publisher-transcript"
            metadata = {"backend": method, "model": None, "model_revision": None, "cost_usd": 0.0}
        except Exception:
            progress("transcript", f"Publisher transcript unusable for {candidate.item_id}; falling back to audio transcription", status="warn")
            segments, media_path, metadata = _transcribe(candidate, model_name, usd_per_audio_minute)
            method = metadata["method"]
    else:
        progress("transcript", f"No timestamped transcript for {candidate.item_id}; audio transcription required", status="warn")
        segments, media_path, metadata = _transcribe(candidate, model_name, usd_per_audio_minute)
        method = metadata["method"]
    if metadata.get("backend") == "mlx-whisper":
        revision = metadata["model_revision"]
        cache_path = cache_dir / f"{_transcript_cache_key(candidate, 'mlx-whisper', model_name, revision)}.json"
    else:
        cache_path = cache_dir / f"{_transcript_cache_key(candidate, metadata.get('backend', method), str(metadata.get('model') or 'none'), str(metadata.get('model_revision') or 'none'))}.json"
    write_json(cache_path, {"segments": segments, "media_path": media_path, "method": method, "metadata": metadata})
    return segments, media_path, method, metadata


def extract(run_dir_arg: str) -> int:
    stage = "extract_content"
    started = utc_now()
    run_dir = None
    output_count = 0
    errors: list[str] = []
    input_count = 0
    tools = {"trafilatura", "requests"}
    models: set[str] = set()
    transcription_records: list[dict[str, Any]] = []
    paid_audio_cost = 0.0
    paid_audio_cost_unknown = False
    try:
        run_dir = validate_run_dir(run_dir_arg)
        raw_records = list(iter_jsonl(sys.stdin))
        input_count = len(raw_records)
        model_config = load_json(run_dir / "config" / "models.json")
        transcription_model = model_config["transcription_model"]
        progress(stage, f"Starting {input_count} candidates; every completed item is flushed immediately", status="info")
        for input_index, raw in enumerate(raw_records, 1):
            try:
                candidate = Candidate.model_validate(raw)
                progress(stage, f"{candidate.kind}: {candidate.title[:90]}", current=input_index, total=input_count, status="wait")
                segments = None
                cache_status = None
                if candidate.kind == "feed":
                    text, cache_status = _article_text(candidate)
                else:
                    audio_rate = model_config.get("usd_per_audio_minute")
                    segments, _media_path, cache_status, transcription_meta = _media_segments(
                        candidate, transcription_model, None if audio_rate is None else float(audio_rate),
                    )
                    text = "\n".join(segment["text"] for segment in segments)
                    tools.add("youtube-transcript-api" if cache_status == "youtube-captions" else "ffmpeg")
                    if transcription_meta.get("model"):
                        models.add(transcription_meta["model"])
                    if transcription_meta.get("backend") in {"mlx-whisper", "openai-audio"}:
                        transcription_records.append({"item_id": candidate.item_id, **transcription_meta})
                    if transcription_meta.get("cost_usd"):
                        paid_audio_cost += float(transcription_meta["cost_usd"])
                    if transcription_meta.get("billing_mode") == "paid_api_fallback" and transcription_meta.get("cost_usd") is None:
                        paid_audio_cost_unknown = True
                version_id = compute_version_id(candidate.model_dump(), text, segments)
                asset_dir = repo_path("data/assets") / sha256_text(candidate.item_id)[:20]
                asset_dir.mkdir(parents=True, exist_ok=True)
                text_path = asset_dir / f"{version_id}.txt"
                if not text_path.exists():
                    text_path.write_text(text.rstrip() + "\n", encoding="utf-8")
                segments_path = None
                if segments is not None:
                    segment_file = asset_dir / f"{version_id}.segments.json"
                    if not segment_file.exists():
                        write_json(segment_file, segments)
                    segments_path = relative(segment_file)
                item = {
                    **candidate.model_dump(),
                    "version_id": version_id,
                    "text_path": relative(text_path),
                    "segments_path": segments_path,
                    "content_hash": sha256_text(normalized_text(text)),
                    "cache_status": cache_status,
                }
                validated_item = Item.model_validate(item).model_dump()
                print(json.dumps(validated_item, ensure_ascii=False), flush=True)
                output_count += 1
                progress(stage, f"Saved {candidate.item_id} via {cache_status}", current=input_index, total=input_count, status="ok")
            except Exception as exc:
                errors.append(f"{raw.get('item_id', '<unknown>')}: {exc}")
                progress(stage, f"Skipped {raw.get('item_id', '<unknown>')}: {exc}", current=input_index, total=input_count, status="error")
        write_receipt(
            run_dir, stage, "incomplete" if errors else "completed", started, input_count, output_count,
            tools=sorted(tools), models=sorted(models), errors=errors,
            cost_usd=None if paid_audio_cost_unknown else round(paid_audio_cost, 6), cost_estimated=False,
            details={"transcriptions": transcription_records},
        )
        for error in errors:
            print(f"{stage}: {error}", file=sys.stderr)
        return 1 if errors else 0
    except Exception as exc:
        return die_from_exception(stage, run_dir, started, exc)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir")
    args = parser.parse_args()
    return extract(args.run_dir)


if __name__ == "__main__":
    raise SystemExit(main())

