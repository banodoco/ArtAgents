---
name: rendering
description: >
  Rendering pack: the stable rendering.render facade, protocol-v1 Remotion,
  FFmpeg, and Three.js renderers, the FFmpeg finalizer, and
  element escape hatches for custom visual effects.
---

# Rendering

The rendering pack turns assembled timelines and optional media asset
registries into finished video files. `rendering.render` is a stable neutral
facade over `RenderService`: the service resolves a renderer or planner from
pack manifests, probes support, invokes protocol-v1 commands, validates media,
completes audio/finalization when required, and publishes the video plus
provenance. Select implementations by their qualified renderer IDs; shorthand
and automatic fallback are unavailable.

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
2. **Selection**: The service resolves a qualified renderer through
   trust-aware registries. Unsupported selectors fail closed with the
   canonical renderer IDs in the recovery details.
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

## Auto-started HTTP server

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
| `rendering.render` | Stable facade that renders a hype timeline through a qualified renderer or planner and writes an MP4 plus provenance. Pipeline step 12 — the terminal step before optional YouTube upload. |
| `rendering.timeline_visualize` | Read managed timeline event logs without mutation and emit a deterministic, run-owned agent evidence pack with JSON, Markdown, PNG, SVG, and navigation actions. |
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

Requires Remotion ≥ 4.0.509 (pinned; 4.0.509+ replaces the extract-zip
dependency that broke Chrome Headless Shell extraction on Node ≥ 26).

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

- Use `rendering.render` with `timeline` to produce the final video from an
  explicit exported or pipeline-produced timeline JSON file and, only when
  needed, an asset registry. Use its mutually exclusive `timeline_ref` input
  (or `astrid timelines render <ref>`) for a canonical kernel slug/UUID/ULID;
  add `expected_version` when the observed stream head must not change.
- Use the `audio-reactive-colour` effect for frozen integer-frame colour
  markers. Keep one effect clip rather than expanding each state into a clip;
  the service selects the supporting renderer from request-sensitive evidence.
- Use `rendering.timeline_visualize` to inspect one or all runtime-managed
  timelines through a deterministic evidence pack. It owns retention through
  run metadata and never mutates timeline manifests.
- Use `rendering.sprite_sheet` when you need to generate a batch of
  related images as a sprite atlas for animation.
- Use `rendering.html_canvas_effect` when you need a custom visual effect
  beyond the built-in element catalog — scaffolds a local Remotion effect
  that you can customize freely.

## Credentials

| Env var | Used by |
|---|---|
| `OPENAI_API_KEY` | sprite_sheet (GPT Image API) |

## Quick-start

Before invoking the renderer, make the timeline visibly renderable. The
smallest known-good file has root `clips`, a `visual` track, structured text
with `clipType: "text"`, and an explicit MP4 output contract:

```json
{"tracks":[{"id":"cards","kind":"visual","label":"Cards"}],
 "clips":[{"id":"title","at":0,"track":"cards","clipType":"text","hold":2,
   "text":{"content":"HELLO ASTRID","fontSize":64,"color":"#ffffff","align":"center"}}],
 "output":{"resolution":"640x360","fps":30,"file":"title.mp4"}}
```

Do not write a text-shaped clip without `clipType: "text"`: Astrid rejects
that ambiguous shape before renderer admission instead of producing an empty
or black frame. The clip-level `effects` field is reserved for fade timing
(`{"fade_in": 0.2, "fade_out": 0.2}` or fade-only objects). A reusable visual
element is a clip whose `clipType` is the registered effect id and whose
arguments live in `params`; an unknown id is rejected before managed render
admission. The default H.264/AAC render also requires an `.mp4`
`output_name` (or `out_path` basename); a `.mov`, extensionless, or otherwise
incompatible name is rejected before spending a render attempt.

An explicit profile is the flat RenderProfile v1 wire object, not nested
`video` and `audio` mappings. This complete profile requests the default
1920x1080@30 Remotion MP4 contract. It must match the authoritative theme
canvas; set `theme_overrides.visual.canvas` when intentionally targeting a
different size:

