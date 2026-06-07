# stream_content.segment_map

Use this executor to turn a long stream recording into a complete labeled
timeline.

```bash
python3 -m astrid executors run stream_content.segment_map -- \
  --video source.mp4 \
  --transcript transcript.json \
  --scenes scenes.json \
  --out runs/stream/segment_map.json
```

It writes `{out}/segment_map.json` (or the explicit `--out` file) with
`version`, `source`, `duration`, and gapless `segments`.

