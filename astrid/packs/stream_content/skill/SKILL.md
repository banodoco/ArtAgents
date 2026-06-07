---
name: "stream-content"
short_description: "Distill long event or stream recordings into content blocks and clip candidates."
description: "Use for stream/event recordings that need holding screens, dead air, real content, and publishable clip candidates separated into reviewable artifacts."
---

# Stream Content

Use this pack when a long event, webinar, livestream, panel, or conference
recording needs to become reviewable publishing material.

## Quick Start

```bash
python3 -m astrid orchestrators run stream_content.distill -- \
  --video sources/event.mp4 \
  --transcript runs/transcript.json \
  --brief brief.md \
  --out runs/stream-content
```

Omit `--transcript` to run `editorial.transcribe` first. Use `--no-scenes` to
skip scene detection. Use `--dry-run` to emit the plan without executing it.

## Output Contract

The orchestrator writes:

- `segment_map.json`: `version`, `source`, `duration`, and gapless `segments`
  with `start`, `end`, `kind`, `label`, `confidence`, and `signals`.
- `segments/`: extracted `content` and `screening` clips plus `segments.json`.
- `candidates.json`: scored clip windows sorted by descending score.
- `review.html`: static local review page with segment links and candidate
  playback.

Use `stream_content.segment_map` directly when you only need the labeled
timeline. Use `stream_content.clip_candidates` directly when you already have a
transcript and optional segment map.

