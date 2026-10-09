# Media retention and retrieval

Large source audio/video and rendered production files are intentionally excluded from Git.

- Candidates preserve the canonical page and direct enclosure URL when available.
- `items.jsonl` preserves the native ID, canonical URL, content hash, and transcript paths.
- Extraction caches media locally in `data/media/` using a hash of `item_id`.
- YouTube audio can be re-fetched with `yt-dlp --no-playlist -x --audio-format mp3 VIDEO_URL`.
- Podcast audio can be re-fetched from the item’s `media_url`.
- Timestamped transcripts committed under `data/assets/` are the evidence used by claims; re-downloading media must not overwrite them.

If a source disappears, retain the existing evidence version and report the accessibility limitation. Do not silently replace it with a different upload.

