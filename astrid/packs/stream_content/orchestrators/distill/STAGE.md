# stream_content.distill

Use this orchestrator for long recordings from events, streams, panels, demos,
or webinars that need to become reviewable publishing material.

```python
import astrid.sdk as sdk
result = sdk.invoke(
    "stream_content.distill",
        kind="orchestrator", project="demo",
    inputs={
        "video": "sources/event.mp4",
        "transcript": "runs/transcript.json",
        "brief": "brief.md",
    },
)
```

Outputs:

- `segment_map.json`: gapless holding/dead/content/screening timeline.
- `segments/`: extracted `content` and `screening` files plus `segments.json`.
- `candidates.json`: scored candidate clips.
- `review.html`: static self-contained review page.

Use `--dry-run` to emit `plan.json` only. Use `--no-scenes` to skip scene
detection.