```json
{"width":1920,"height":1080,"fps_rational":[30,1],"time_base":[1,90000],"container":"mp4","video_codec":"h264","video_profile":null,"video_level":null,"pixel_format":"yuv420p","audio_codec":"aac","audio_sample_rate":48000,"audio_channel_layout":"stereo","duration_tolerance":1}
```

Required fields: `width`, `height`, `fps_rational`, `time_base`, `container`,
`video_codec`, `video_profile`, `video_level`, `pixel_format`, and
`duration_tolerance`. Supply `audio_codec`, `audio_sample_rate`, and
`audio_channel_layout` together or omit all three. Remotion always muxes an
AAC track, so its explicit profile should include the trio shown above.
Managed-ref invocation rejects missing, unknown, and invalid profile fields
before kernel admission; it does not normalize a nested convenience shape.

```python
# Render a timeline to video
import astrid.sdk as sdk
result = sdk.invoke(
    "rendering.render",
    inputs={"timeline": "./out/hype.timeline.json"},
    out="./out",
)

# Render a canonical managed timeline with a stream-head CAS guard
result = sdk.invoke(
    "rendering.render",
    project="demo",
    inputs={"timeline_ref": "main", "expected_version": 4},
)

# Render a timeline with a media asset registry
result = sdk.invoke(
    "rendering.render",
    inputs={"timeline": "./out/hype.timeline.json", "assets_registry": "./out/hype.assets.json"},
    out="./out",
)

# Render with a custom theme and strict qualified renderer
result = sdk.invoke(
    "rendering.render",
    inputs={
        "timeline": "./out/hype.timeline.json",
        "assets_registry": "./out/hype.assets.json",
        "theme": "./themes/my-theme",
        "backend": "rendering.remotion",
    },
    out="./out",
)
```

```python
# Inspect a managed or kernel timeline (kernel-owned CAS evidence pack)
result = sdk.invoke(
    "rendering.timeline_visualize",
    kind="executor",
    project="demo",  # supplies the owning project and managed output root
    inputs={
        "timeline_slug": "main",  # UUID, ULID, or slug; omit for the default
        "formats": ["png", "svg", "md"],
        "layout": "both",
    },
)
print(result.ok, result.outputs)

# The same default/slug/UUID/ULID selectors resolve the runtime timeline
# immediately after the public
# `client.timelines.create/save` journey; no hand-authored event log is
# required. Kernel config is materialized privately and pinned to the real
# immutable stream head version/hash for this run.
# A project-owned registry `media_id` is enough for visualization to derive
# and verify the current managed-CAS locator; do not copy `.astrid/media`
# hash-fanout paths into timeline state. Explicit `file` remains appropriate
# for project-owned legacy/external sources.

```

The SDK field is plural (`formats`), while the direct runner uses repeatable
singular `--format png --format svg` (also accepted as `--format png,svg`).
With `project=...`, omit `out`; Astrid owns staging and publishes each durable
evidence artifact to managed CAS. Treat `result.manifest_path` as the durable
navigation handle. `result.outputs["pack_root"]` is a verified, browsable copy
under `.astrid/views/timeline_visualize/`, not a second authority; private
attempt staging is removed and `result.run_root` is therefore `None`.
Admission freezes the selected runtime timeline or frozen-manifest identity and
the executor-definition digest into the kernel task. The runner checks that
authority again before materialization; if the head, frozen manifest, focus, or
executor definition changed meanwhile, retry the invocation instead of treating
the failed run as a view of either state. Exact terminal replays report the
executor version stored with the original task.

The public CLI equivalent is the nested timeline command (the gateway still
has eight top-level families):

```bash
python3 -m astrid timelines visualize --project demo \
  --timeline-slug main --format png,svg --format md --json
```

Omit `--timeline-slug` for the project default, or pass `--all` for every
active timeline. The command returns the stable five-key envelope
synchronously; successful `data` includes run/kernel IDs and durable artifact
paths, while invalid selectors return a typed validation error before ledger
admission.

Use the qualified `selector` input (`rendering.remotion`, `rendering.ffmpeg`, or
`rendering.threejs`). The host does not translate shorthand selectors or
automatically route to another backend.

