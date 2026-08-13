# Render

**Executor**: `rendering.render`  
**Status**: implemented  
**Pipeline step**: 12 (terminal)

Renders a hype timeline into `hype.mp4` through the backend-neutral
`RenderService`. This executor is the stable facade: it adapts CLI inputs into
a protocol-v1 request while the service resolves a qualified renderer or
planner, validates support and artifacts, performs explicit finalization when
required, and publishes the final video plus provenance. `hybrid` is a legacy
planning policy, not a renderer.

A timeline containing one built-in `audio-reactive-colour` effect and one
coextensive audio clip can be compiled by the FFmpeg renderer to its dedicated
`sendcmd` specialization. The compact effect remains the editable timeline
representation; service selection and request-sensitive support evidence
choose the implementation.

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

With a custom theme and strict qualified renderer:

```bash
python3 -m astrid executors run rendering.render \
  --out ./out \
  --input timeline=./out/hype.timeline.json \
  --input assets_registry=./out/hype.assets.json \
  --input theme=./themes/my-theme \
  --input backend=rendering.remotion
```

The executor writes `./out/hype.mp4` and
`./out/hype.mp4.provenance.json`.

## Inputs

| Name            | Type   | Required | Description |
|-----------------|--------|----------|-------------|
| timeline        | file   | yes      | Hype timeline JSON. Pass as `--input timeline=<path>`. |
| assets_registry | file   | no       | Optional Hype media asset registry JSON. Pass as `--input assets_registry=<path>` when the timeline references media assets. If omitted, the runner supplies an empty registry. |
| theme           | file   | no       | Optional theme configuration. |
| engine          | string | no       | Compatibility selector. Accepts legacy `remotion`, `ffmpeg`, `hybrid`, or a qualified renderer id. Legacy `remotion` preserves support-based FFmpeg auto-routing; `hybrid` selects `rendering.legacy_hybrid`. Do not combine with `backend`. |
| backend         | string | no       | Neutral selector synonym. Prefer a qualified id such as `rendering.remotion` for strict renderer selection. Do not combine with `engine`. |
| backend_config  | JSON   | no       | Object keyed by qualified implementation id. The service forwards only the selected implementation's namespace. |
| output_name     | string | no       | Plain `.mp4` basename; defaults to `hype.mp4`. The video and sidecar outputs use this value. |
| keep_previous_renders | boolean | no | Preserve prior provenance-linked sibling render outputs. |

Qualified renderer selection fails closed when that implementation reports the
request unsupported. Only an explicit planner/fallback policy may route to an
alternative. The legacy `remotion` selector is the one compatibility policy
that tries supported FFmpeg media rendering before Remotion.

## Outputs

| Name       | Type | Path                         | Description |
|------------|------|------------------------------|-------------|
| video      | file | `{out}/{output_name}` | Rendered video; default `{out}/hype.mp4`. |
| provenance | file | `{out}/{output_name}.provenance.json` | Sidecar describing render inputs, plan, resolution, and artifacts. |

## Remotion asset materialization

The shared render-host asset layer resolves local paths relative to the asset
registry, enforces project containment where a project is known, and stages
local/cached files into one invocation-owned directory. Remote URLs with byte
range support stream directly; other URLs are cached, optionally hash-checked,
and staged. The Remotion backend serves only that staging directory on
`127.0.0.1` through an `InvocationAssetServer` with HTTP Range support. The
materializer, server, and stage are cleaned after success or failure.

If `assets_registry` is omitted, the facade creates a temporary empty registry.
This is valid for timelines that do not reference registry media.

## Theme support

The selected Remotion backend resolves the timeline's theme slug against the workspace themes
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

Every successful facade render writes `<output>.provenance.json`. Core owns its
routing and identity fields: request digest, requested policy, planner, ordered
segments and renderer resolution, finalizer, manifest/input/artifact hashes,
trust and support evidence, artifact profiles, audio ownership, normalization,
attachments, and publication output. Backend-private data is preserved only
under `backend_fragments[qualified-id]`. The sidecar also retains the existing
v1 projections for active packs/theme, element resolution, staging, and
specialized render metadata when applicable.

## Authoring a renderer behind this facade

The facade never changes when a new backend appears: a pack contributes a
qualified renderer/planner/finalizer through
`extensions.rendering.{renderers,planners,finalizers}` and `RenderService`
discovers and invokes it. To author one, scaffold the canonical four-file pack
with `python3 -m astrid renderers create <name> <dest>`, implement
`render.py`, run the generated `test_renderer.py`, then `renderers validate` →
trusted `packs install` → `renderers smoke` → `renderers replay <bundle-dir>`
for captured failure bundles (the golden
path in `docs/contracts/render-backend-v1.md`). `render.py` may parse the raw
v1 file protocol or use the public rendering SDK (`astrid.renderer_main` as
the manifest command, `astrid.RenderContext` inside the implementation — see
`docs/reference/sdk.md`). A failed invocation retains a self-contained replay
bundle — resolved request, localized inputs, configuration, redacted logs,
partial result, and the exact replay command — so backend authors can
reproduce failures without rerunning the editorial pipeline.

## Lower-level debug commands

Use direct module execution only when debugging the facade itself. It bypasses
the normal Astrid executor input mapping, still delegates to `RenderService`,
and writes to the exact `--out` path:

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
