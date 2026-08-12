---
name: rendering
description: >
  Rendering pack: the stable rendering.render facade, protocol-v1 Remotion
  and FFmpeg renderers, the legacy hybrid planner, the FFmpeg finalizer, and
  element escape hatches for custom visual effects.
---

# Rendering

The rendering pack turns assembled timelines and optional media asset
registries into finished video files. `rendering.render` is a stable neutral
facade over `RenderService`: the service resolves a renderer or planner from
pack manifests, probes support, invokes protocol-v1 commands, validates media,
completes audio/finalization when required, and publishes the video plus
provenance. `hybrid` is a legacy planning policy, not a renderer.

## Render flow

The core rendering path is:

```
timeline.json + optional assets.json
  → rendering.render facade
  → RenderService
  → renderer or planner → segment renderer(s) → finalizer
  → hype.mp4 + provenance
```

1. **Input**: `hype.timeline.json` (clip sequence, effects, animations,
   transitions) and, when the timeline references media files,
   `hype.assets.json` (asset registry with file paths).
2. **Selection**: The service resolves a qualified renderer/planner through
   trust-aware registries. Legacy `remotion`, `ffmpeg`, and `hybrid` selectors
   are translated only at the compatibility boundary.
3. **Invocation**: The selected protocol command receives one request file
   and writes one authoritative result file in an isolated workspace.
4. **Validation/publication**: Astrid probes the media, validates profile,
   duration, audio, paths, and hashes, then atomically publishes `hype.mp4`
   and `hype.mp4.provenance.json`.

For the built-in `audio-reactive-colour` effect, the FFmpeg renderer exposes a
strict request-sensitive specialization: one full-duration frame-aligned
effect plus one coextensive local audio clip is compiled to FFmpeg `sendcmd`.
The effect parameters remain the editable source of truth; normal service
selection and support evidence decide whether this renderer is used.

## Remotion asset materialization

The shared render-host asset layer materializes an invocation before the
Remotion backend renders:

- Local registry paths resolve relative to the registry file and are staged
  into an invocation-owned directory with project containment checks.
- Remote URLs that advertise byte ranges stream directly. Other URLs are
  fetched through the shared cache, optionally verified by `content_sha256`,
  and staged.
- **Range request support**: Implements HTTP `Range` (byte-range) headers
  with proper `206 Partial Content` responses, `Content-Range`, and
  `Accept-Ranges: bytes` headers. This is essential — Remotion's media
  components seek into long source videos via byte-range requests. Without
  Range support, every seek would fully download the source video, causing
  timeouts or black/silent frames.
- **Lifecycle**: `AssetMaterializer` and `InvocationAssetServer` are owned by
  the Remotion backend invocation and cleaned on success or failure.
- **Exposure**: Only the staging directory is served on `127.0.0.1` using an
  operating-system-assigned port; arbitrary source directories are not served.

When `assets_registry` is omitted, the runner supplies an empty media registry.
This is the normal path for timelines that contain only text, effects,
generated visuals, or other clips that do not reference media entries.

## Theme support

The Remotion backend resolves the timeline's theme slug against the workspace
themes directory (`themes/`), merges any per-run `theme_overrides` from
the timeline, and passes the merged `{id, visual}` dict to Remotion as
props. A fallback `banodoco-default` theme is used when no theme is
specified.

## Executors

| Executor | What it does |
|---|---|
| `rendering.render` | Stable facade that renders a hype timeline through a qualified renderer or planner and writes an MP4 plus provenance. Pipeline step 12 — the terminal step before optional YouTube upload or Reigh publish. |
| `rendering.sprite_sheet` | Generate, slice, and preview GPT Image sprite sheets for batch image work. Produces a sprite atlas (`sprite_sheet.png`), alpha-processed variant, manifest, and MP4 preview. |
| `rendering.html_canvas_effect` | Scaffold a local Remotion HTML-in-canvas effect element. Creates a user-editable effect under `astrid/packs/local/elements/effects/<effect_id>/` with DOM content wrapped in Remotion's `HtmlInCanvas` for optional canvas/WebGL post-processing. |

## Escape hatch: element system

When the standard Remotion timeline rendering doesn't cover your needs,
the rendering pack provides two escape hatches into the element system:

### `rendering.html_canvas_effect`

Scaffolds a custom local effect element that renders DOM content inside
a Remotion `<HtmlInCanvas>` component. Useful for:

- Custom WebGL/shaders overlaid on video
- Glass product cards with HTML content
- Any effect that benefits from DOM content rendered into a canvas for
  post-processing

