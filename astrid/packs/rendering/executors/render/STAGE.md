# Render

**Executor**: `rendering.render`  
**Status**: implemented  
**Pipeline step**: 12 (terminal)

Renders a hype timeline into opaque `hype.mp4` (or an explicitly
alpha-stamped layer into transparent ProRes 4444 `.mov`) through the backend-neutral
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

Normal Astrid usage goes through the SDK (`astrid.sdk.invoke(...)`). The
direct `run.py` entrypoint is a lower-level debug surface for reproducing
runner behavior outside the Astrid executor wrapper.

`rendering.render` has two explicit, mutually exclusive modes. `timeline`
names an exported or pipeline-produced JSON file owned by the project; values
such as `timeline="main"` remain file paths and never gain implicit canonical
meaning. `timeline_ref` names a managed kernel slug, UUID, or ULID and may be
paired with `expected_version`. The managed mode resolves and pins the stream
head before admission, materializes immutable private renderer inputs, and
stamps the canonical ID, version, tail hash, and content hashes in provenance.
The product CLI exposes that mode as `astrid timelines render <ref>`.

## Quick-start

Render a timeline with no external media registry:

```python
import astrid.sdk as sdk
result = sdk.invoke(
    "rendering.render",
    kind="executor",
    project="demo",
    inputs={"timeline": "./out/hype.timeline.json"},
)
```

Note: raw-file `timeline=<path>` mode keys idempotency by path, not content —
editing the timeline at the same path and re-invoking returns the cached render
without recomputing. For iterative edit/re-render workflows use the canonical
managed path (`timelines create`/`save` + `timelines render <timeline_ref>`) or pass
`timeline_ref=` so renders are content-hashed and never serve stale results.

Render a timeline with the optional media asset registry produced by
`video_editing.cut`:

```python
import astrid.sdk as sdk
result = sdk.invoke(
    "rendering.render",
    kind="executor",
    project="demo",
    inputs={"timeline": "./out/hype.timeline.json", "assets_registry": "./out/hype.assets.json"},
)
```

With a custom theme and strict qualified renderer:

```python
import astrid.sdk as sdk
result = sdk.invoke(
    "rendering.render",
    kind="executor",
    project="demo",
    inputs={
        "timeline": "./out/hype.timeline.json",
        "assets_registry": "./out/hype.assets.json",
        "theme": "./themes/my-theme",
        "backend": "rendering.remotion",
    },
)
```

The SDK invocation writes `./out/hype.mp4` and
`./out/hype.mp4.provenance.json`.

Render the current canonical kernel timeline, failing before admission if the
caller has observed a different version:

```python
result = sdk.invoke(
    "rendering.render",
    kind="executor",
    project="demo",
    inputs={"timeline_ref": "main", "expected_version": 4},
)
```

The equivalent product command is
`astrid timelines render main --project demo --expected-version 4`.

## Inputs

| Name            | Type   | Required | Description |
|-----------------|--------|----------|-------------|
| timeline        | file   | conditional | Explicit project-owned Hype timeline JSON; mutually exclusive with `timeline_ref`. |
| timeline_ref    | string | conditional | Canonical kernel slug, UUID, or ULID; mutually exclusive with `timeline`. |
| expected_version | integer | no | Positive stream-head CAS pin; valid only with `timeline_ref`. |
| assets_registry | file   | no       | Optional Hype media asset registry JSON. Pass as the `assets_registry` input when the timeline references media assets. If omitted, the runner supplies an empty registry. |
| theme           | file   | no       | Optional theme configuration. |
| selector        | string | no       | Qualified renderer id: `rendering.remotion`, `rendering.ffmpeg`, or `rendering.threejs`. Omit to select `rendering.remotion`. |
| backend_config  | JSON   | no       | Object keyed by qualified implementation id. The service forwards only the selected implementation's namespace. |
| output_name     | string | no       | Plain basename; defaults to `hype.mp4`. `.mov` is admitted only when the timeline has the exact `metadata.astrid_layer.alpha: true` stamp, and an explicit profile must declare MOV/ProRes/`yuva444p12le` plus PCM S16LE/48 kHz/stereo. The video and sidecar outputs use this value. |
| keep_previous_renders | boolean | no | Preserve prior provenance-linked sibling render outputs. |

