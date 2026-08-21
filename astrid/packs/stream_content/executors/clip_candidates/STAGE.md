# stream_content.clip_candidates

Use this executor after transcription, optionally after `stream_content.segment_map`,
to produce ranked 20-90 second clip candidates.

```python
import astrid.sdk as sdk
result = sdk.invoke(
    "stream_content.clip_candidates",
    inputs={
        "transcript": "transcript.json",
        "segment_map": "segment_map.json",
        "brief": "brief.md",
    },
    out="runs/stream/candidates.json",
)
```

The output schema is `{"version": 1, "candidates": [...]}` sorted by descending
score. V1 uses local stdlib heuristics only; the scorer is split out so a future
LLM backend can replace or augment it.