The scaffolded element lives under `astrid/packs/local/elements/effects/`
and can be freely edited. Once created, it integrates into the standard
Remotion render flow — you reference it by id in the timeline and render
via `rendering.render`.

Local effect, animation, and transition manifests may declare static files with
optional top-level syntax:

```yaml
assets:
  badge: assets/badge.png
  palette: assets/palette.json
```

Each value is a file path relative to the element root. During render, only
declared assets for elements used by the timeline are staged under
`remotion/public/astrid-effects/<render-hash>/<effect-id>/`, exposed to the
component as `params.__astridAssets`, and cleaned up after Remotion exits.

Requires Remotion ≥ 4.0.455.

### `rendering.sprite_sheet`

Generates a sprite sheet (atlas image) using OpenAI GPT Image models.
The sprite sheet is sliced into individual frames and can be used as an
animation source in Remotion compositions. Produces:

- `sprite_sheet.png` — the full sprite atlas
- `sprite_sheet_alpha.png` — alpha-processed variant
- `sprite_manifest.json` — per-frame metadata
- `sprite_preview.mp4` — animated preview of all frames

Requires `OPENAI_API_KEY` and `ffmpeg` on the system path.

## When to use

- Use `rendering.render` to produce the final video from a timeline and,
  only when needed, an asset registry. This is the standard rendering path.
- Use the `audio-reactive-colour` effect for frozen integer-frame colour
  markers. Keep one effect clip rather than expanding each state into a clip;
  the service selects the supporting renderer from request-sensitive evidence.
- Use `rendering.sprite_sheet` when you need to generate a batch of
  related images as a sprite atlas for animation.
- Use `rendering.html_canvas_effect` when you need a custom visual effect
  beyond the built-in element catalog — scaffolds a local Remotion effect
  that you can customize freely.

## Credentials

| Env var | Used by |
|---|---|
| `OPENAI_API_KEY` | sprite_sheet (GPT Image API) |

## CLI quick-start

```bash
# Render a timeline to video
python3 -m astrid executors run rendering.render \
  --out ./out \
  --input timeline=./out/hype.timeline.json

# Render a timeline with a media asset registry
python3 -m astrid executors run rendering.render \
  --out ./out \
  --input timeline=./out/hype.timeline.json \
  --input assets_registry=./out/hype.assets.json

# Render with a custom theme and strict qualified renderer
python3 -m astrid executors run rendering.render \
  --out ./out \
  --input timeline=./out/hype.timeline.json \
  --input assets_registry=./out/hype.assets.json \
  --input theme=./themes/my-theme \
  --input backend=rendering.remotion
```

Use `--input engine=hybrid` only when compatibility with the legacy hybrid
planning policy is required. Legacy `engine=remotion` preserves its historical
support-based FFmpeg auto-route; `backend=rendering.remotion` is strict.

The normal executor CLI writes `./out/hype.mp4` and
`./out/hype.mp4.provenance.json`. The sidecar records the resolved plan,
renderer/planner/finalizer identities, aliases and overrides, manifest and input
hashes, trust/support evidence, artifact profiles, audio ownership,
normalization, attachments, and namespaced backend fragments.

Direct facade-module execution is reserved for debugging executor input
mapping. It still delegates to `RenderService`; it is not a concrete renderer
entry point:

```bash
python3 -m astrid.packs.rendering.executors.render.run \
  --timeline ./out/hype.timeline.json \
  --assets ./out/hype.assets.json \
  --out ./out/hype.mp4
```

Omit `--assets` in direct debug runs only for asset-free timelines.

```bash
python3 -m astrid.packs.rendering.executors.render.run \
  --timeline ./out/hype.timeline.json \
  --out ./out/hype.mp4
```

```bash
# Generate a sprite sheet
python3 -m astrid executors run rendering.sprite_sheet -- \
  --animation "a character waving" \
  --subject "cartoon robot" \
  --reference-image ./robot_ref.png \
  --out-dir ./sprites

# Scaffold a custom HTML canvas effect
python3 -m astrid executors run rendering.html_canvas_effect -- \
  --effect-id glass-product-card --out ./out
```

## Dependencies

- **Remotion** (`npx remotion render`) — must be installed in the `remotion/` project directory
- **Node.js / npm** — `npm install` must have been run in the Remotion project
- **ffmpeg/ffprobe** — required by the FFmpeg renderer/finalizer and media probing

## Adding another renderer

Do not add code to the facade or service. A pack advertises protocol commands
through `extensions.rendering.renderers`, `.planners`, or `.finalizers` and
uses a qualified implementation id owned by that pack. The public contract,
manifest schemas, transport verbs, artifact/audio rules, and worked
third-backend example are in
`docs/contracts/render-backend-v1.md`.