Qualified renderer selection fails closed when that implementation reports the
request unsupported. There is no implicit planner or fallback route; select a
different qualified renderer explicitly.

## Outputs

| Name       | Type | Path                         | Description |
|------------|------|------------------------------|-------------|
| video      | file | `{out}/{output_name}` | Rendered video; default `{out}/hype.mp4`. |
| provenance | file | `{out}/{output_name}.provenance.json` | Sidecar describing render inputs, plan, resolution, and artifacts. |

## Remotion asset materialization

The shared render-host asset layer resolves local paths relative to the asset
registry, enforces project containment where a project is known, and stages
local/cached files into one invocation-owned directory. A project-scoped
render may also reference a canonical `managed_local` media locator under
`$ASTRID_PROJECTS_ROOT/.astrid/media`, but only when the exact locator is
present in the active project's kernel media rows and its bytes still match the
recorded content hash. Arbitrary sibling-project and unmanaged-root paths are
rejected during renderer support, before rendering starts. Remote URLs with
byte range support stream directly; other URLs are cached, optionally
hash-checked, and staged.

The Remotion backend serves only that staging directory on `127.0.0.1` through
an `InvocationAssetServer` with HTTP Range support. The ephemeral server sends
the local transport CORS headers needed when the Remotion page is hosted on
`localhost` while the asset server binds `127.0.0.1`. The materializer, server,
and stage are cleaned after success or failure.

If `assets_registry` is omitted, the facade creates a temporary empty registry.
This is valid for timelines that do not reference registry media.
In `timeline_ref` mode the registry cannot be overridden: Astrid uses the
canonical stored registry of runtime-managed object IDs and content hashes.
The host supplies verified bytes into an attempt-owned staging root. Private snapshots live under
`<project>/.astrid/render-snapshots/<authority-hash>/`; unchanged heads reuse
one directory. They are immutable derived inputs, not timeline authority, and
can be regenerated from the kernel. Retention tooling must retain directories
referenced by retryable tasks before removing unreferenced versions.

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
with the internal rendering CLI (`python3 -m astrid.core.rendering.cli create <name> <dest>`), implement
`render.py`, run the generated `test_renderer.py`, then `validate` →
trusted `install` via the internal pack CLI (`python3 -m astrid.core.pack.cli`)
→ `smoke` → `replay <bundle-dir>`
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
and writes to the exact `--out` path. It is not a public entrypoint; the
canonical guard requires Astrid's internal invocation marker:

```bash
ASTRID_INTERNAL_INVOCATION=1 python3 -m astrid.packs.rendering.executors.render.run \
  --timeline ./out/hype.timeline.json \
  --assets ./out/hype.assets.json \
  --out ./out/hype.mp4
```

For an asset-free debug render, omit `--assets`; the direct runner creates a
temporary empty asset registry:

```bash
ASTRID_INTERNAL_INVOCATION=1 python3 -m astrid.packs.rendering.executors.render.run \
  --timeline ./out/hype.timeline.json \
  --out ./out/hype.mp4
```

Free-space guard is also a direct-runner debug flag:

```bash
ASTRID_INTERNAL_INVOCATION=1 python3 -m astrid.packs.rendering.executors.render.run \
  --timeline ./out/hype.timeline.json \
  --assets ./out/hype.assets.json \
  --out ./out/hype.mp4 \
  --min-free-gb 10
```

## Pipeline position

Step 12 — the terminal step of the editorial pipeline. Runs after
`video_editing.cut` and produces the final rendered video. This is the
last step before optional YouTube upload.

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

- **Remotion** — requires server-owned `ASTRID_REMOTION_PROJECT_DIR` and
  `ASTRID_NODE_EXECUTABLE`; the locked project-local CLI is invoked directly
- **Node.js / npm** — `npm install` must have been run in the Remotion project
- **ffmpeg/ffprobe** — required by Remotion's render pipeline
