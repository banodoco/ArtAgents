# Render

**Executor**: `rendering.render`  
**Status**: implemented  
**Pipeline step**: 12 (terminal)

Renders a hype timeline into `hype.mp4` through Remotion, ffmpeg, or the
hybrid renderer. This is the terminal step of the editorial pipeline: it takes
the assembled timeline, optionally an asset registry, and produces the final
video file plus a provenance sidecar.

Normal Astrid usage goes through the first-class executor CLI. The direct
`run.py` entrypoint is a lower-level debug surface for reproducing runner
behavior outside the Astrid executor wrapper.

## CLI quick-start

Render a timeline with no external media registry:

```bash
python3 -m astrid executors run rendering.render \
  --out ./out \
  --input timeline=./out/hype.timeline.json
```

Render a timeline with the optional media asset registry produced by
`video_editing.cut`:

```bash
python3 -m astrid executors run rendering.render \
  --out ./out \
  --input timeline=./out/hype.timeline.json \
  --input assets_registry=./out/hype.assets.json
```

With a custom theme and backend:

```bash
python3 -m astrid executors run rendering.render \
  --out ./out \
  --input timeline=./out/hype.timeline.json \
  --input assets_registry=./out/hype.assets.json \
  --input theme=./themes/my-theme \
  --input engine=hybrid
```

The executor writes `./out/hype.mp4` and
`./out/hype.mp4.provenance.json`.

## Inputs

| Name            | Type   | Required | Description |
|-----------------|--------|----------|-------------|
| timeline        | file   | yes      | Hype timeline JSON. Pass as `--input timeline=<path>`. |
| assets_registry | file   | no       | Optional Hype media asset registry JSON. Pass as `--input assets_registry=<path>` when the timeline references media assets. If omitted, the runner supplies an empty registry. |
| theme           | file   | no       | Optional theme configuration. |
| engine          | string | no       | Render backend. Defaults to Remotion; `ffmpeg` handles media-only timelines, and `hybrid` renders complex windows with Remotion. |

## Outputs

| Name       | Type | Path                         | Description |
|------------|------|------------------------------|-------------|
| video      | file | `{out}/hype.mp4`             | Rendered video. |
| provenance | file | `{out}/hype.mp4.provenance.json` | Sidecar describing the render inputs and resolution state. |

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

If `assets_registry` is omitted, media registry serving is skipped and Remotion
receives an empty registry. This is valid for timelines that use only text,
effects, generated visuals, or other clips that do not reference entries from
`hype.assets.json`.

## Theme support

The executor resolves the timeline's theme slug against the workspace themes
directory (`themes/`), merges any per-run `theme_overrides` from the timeline,
and passes the merged `{id, visual}` dict to Remotion as props. A fallback
`banodoco-default` theme is used when no theme is specified.

## Local effect assets

Element manifests may declare static files needed by an effect, animation, or
transition with optional top-level asset syntax:

```yaml
assets:
  badge: assets/badge.png
  palette: assets/palette.json
```

Asset paths are relative to the element root, must stay inside that root, and
must point to existing files. During render, only declared assets for elements
actually used by the timeline are copied into:

```bash
remotion/public/astrid-effects/<render-hash>/<effect-id>/
```

The renderer injects Remotion-static-file-relative paths into the clip params
under the reserved key `params.__astridAssets`, for example:

```json
{
  "__astridAssets": {
    "badge": "astrid-effects/<render-hash>/my-effect/badge.png"
  }
}
```

The staging directory and temporary props file are cleaned up after Remotion
exits.

## Provenance sidecar

Successful full Remotion renders and hybrid renders write
`<output>.provenance.json`. The sidecar records the active pack order, active
theme, generated registry hash/state, resolved effect ids, source pack ids,
element roots, staged asset ids and paths, and hybrid segment provenance when
applicable. Use it when debugging which local overlay or pack supplied a
rendered effect.

## Lower-level debug commands

Use direct module execution only when debugging the executor itself. It bypasses
the normal Astrid executor input mapping and writes to the exact `--out` path:

```bash
python3 -m astrid.packs.rendering.executors.render.run \
  --timeline ./out/hype.timeline.json \
  --assets ./out/hype.assets.json \
  --out ./out/hype.mp4
```

For an asset-free debug render, omit `--assets`; the direct runner creates a
temporary empty asset registry:

```bash
python3 -m astrid.packs.rendering.executors.render.run \
  --timeline ./out/hype.timeline.json \
  --out ./out/hype.mp4
```

Free-space guard is also a direct-runner debug flag:

```bash
python3 -m astrid.packs.rendering.executors.render.run \
  --timeline ./out/hype.timeline.json \
  --assets ./out/hype.assets.json \
  --out ./out/hype.mp4 \
  --min-free-gb 10
```

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
