from __future__ import annotations

import argparse
import html
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import requests
import trafilatura

from .common import InputError, PipelineError, compute_version_id, die_from_exception, emit_jsonl, iter_jsonl, normalized_text, relative, repo_path, sha256_text, utc_now, validate_run_dir, write_json, write_receipt
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
    target.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, headers={"User-Agent": USER_AGENT}, stream=True, timeout=(20, 120)) as response:
        response.raise_for_status()
        with target.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    handle.write(chunk)


def _youtube_audio(candidate: Candidate, target: Path) -> None:
    command = [
        "yt-dlp", "--no-playlist", "-x", "--audio-format", "mp3", "--audio-quality", "7",
        "-o", str(target.with_suffix(".%(ext)s")), candidate.url,
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    produced = target.with_suffix(".mp3")
    if completed.returncode != 0 or not produced.is_file():
        raise PipelineError(f"yt-dlp audio retrieval failed: {completed.stderr[-500:]}")
    if produced != target:
        produced.replace(target)


def _group_words(words: Any) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    group: list[Any] = []
    start = 0.0
    for word in words:
        word_start = float(getattr(word, "start", word.get("start") if isinstance(word, dict) else 0.0))
        word_end = float(getattr(word, "end", word.get("end") if isinstance(word, dict) else word_start))
        word_text = str(getattr(word, "word", word.get("word") if isinstance(word, dict) else ""))
        if not group:
            start = word_start
        group.append((word_text, word_start, word_end))
        if word_end - start >= 12.0 or word_text.rstrip().endswith((".", "?", "!")):
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


def _transcribe(candidate: Candidate) -> tuple[list[dict[str, Any]], str]:
    if not os.environ.get("OPENAI_API_KEY"):
        raise PipelineError(f"no captions/transcript for {candidate.item_id}; OPENAI_API_KEY is required for timestamped transcription")
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
    upload_path = media_path
    if media_path.stat().st_size > 24_000_000:
        compressed = media_dir / f"{safe}-compressed.m4a"
        completed = subprocess.run(
            ["ffmpeg", "-y", "-i", str(media_path), "-vn", "-ac", "1", "-b:a", "48k", str(compressed)],
            check=False, capture_output=True, text=True,
        )
        if completed.returncode != 0 or not compressed.is_file() or compressed.stat().st_size > 25_000_000:
            raise PipelineError("media exceeds transcription limit after compression; split it manually")
        upload_path = compressed
    from openai import OpenAI
    with upload_path.open("rb") as audio:
        transcript = OpenAI().audio.transcriptions.create(
            file=audio,
            model="whisper-1",
            response_format="verbose_json",
            timestamp_granularities=["word"],
            prompt="Academic research, artificial intelligence, operations research, scholarly writing, citations.",
        )
    segments = _group_words(transcript.words or [])
    if not segments:
        raise PipelineError(f"transcription returned no timestamped words for {candidate.item_id}")
    return segments, relative(media_path)


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


def _media_segments(candidate: Candidate) -> tuple[list[dict[str, Any]], str | None, str]:
    cache_dir = repo_path("data/cache/transcripts")
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = sha256_text(f"{candidate.kind}:{candidate.native_id or candidate.media_url or candidate.url}")
    cache_path = cache_dir / f"{key}.json"
    if cache_path.is_file():
        value = json.loads(cache_path.read_text(encoding="utf-8"))
        return value["segments"], value.get("media_path"), "transcript-cache"
    media_path = None
    if candidate.kind == "youtube" and candidate.native_id:
        try:
            segments = _youtube_segments(candidate.native_id)
            method = "youtube-captions"
        except Exception:
            segments, media_path = _transcribe(candidate)
            method = "whisper-1"
    elif candidate.transcript_url:
        try:
            segments = _transcript_url_segments(candidate.transcript_url)
            method = "publisher-transcript"
        except Exception:
            segments, media_path = _transcribe(candidate)
            method = "whisper-1"
    else:
        segments, media_path = _transcribe(candidate)
        method = "whisper-1"
    write_json(cache_path, {"segments": segments, "media_path": media_path, "method": method})
    return segments, media_path, method


def extract(run_dir_arg: str) -> int:
    stage = "extract_content"
    started = utc_now()
    run_dir = None
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    input_count = 0
    tools = {"trafilatura", "requests"}
    models: set[str] = set()
    try:
        run_dir = validate_run_dir(run_dir_arg)
        for raw in iter_jsonl(sys.stdin):
            input_count += 1
            try:
                candidate = Candidate.model_validate(raw)
                segments = None
                cache_status = None
                if candidate.kind == "feed":
                    text, cache_status = _article_text(candidate)
                else:
                    segments, _media_path, cache_status = _media_segments(candidate)
                    text = "\n".join(segment["text"] for segment in segments)
                    tools.add("youtube-transcript-api" if cache_status == "youtube-captions" else "ffmpeg")
                    if cache_status == "whisper-1":
                        models.add("whisper-1")
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
                records.append(Item.model_validate(item).model_dump())
            except Exception as exc:
                errors.append(f"{raw.get('item_id', '<unknown>')}: {exc}")
        emit_jsonl(records)
        write_receipt(run_dir, stage, "incomplete" if errors else "completed", started, input_count, len(records), tools=sorted(tools), models=sorted(models), errors=errors)
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