The normal SDK invocation writes `./out/hype.mp4` and
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

```python
# Generate a sprite sheet
import astrid.sdk as sdk
result = sdk.invoke(
    "rendering.sprite_sheet",
    inputs={
        "animation": "a character waving",
        "subject": "cartoon robot",
        "reference_image": "./robot_ref.png",
        "out_dir": "./sprites",
    },
)

# Scaffold a custom HTML canvas effect
result = sdk.invoke(
    "rendering.html_canvas_effect",
    inputs={"effect_id": "glass-product-card"},
    out="./out",
)
```

## Dependencies

- **Remotion** — requires server-owned `ASTRID_REMOTION_PROJECT_DIR` and
  `ASTRID_NODE_EXECUTABLE`; the locked project-local CLI is invoked directly
- **Node.js / npm** — `npm install` must have been run in the Remotion project
- **ffmpeg/ffprobe** — required by the FFmpeg renderer/finalizer and media probing

## Adding another renderer

Do not add code to the facade or service. A pack advertises protocol commands
through `extensions.rendering.renderers`, `.planners`, or `.finalizers` and
uses a qualified implementation id owned by that pack. The public contract,
manifest schemas, transport verbs, artifact/audio rules, and worked
third-backend example are in
`docs/contracts/render-backend-v1.md`.

### Scaffold → golden path

For a self-contained starting point, scaffold the canonical four-file pack
(`pack.yaml`, `renderer.yaml`, `render.py`, `test_renderer.py`) and walk the
golden path — the destination directory name becomes the pack id and the
renderer id becomes `<dest>.<name>`:

```bash
python3 -m astrid.core.rendering.cli create wave acme_wave
cd acme_wave
python3 -m pytest -q test_renderer.py     # generated deterministic test
python3 -m astrid.core.rendering.cli validate .    # static validation
python3 -m astrid.core.rendering.cli list --pack-root ..  # source checkout discovery
python3 -m astrid.core.rendering.cli inspect acme_wave.wave --pack-root ..
python3 -m astrid.core.rendering.cli smoke acme_wave.wave --pack-root .. --out ./out/smoke.mp4  # smoke
python3 -m astrid.core.rendering.cli replay <bundle-dir>   # replay a captured failure bundle
```

V1 is synchronous local execution only; asynchronous job scheduling, remote
render infrastructure, and layer compositing are explicitly deferred beyond V1
and are NOT part of the V1 renderer contract.

The smoke verb runs a deterministic direct-service render (fresh temp
workspace, no ledger/project mutation) and prints the output path plus its
provenance sidecar path. A real-timeline render goes through the facade:
`astrid.sdk.invoke("rendering.render", inputs={"timeline": "./out/hype.timeline.json", "backend": "acme_wave.wave"}, out="./out")`, which
writes `./out/hype.mp4` plus `./out/hype.mp4.provenance.json`; the sidecar
records resolution/trust/support evidence, artifact hashes and profiles, audio
ownership, normalization, attachments, and your namespaced
`backend_fragments`. Failed invocations retain a self-contained replay bundle
(resolved request, localized inputs, configuration, redacted logs, partial
result, exact replay command) instead of publishing a sidecar. The full
walkthrough is the golden-path section of
`docs/contracts/render-backend-v1.md`.

### SDK renderers

A `render.py` may also be written against the public rendering SDK instead of
parsing the raw file protocol: `astrid.render`/`astrid.support` drive the
shared `RenderService`, `astrid.renderer_main` is a protocol-v1 command
entrypoint that a manifest `command` can point at directly
(`command: [python3, -m, astrid.sdk.rendering]`), and `astrid.RenderContext`
provides workspace-validated paths, sanitized subprocesses, redacted logs,
probing/hashing, audio completion, and attachments for the duration of one
invocation. See `docs/reference/sdk.md` (Rendering SDK) for the worked
example. Wire equivalence is a hard contract: the SDK writes the same frozen
DTO JSON as the raw path, so both kinds of renderer pass the same conformance
fixtures.
