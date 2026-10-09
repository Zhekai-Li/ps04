from __future__ import annotations

import argparse
import calendar
import os
import sys
from datetime import datetime, timezone
from typing import Any

import feedparser

from .common import InputError, canonical_url, die_from_exception, emit_jsonl, load_json, stable_item_id, utc_now, validate_run_dir, write_receipt
from .schemas import Candidate


def _entry_date(entry: Any) -> str | None:
    value = entry.get("published_parsed") or entry.get("updated_parsed")
    if value:
        return datetime.fromtimestamp(calendar.timegm(value), timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    raw = entry.get("published") or entry.get("updated")
    if raw:
        try:
            from dateutil import parser
            return parser.parse(raw).astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        except (ValueError, TypeError, OverflowError):
            return raw
    return None


def _feed_records(source: dict[str, Any], retrieved_at: str, podcast: bool) -> tuple[list[dict[str, Any]], list[str]]:
    parsed = feedparser.parse(source["url"], request_headers={"User-Agent": "ScholarInTheLoop/1.0 (+https://github.com/Zhekai-Li/ps04)"})
    errors: list[str] = []
    if getattr(parsed, "bozo", False) and not parsed.entries:
        errors.append(f"{source['source_id']}: {parsed.bozo_exception}")
    records: list[dict[str, Any]] = []
    for entry in parsed.entries[: int(source.get("max_items", 8))]:
        link = entry.get("link") or entry.get("id")
        if not link:
            errors.append(f"{source['source_id']}: skipped entry without URL")
            continue
        native_id = str(entry.get("id") or "").strip() or None
        media_url = None
        transcript_url = None
        if podcast:
            for enclosure in entry.get("enclosures", []):
                if enclosure.get("href") and (str(enclosure.get("type", "")).startswith("audio") or media_url is None):
                    media_url = enclosure["href"]
            for candidate in entry.get("links", []):
                rel = str(candidate.get("rel", "")).lower()
                mime = str(candidate.get("type", "")).lower()
                if "transcript" in rel or "transcript" in mime:
                    transcript_url = candidate.get("href")
            podcast_transcript = entry.get("podcast_transcript")
            if isinstance(podcast_transcript, dict):
                transcript_url = podcast_transcript.get("url") or podcast_transcript.get("href") or transcript_url
            elif isinstance(podcast_transcript, list):
                for candidate in podcast_transcript:
                    if isinstance(candidate, dict) and (candidate.get("url") or candidate.get("href")):
                        transcript_url = candidate.get("url") or candidate.get("href")
                        break
        kind = "podcast" if podcast else "feed"
        override = source.get("identity_overrides", {}).get(native_id or canonical_url(link))
        item_id = override or stable_item_id(kind, link, native_id)
        record = {
            "item_id": item_id,
            "source_id": source["source_id"],
            "publisher_id": source["publisher_id"],
            "kind": kind,
            "title": str(entry.get("title") or "Untitled").strip(),
            "url": canonical_url(link),
            "published_at": _entry_date(entry),
            "retrieved_at": retrieved_at,
            "media_url": media_url,
            "underlying_id": source.get("underlying_id_overrides", {}).get(native_id or canonical_url(link)),
            "native_id": native_id,
            "summary": entry.get("summary"),
            "transcript_url": transcript_url,
            "identity_override": override,
        }
        records.append(Candidate.model_validate(record).model_dump())
    return records, errors


def _youtube_records(source: dict[str, Any], retrieved_at: str) -> tuple[list[dict[str, Any]], list[str]]:
    import yt_dlp

    errors: list[str] = []
    options = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "playlistend": int(source.get("max_items", 8)),
        "skip_download": True,
    }
    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(source["url"], download=False)
    except Exception as exc:
        return [], [f"{source['source_id']}: {exc}"]
    entries = info.get("entries") or [info]
    records: list[dict[str, Any]] = []
    detail_options = {"quiet": True, "no_warnings": True, "skip_download": True, "noplaylist": True}
    with yt_dlp.YoutubeDL(detail_options) as detail_ydl:
        for entry in entries:
            if not entry:
                continue
            video_id = entry.get("id")
            url = entry.get("webpage_url") or entry.get("url")
            if video_id and (not url or not str(url).startswith("http")):
                url = f"https://www.youtube.com/watch?v={video_id}"
            if not video_id or not url:
                errors.append(f"{source['source_id']}: skipped entry without native ID or URL")
                continue
            # Flat playlist extraction omits dates on many channels. Fetch each selected video's
            # metadata so an upload cannot enter the corpus with collection time as a fake date.
            if not entry.get("upload_date") and not entry.get("timestamp"):
                try:
                    detail = detail_ydl.extract_info(url, download=False)
                    entry = {**entry, **detail}
                except Exception as exc:
                    errors.append(f"{source['source_id']}:{video_id}: metadata lookup failed: {exc}")
            upload_date = entry.get("upload_date")
            published_at = None
            if upload_date and len(str(upload_date)) == 8:
                published_at = datetime.strptime(str(upload_date), "%Y%m%d").replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
            elif entry.get("timestamp"):
                published_at = datetime.fromtimestamp(float(entry["timestamp"]), timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
            override = source.get("identity_overrides", {}).get(video_id)
            record = {
                "item_id": override or stable_item_id("youtube", url, video_id),
                "source_id": source["source_id"],
                "publisher_id": source["publisher_id"],
                "kind": "youtube",
                "title": str(entry.get("title") or "Untitled").strip(),
                "url": canonical_url(url),
                "published_at": published_at,
                "retrieved_at": retrieved_at,
                "media_url": None,
                "underlying_id": source.get("underlying_id_overrides", {}).get(video_id),
                "native_id": video_id,
                "summary": entry.get("description"),
                "transcript_url": None,
                "identity_override": override,
            }
            records.append(Candidate.model_validate(record).model_dump())
    return records, errors


def collect(kind: str, run_dir_arg: str) -> int:
    stage = f"fetch_{kind}"
    started = utc_now()
    run_dir = None
    try:
        run_dir = validate_run_dir(run_dir_arg)
        if os.environ.get("PS04_FAIL_COLLECTOR") == kind:
            message = f"deliberately simulated {kind} collector failure"
            write_receipt(run_dir, stage, "failed", started, 0, 0, errors=[message], details={"simulated": True})
            print(f"{stage}: {message}", file=sys.stderr)
            return 1
        sources = load_json(run_dir / "config" / "sources.json")
        if not isinstance(sources, list):
            raise InputError("sources.json must contain an array")
        config_kind = {"feeds": "feed", "youtube": "youtube", "podcasts": "podcast"}[kind]
        selected = [source for source in sources if source.get("kind") == config_kind]
        retrieved_at = utc_now()
        all_records: list[dict[str, Any]] = []
        errors: list[str] = []
        for source in selected:
            required = {"source_id", "publisher_id", "kind", "url"}
            if not required.issubset(source):
                errors.append(f"invalid source definition: missing {sorted(required - set(source))}")
                continue
            if config_kind == "youtube":
                records, source_errors = _youtube_records(source, retrieved_at)
            else:
                records, source_errors = _feed_records(source, retrieved_at, config_kind == "podcast")
            all_records.extend(records)
            errors.extend(source_errors)
        emit_jsonl(all_records)
        status = "incomplete" if errors else "completed"
        write_receipt(run_dir, stage, status, started, len(selected), len(all_records), tools=["feedparser" if config_kind != "youtube" else "yt-dlp"], errors=errors)
        for error in errors:
            print(f"{stage}: {error}", file=sys.stderr)
        return 1 if errors else 0
    except Exception as exc:
        return die_from_exception(stage, run_dir, started, exc)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("kind", choices=["feeds", "youtube", "podcasts"])
    parser.add_argument("run_dir")
    args = parser.parse_args()
    return collect(args.kind, args.run_dir)


if __name__ == "__main__":
    raise SystemExit(main())

