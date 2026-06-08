---
name: text_analysis
description: >
  Text Analysis pack — simple text file reading, summarization, and
  verdict generation.  Single-orchestrator pack for lightweight text
  processing.
---

# Text Analysis

The text_analysis pack provides a single orchestrator for reading text files,
summarizing content, and writing structured verdict outputs.

## Orchestrators

| Orchestrator | What it does |
|---|---|
| `text_analysis.summarize` | Read the bundled sample text fixture, emit content and summary metadata, and write a one-line verdict artifact. |

## When to use

- Use `text_analysis.summarize` for simple text file reading, summarization,
  and verdict generation.

## When NOT to use

- Do not use for video, audio, or image processing — this pack is text-only.

## CLI quick-start

```bash
python3 -m astrid orchestrators run text_analysis.summarize --out ./out
```
