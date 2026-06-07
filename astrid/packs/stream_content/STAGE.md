# stream_content

The stream_content pack turns long stream or event recordings into reviewable
publishing material.

Primary entrypoint:

```bash
python3 -m astrid orchestrators run stream_content.distill -- \
  --video sources/event.mp4 \
  --transcript runs/transcript.json \
  --out runs/stream-content
```

Capabilities:

- `stream_content.segment_map`: gapless timeline with holding/dead/content/screening labels.
- `stream_content.clip_candidates`: ranked 20-90 second transcript clip windows.
- `stream_content.distill`: full local workflow and review page.

