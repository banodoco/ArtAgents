---
name: moirae
description: >
  Moirae pack — renders YAML screenplays into terminal-as-cinema videos
  via asciinema, agg, and ffmpeg.  External pack requiring the moirae
  package plus system binaries.
---

# Moirae

The moirae pack renders a YAML screenplay into a scripted terminal/CLI demo
video with typewriter text, simulated agent Q&A, and camera moves.

## Executors

| Executor | What it does |
|---|---|
| `moirae.moirae` | Take a Moirae screenplay YAML file and produce a terminal-as-cinema video via asciinema → agg → ffmpeg. |

## When to use

- Use `moirae.moirae` to turn a screenplay file into a polished terminal demo
  video.

## When NOT to use

- Do not use for trimming real video files — use the `media` pack.
- Do not use for assembling iteration videos from run provenance — use the
  `iteration` pack.

## Requirements

- `moirae` package installed
- `asciinema`, `agg`, and `ffmpeg` binaries on PATH

## CLI quick-start

```bash
python3 -m astrid executors run moirae.moirae -- --screenplay ./demo.yaml --out ./out
```
