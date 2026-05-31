# Render

**Executor**: `rendering.render`  
**Status**: implemented  
**Pipeline step**: 12 (terminal)

Renders a hype timeline + assets pair into `hype.mp4` through the Remotion
compositor. This is the terminal step of the editorial pipeline — it takes
the assembled timeline and asset registry from `video_editing.cut` and
produces the final video file.

## Auto-started HTTP server

Before launching Remotion, the executor starts a local `ThreadingHTTPServer`
on a randomly-chosen free port (127.0.0.1 only). The server implements HTTP
**Range request support** (`_RangeHTTPRequestHandler`) — essential for Remotion's
media components, which seek into long source videos via byte-range requests.
Without Range support, every seek would fully download the source video,
causing timeouts or black/silent frames. The server is auto-started as a daemon
thread and shut down in a `finally` block after Remotion exits.

All asset paths in the registry are rewritten to `http://localhost:<port>/...`
URLs so Remotion can stream them directly.

## Theme support

The executor resolves the timeline's theme slug against the workspace themes
directory (`themes/`), merges any per-run `theme_overrides` from the timeline,
and passes the merged `{id, visual}` dict to Remotion as props. A fallback
`banodoco-default` theme is used when no theme is specified.

## CLI quick-start

```bash
python -m astrid executors run rendering.render -- \
  --timeline ./out/hype.timeline.json \
  --assets ./out/hype.assets.json \
  --out ./out/hype.mp4
```

With a custom theme and composition:

```bash
python -m astrid executors run rendering.render -- \
  --timeline ./out/hype.timeline.json \
  --assets ./out/hype.assets.json \
  --out ./out/hype.mp4 \
  --theme ./themes/my-theme \
  --composition MyComposition
```

With free-space guard:

```bash
python -m astrid executors run rendering.render -- \
  --timeline ./out/hype.timeline.json \
  --assets ./out/hype.assets.json \
  --out ./out/hype.mp4 \
  --min-free-gb 10
```

## Inputs

| Name            | Type | Required | Description                         |
|-----------------|------|----------|-------------------------------------|
| timeline        | file | yes      | Hype timeline JSON                  |
| assets_registry | file | yes      | Hype asset registry JSON            |
| theme           | file | no       | Theme configuration file            |

## Outputs

| Name  | Type | Path               | Description        |
|-------|------|--------------------|--------------------|
| video | file | `{out}/hype.mp4`   | Rendered video     |

## Pipeline position

Step 12 — the terminal step of the editorial pipeline. Runs after
`video_editing.cut` and produces the final rendered video. This is the
last step before optional YouTube upload or Reigh publish.

## Depends on

- `editorial.transcribe`
- `editorial.scenes`
- `editorial.quality_zones`
- `editorial.shots`
- `editorial.triage`
- `understanding.scene_describe`
- `editorial.quote_scout`
- `training.pool_build`
- `training.pool_merge`
- `editorial.arrange`
- `video_editing.cut`
- `editorial.refine`

## Dependencies

- **Remotion** (`npx remotion render`) — must be installed in `remotion/` project dir
- **Node.js / npm** — `npm install` must have been run in the Remotion project
- **ffmpeg/ffprobe** — required by Remotion's render pipeline
