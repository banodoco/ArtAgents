---
name: "astrid"
short_description: "Astrid — file-based toolkit for agents to make video, image, and audio art alongside a human."
description: "Use for the Astrid repo: a file-based toolkit for agents to make art and creative work alongside a human. Video edits, generative timelines, image/audio/video understanding and generation — all behind one CLI gateway."
---

# Astrid

Astrid is a pack and client toolkit for making video, image, and audio art
alongside a human. Stage1 has two supported user surfaces:

- **The CLI gateway** — `python3 -m astrid` exposes five product families
  (`projects`, `timelines`, `media`, `tasks`, `runs`) and two operational
  routes (`doctor`, `backup`), plus the nested mounts (`timelines shots`,
  `media references`). Every command is sent to the workspace runtime.
- **The SDK** — `import astrid` is the sanctioned programmatic surface;
  `AstridClient` and capability invocation use the generated workspace client.

The Banodoco workspace runtime is the sole live authority for projects, media,
timeline versions, tasks, runs, receipts, and events. Start it with
`banodoco-local up --profile astrid`. The Astrid checkout supplies packs and
client code; it does not own a project database, CAS, session/thread store, or
execution ledger.

Nothing else is a command. `next`, `status`, `attach`, `setup`, `start`,
`ack`, `executors`, `orchestrators`, `elements`, `sessions`, `packs`, and
`skills` are not gateway verbs — the legacy task-mode CLI (attach/next/start/
ack) and the old filesystem task-run store are gone; use the seven-family CLI
and the SDK.

## When in doubt, run the census

```bash
python3 -m astrid --help          # the complete seven-family census
python3 -m astrid help            # same census, plus mounts and exit codes
python3 -m astrid --version       # the app name (importlib.metadata)
python3 -m astrid projects --help # inspect one family's verbs
```

`--help` prints exactly the seven families and the two nested mounts. There
is no other CLI surface to discover; when you do not know which family a
question belongs to, read the census first.

## Runtime connection

Resolve the runtime from `BANODOCO_RUNTIME_ENDPOINT`, or from the discovery
JSON named by `BANODOCO_RUNTIME_DISCOVERY`; the token is read from
`BANODOCO_RUNTIME_CREDENTIAL`. If any of these are unavailable, the typed
recovery action is `banodoco-local up --profile astrid`.

`doctor --json` asks the runtime for health. `backup` is currently unavailable
until the runtime exposes its backup route. Neither command opens or repairs a
checkout-local store. Do not set `ASTRID_PROJECTS_ROOT` to try to redirect
product state; that legacy/test variable is not Stage1 authority.

## Start Here

The canonical clean-machine flow is:

```bash
banodoco-local up --profile astrid
python3 -m astrid doctor --json
python3 -m astrid projects create demo --name "Demo" --json
python3 -m astrid projects list --json
python3 -m astrid timelines create primary --project demo --name "Primary" --default --json
python3 -m astrid media import ./shot.png --project demo --json
python3 -m astrid tasks create --project demo --capability rendering.timeline_visualize \
  --spec '{"timeline_source": "..."}' --json
python3 -m astrid runs list --project demo --json
```

`media import` accepts existing files and directories. Product and nested-mount
commands support `--json` as the stable machine surface: exactly one five-key
envelope (`ok` / `data` / `error` / `receipt` / `idempotency_key`). `doctor
--json` is the diagnostic exception; it returns the runtime health object.
`backup` has no stable product route in Stage1. Exit codes are stable: `0`
success, `1` typed SDK/runtime error, `2` usage/parse error.

## Product families

| Family | Verbs | Notes |
| --- | --- | --- |
| `projects` | `create`, `list`, `show`, `update` | Project selection is runtime-scoped; a sole runtime project may be selected implicitly, while multiple projects require `--project`. |
| `timelines` | `create`, `list`, `show`, `save`, `archive`, `unarchive`, `history`, `diff`, `visualize`, `render` | `list --include-archived` is the recovery read; `unarchive` is safe to repeat; `visualize` emits a run-owned evidence pack and `render` accepts a pinned canonical timeline |
| `media` | `import`, `list`, `show`, `verify` | Media is ingested and addressed as runtime-owned objects; reference-in-place repair is not a Stage1 user operation. |
| `tasks` | `create`, `list`, `show`, `cancel`, `retry`, `events` | `create` admits one immutable task (`--capability` + JSON `--spec`) |
| `runs` | `list`, `show`, `cancel`, `retry-failed`, `events` | `retry-failed` is the batch-retry surface (all-failed-children or explicit `--task` subset) |

The former file-side `projects select/current` preference is not Stage1
authority. Runtime selection is resolved by the connected workspace service:
an explicit `--project` always wins, a sole runtime project is safe to infer,
and multiple projects require an explicit reference.

Nested mounts (reachable only beneath their parent family, never top-level):

```bash
python3 -m astrid media references ...      # create/update/archive/unarchive/associate/link/set-primary/list/show
python3 -m astrid timelines shots ...       # project-level reusable list/create/show/add/remove/reorder
```

To return to paused work without remembered ids, discover archived timelines
and references inclusively, then restore by timeline slug or an unambiguous
project-local reference name:

```bash
python3 -m astrid timelines list --project demo --include-archived --json
python3 -m astrid timelines unarchive primary --project demo --json
python3 -m astrid media references list --project demo --include-archived --json
python3 -m astrid media references unarchive "Character Name" --project demo --json
```

Routes not exposed by the connected runtime return a typed `unavailable`
result. Do not fall back to local files, a checkout database, or a second
authority.

## Runs & tasks

Tasks and runs are runtime resources. Every capability admission and lifecycle
transition crosses the generated workspace client; local projections are not
status authority. Use an explicit runtime project reference when more than
one project is visible; the sole runtime project is selected automatically:

```bash
python3 -m astrid tasks list --project demo --json
python3 -m astrid runs show <run_id> --project demo --json --evidence
python3 -m astrid runs cancel <run_id> --project demo --json
python3 -m astrid runs retry-failed <run_id> --project demo --json
```

Read events with `client.read_events(...)` or the runtime-backed
`client.runs.events(...)`; event ordering and retention belong to the runtime.
`projects_root`, local `events.jsonl`, and SQLite fallbacks are historical
interfaces and must not be used for live observation.

## Operational routes

```bash
python3 -m astrid doctor [--json]   # runtime health check
python3 -m astrid backup             # unavailable until a runtime route exists
```

There is no public `astrid serve` command in Stage1. Start the separate
workspace runtime with `banodoco-local up --profile astrid`. Backup and restore
are runtime-owned operations; do not copy or edit a local SQLite/CAS tree.

## The SDK is the pack surface

Packs ship capabilities (executors, orchestrators, elements). They are not
gateway commands. Run them through the SDK:

```python
import astrid.sdk as sdk

result = sdk.discover()   # source and explicitly supplied pack inventory
cap = sdk.get_capability(
    "editorial.transcribe", kind="executor",
)
result = sdk.invoke(
    "iteration.experiment_review",
    kind="executor",
    inputs={"review": "experiments/prompt-brevity/review.json"},
    project="demo",          # every executor run belongs to exactly one project
)
```

`kind` is required; pass `project=<slug>` and omit `out` — project-scoped
runs write inside the project's own `runs/<run-id>/` tree.

or through a bound client:

```python
from astrid.sdk.client import AstridClient

with AstridClient.open() as client:          # composes the standard application
    result = client.invoke(
        "rendering.render",
        kind="executor",
        inputs={...},
        project="demo",
    )
```

Typed facades exist for the most common surfaces: `astrid.generate.*`
(image/audio/video generation), `astrid.render` / `astrid.support` /
`astrid.renderer_main` / `astrid.RenderContext` (rendering), and
`client.tasks` / `client.timelines` / `client.media` / … (the seven typed
services). See [docs/reference/sdk.md](../../../../docs/reference/sdk.md).

Rendering has two deliberately explicit contracts. `rendering.render` with
`timeline` consumes a project-owned exported or pipeline JSON file; a value
like `timeline="main"` is still a file path. Its `timeline_ref` input resolves
a canonical runtime slug/UUID/ULID and optionally enforces `expected_version`;
use `astrid timelines render <ref>` for the product CLI. Managed visualization
likewise resolves the canonical runtime timeline and pins its actual stream
head. Visualization's `timeline_source` remains the explicit legacy filesystem
compatibility route.

### How capabilities execute

Every live capability invocation crosses the workspace runtime:

- **Runtime admission** — `sdk.invoke(...)` and typed clients send a
  capability id, digest, project, and spec to the generated workspace client.
  The runtime owns claim/start/execute/complete|fail, attempts, receipts,
  leases, and event ordering.
- **Attempt-local artifacts** — pack code may write files in its provided
  attempt workspace and return a manifest. Those files are delivery artifacts,
  not a second project/run authority; publish durable objects through the
  runtime contract.
- **Never invoke `run.py` modules directly** — the canonical-entrypoint
  guard refuses it; `astrid.sdk.invoke` is the entry.

## Retired legacy surface

The legacy task-mode CLI (`attach`/`next`/`start`/`ack`) and filesystem task
store are retired. Historical pre-runtime plans and thread/session records may
remain for migration or research, but they are not live authority and must not
be updated as part of a runtime operation.

## Shared Knowledge With Hivemind

Hivemind is Astrid's shared knowledge pack. Use `hivemind.search` before
researching community best practices, model behavior, settings, known
failures, or workflow precedents; use `hivemind.get_item` when a search result
needs its full body or citation context. Run them through the SDK:

```python
import astrid.sdk as sdk
result = sdk.invoke("hivemind.search", kind="executor", inputs={"query": "wan 2.2 best settings"})
```

Astrid project files remain the source of truth for raw runs, experiment
reviews, and `conclusions.json`. Hivemind is the cross-project publication and
retrieval layer for generalizable learnings. Hivemind writes are public
publication, including pending distillations. Never publish automatically:
dry-run or preview the payload, remove private paths, prompts, media, and
URLs, and obtain explicit user confirmation before calling
`hivemind.contribute`.

## Pack Model

Packs are namespace and distribution containers for capabilities (executors,
orchestrators, elements). Every capability lives in exactly one pack under
`astrid/packs/<pack>/`, declared in a `pack.yaml` manifest. Capability ids are
always qualified as `<pack>.<name>`; bare ids are rejected. Executor folders
use `astrid/packs/<pack>/executors/<slug>/{executor.yaml,STAGE.md,run.py}` and
orchestrator folders use
`astrid/packs/<pack>/orchestrators/<slug>/{orchestrator.yaml,STAGE.md,run.py}`,
with optional local `src/` modules. Element folders live at
`astrid/packs/<pack>/elements/<kind>/<id>/{component.tsx,element.yaml}` where
kind is `effects`, `animations`, or `transitions`. A gitignored `local` pack
at `astrid/packs/local/` holds user-edited element forks.

- **Executor** — one concrete, independently runnable unit of work.
- **Orchestrator** — a workflow that coordinates executors or child
  orchestrators.
- **Element** — a reusable render building block: effect, animation, or
  transition.

Timeline renderers, planners, and finalizers are a fourth surface but not
executor kinds: protocol commands registered by a pack through
`extensions.rendering.{renderers,planners,finalizers}` behind the stable
`rendering.render` facade (see `docs/contracts/render-backend-v1.md`).

### Discovery

Discover capabilities through the SDK, not by grepping source:

```python
import astrid.sdk as sdk
result = sdk.discover()   # full source inventory, pack by pack
caps = sdk.get_capability(                       # typed lookup (raises on missing/ambiguous)
    "editorial.arrange", kind="executor",
)
```

Read the relevant `STAGE.md` before running a capability; it is the source of
truth for invocation details. Do not package every STAGE.md into one merged
prompt — open only the folder-level `STAGE.md` for the selected capability.

### Aliases, Forks, and Overrides

Three mechanisms customize capabilities without editing originals: **aliases**
(old ids mapped to current capabilities, declared in `pack.yaml`),
**forks** (a copy into the local pack with provenance back to the source),
and **overrides** (redirect an id to a preferred fork). Full details:
[docs/packs/aliases-vs-forks-vs-overrides.md](../../../../docs/packs/aliases-vs-forks-vs-overrides.md).

## Safety Rules

- Generated files live under `runs/` or another ignored output directory.
- Do not commit source media, rendered videos, local dependency envs, or secrets.
- Do not print or hardcode API keys; use `--env-file` or nearby `.env` files.
- Do not edit runtime state, receipts, or event streams by hand; mutate through
  the generated client-backed CLI and SDK only.
- Treat curated tool stages as protected unless explicitly asked to edit them,
  notably `astrid/packs/moirae/executors/moirae/STAGE.md` and
  `astrid/packs/vibecomfy/executors/run/STAGE.md`.
- Orchestrators may call declared child orchestrators; executors must not call orchestrators.

After editing `short_description` / `keywords` on any executor, orchestrator,
or element manifest, refresh the capability index in this file:

```bash
python3 scripts/gen_capability_index.py
```

## Common Defaults

Built-in orchestrators: `video_editing.hype`, `video_editing.event_talks`,
`video_editing.thumbnail_maker`.

Built-in executors include `editorial.transcribe`, `video_editing.cut`,
`rendering.render`, `editorial.validate`, `understanding.understand`
(audio/visual/video dispatcher; pass `--mode {audio,visual,video}`), and
`generation.generate_image_openai`. External executors include `moirae.moirae`
and `vibecomfy.run` (executor only, not an orchestrator).

Element source priority: active theme →
`astrid/packs/local/elements/<kind>/<id>` (gitignored scratch pack) →
`astrid/packs/builtin/elements/<kind>/<id>`. Forking copies the source element
into `astrid/packs/local/`, auto-creating `astrid/packs/local/pack.yaml` and
rewriting the element's `pack_id` to `local`.

## Adding overlays to a rendered video

Quick recipe: take any `.mp4` and overlay text captions / a wordmark via the
timeline + Remotion path.

### The timeline and optional asset registry

- `timeline.json` — defines tracks and clips. Schema: `@banodoco/timeline-schema`
  (see `remotion/node_modules/@banodoco/timeline-schema/typescript/src/schemas.ts`).
  Top level: `{theme, theme_overrides?, tracks, clips, output?}`. Each clip has
  `id, at (seconds), track, clipType?, asset?, hold? | from/to, text?, params?,
  effects?, x?/y?/width?/height?`.
  Ordinary asset-backed clips may omit `clipType` or use the explicit
  `media`, `video`, `image`, or `audio` spellings; Remotion treats all four as
  built-in media, not effect ids. Structured text must use `clipType: "text"`.
  `clip.effects` is only the fade envelope: either a numeric map such as
  `{"fade_in": 0.2, "fade_out": 0.2}` or a list of objects containing only
  `fade_in` / `fade_out`. It is not the reusable-element reference surface.
  To use a registered visual element, make it the clip itself with
  `clipType: "<effect-id>"` and optional `params: {...}`. Canonical managed
  render rejects an unknown effect id before creating a run.
- For a first visible render, use the canonical shape below: root `clips`, a
  visual track, `output.resolution` as a string (for example `640x360`),
  `output.fps`, and an `.mp4` `output.file`. A structured text payload is a
  `clipType: "text"` clip; a clip with a `text` object but no text clip type is
  rejected before rendering because it otherwise becomes an empty/black media
  layer.

```json
{
  "tracks": [{"id": "cards", "kind": "visual", "label": "Cards"}],
  "clips": [{
    "id": "title", "at": 0, "track": "cards", "clipType": "text",
    "hold": 2,
    "text": {"content": "HELLO ASTRID", "fontSize": 64, "color": "#ffffff", "align": "center"}
  }],
  "output": {"resolution": "640x360", "fps": 30, "file": "title.mp4"}
}
```
- `assets.json` — optional media registry:
  `{"assets": {"<id>": {file?: <relative-or-absolute-path>, url?,
  content_sha256?, type?, resolution?, fps?, duration?}}}`. Include it when
  clips reference media assets.

### Layering rule (gotcha)

Visual tracks render in **reversed** array order (`TimelineComposition.tsx`:
`[...getVisualTracks(timeline)].reverse()`). To put overlays on top, list the
overlay track **first** in `timeline.tracks`.

### Timeline design conventions

Use one track per editing concern, not one catch-all overlay track. A
maintainable visual stack usually reads top-to-bottom as `brand` or persistent
CTA, `captions`, moment-specific `fx` or text callouts, `broll`, then
`source`; audio tracks follow visual tracks. Because visual tracks render in
reversed order, the first visual track in `tracks` is the top layer. Keep clip
ids prefixed by concern (`brand_`, `cap_`, `fx_`, `broll_`, `src_`, `audio_`)
so later patches can target the right layer without re-reading every clip. The
canonical small fixture is `examples/hype.timeline.json`; read it before
hand-authoring a timeline.

### Rendering

```python
import astrid.sdk as sdk

result = sdk.invoke(
    "rendering.render",
    kind="executor",
    inputs={
        "timeline": "runs/<my-run>/timeline.json",
        "assets_registry": "runs/<my-run>/assets.json",
    },
    project="demo",
)
```

For timelines with no media registry entries, omit `assets_registry`. The
project-scoped render writes `hype.mp4` (plus its `.provenance.json`
sidecar) into the run's output directory under `demo/runs/<run-id>/`.
Output names must use the selected container suffix; the default H.264/AAC
profile requires `.mp4`. The service checks this and the text-clip shape
before creating a renderer workspace. `output.resolution` / `output.fps` are
legacy timeline hints, not the encoder profile: Remotion renders its resolved
theme canvas (1920x1080 at 30 fps when no canvas is configured). An explicit
profile must match that authoritative canvas; set
`theme_overrides.visual.canvas` when a different output size is intended.
`--profile` is the flat RenderProfile v1 wire object; nested `video`/`audio`
objects are invalid. A complete Remotion MP4 profile is:

```json
{"width":1920,"height":1080,"fps_rational":[30,1],"time_base":[1,90000],"container":"mp4","video_codec":"h264","video_profile":null,"video_level":null,"pixel_format":"yuv420p","audio_codec":"aac","audio_sample_rate":48000,"audio_channel_layout":"stereo","duration_tolerance":1}
```

The required flat fields are `width`, `height`, `fps_rational`, `time_base`,
`container`, `video_codec`, `video_profile`, `video_level`, `pixel_format`, and
`duration_tolerance`. The three `audio_*` fields must be supplied together or
all omitted; Remotion always muxes AAC audio, so use all three as shown.
Managed render validates missing, unknown, and invalid profile fields before
run admission and returns null run/task ids on failure.
Canonical create/save intentionally permit unfinished drafts. Managed render
preflights the pinned document before run admission: `output` may be omitted,
but when present it must contain `resolution`, `fps`, and `file`; timeline and
registry schema errors or missing asset ids return typed validation errors
with null run/task ids.
Renderer authors use the typed
`astrid.render` / `astrid.support` / `astrid.renderer_main` /
`astrid.RenderContext` surface (see `docs/reference/sdk.md`).

### Local effect assets

Effect, animation, and transition manifests may declare static files with
optional top-level syntax:

```yaml
assets:
  badge: assets/badge.png
  palette: assets/palette.json
```

Values are paths relative to the element root, must stay inside that root, and
must point to files. During render, Astrid stages only declared assets for
elements used by the timeline under
`remotion/public/astrid-effects/<render-hash>/<effect-id>/`, injects their
static-file-relative paths into `params.__astridAssets`, and cleans the staging
directory after Remotion exits.

### Where the schemas and render boundary live (authoritative)

- Timeline + clip Zod schemas: `remotion/node_modules/@banodoco/timeline-schema/typescript/src/schemas.ts`
- Composition (clip → component dispatch, layering): `remotion/node_modules/@banodoco/timeline-composition/typescript/src/TimelineComposition.tsx`
- Effect / animation registries: generated by `scripts/gen_effect_registry.py`
- Python timeline IO + validation: `astrid/core/timeline/`
- Stable facade: `astrid/packs/rendering/executors/render/run.py`
- Backend-neutral lifecycle: `astrid/core/rendering/service.py`
- Rendering protocol schemas: `astrid/core/rendering/schemas/v1/`
- Public pack-author contract: `docs/contracts/render-backend-v1.md`
- Render provenance: `<video-output>.provenance.json`

### Available elements

Discover elements through the SDK (`sdk.discover()` / `get_capability` with an
element id), or read the index below. At time of writing: effects `text-card`
(the built-in component is `() => null` — it expects a theme override to do
the real DOM rendering; fork into the local pack and regenerate with
`scripts/gen_effect_registry.py` to customize), `sliding-media`,
`neon-orbit-card`, `model-trends`, `audio-reactive-colour`, `vibe-comfy-*`;
animations `fade`, `fade-up`, `scale-in`, `slide-left`, `slide-up`, `type-on`;
transitions `cross-fade`, `fade`.

### 5-minute "add a caption" recipe

1. Drop your source `.mp4` into `runs/<name>/`.
2. Write `runs/<name>/{timeline,assets}.json` per the shapes above. Adjust
   `at`, `hold`, `text.content`, and `params.anchor`; add a new track when the
   new clip is a new concern, not just another caption.
3. Render with the SDK snippet above.
4. ffprobe / open the `hype.mp4`.
5. If captions don't appear after editing the local-pack component, blow away
   `remotion/node_modules/.cache` — Remotion's webpack caches aggressively
   across renders.

## Further Reading

- [docs/getting-started.md](../../../../docs/getting-started.md) — the canonical human setup doc
- [docs/guides/cli-journeys.md](../../../../docs/guides/cli-journeys.md) — runtime-backed families, journeys, recovery
- [docs/reference/sdk.md](../../../../docs/reference/sdk.md) — Python SDK (DTOs, exceptions, typed facades)
- [docs/contracts/cli-contract.md](../../../../docs/contracts/cli-contract.md) — CLI stream/exit-code discipline
- [docs/guides/creating-tools.md](../../../../docs/guides/creating-tools.md) — when to create each capability kind
- [docs/packs/creating-packs.md](../../../../docs/packs/creating-packs.md) — pack authoring workflow
- [docs/contracts/render-backend-v1.md](../../../../docs/contracts/render-backend-v1.md) — renderer-author contract

The capability index below is **auto-generated** by
`scripts/gen_capability_index.py`. Re-run it after editing executor,
orchestrator, or element manifests.

<!-- BEGIN CAPABILITY INDEX (auto-generated by scripts/gen_capability_index.py) -->

### Executors

| id | short_description |
| --- | --- |
| `blender.render` | Render a Blender scene (declarative spec or .blend file) to a still or animation, locally or on a cloud render host. |
| `comfy_wrap.run` | Generate an image by injecting a prompt into a ComfyUI workflow JSON and running it via vibecomfy. |
| `editorial.arrange` | Compose a brief-specific shot arrangement from the source clip pool. |
| `editorial.boundary_candidates` | Package candidate video frames for visual scene-boundary review. |
| `editorial.editor_review` | Run heuristic editorial reviewers over an arrangement and emit notes. |
| `editorial.human_notes` | Convert human editorial notes into structured pipeline inputs. |
| `editorial.human_review` | Serve a small HTML page locally, collect human decisions as JSON, block until submit. |
| `editorial.inspect_cut` | Inspect a generated cut run directory and report timeline/asset health. |
| `editorial.quality_zones` | Tag arrangement clips with per-zone quality grades for downstream picks. |
| `editorial.quote_scout` | Scan a transcript for quotable lines suitable for hype clips. |
| `editorial.refine` | Apply targeted reviewer-driven refinements to an existing arrangement. |
| `editorial.scenes` | Detect source-video scene boundaries with ffmpeg-driven analysis. |
| `editorial.script_pipeline` | Generate short scripts through rough attempts, synthesis, style pass, and optional judging. |
| `editorial.shots` | Slice scenes into shot windows for downstream pool building. |
| `editorial.transcribe` | Transcribe source audio to transcript.json via Whisper. |
| `editorial.triage` | Triage source-video scenes by quality before pool building. |
| `editorial.validate` | Validate the rendered video against its declared timeline and metadata. |
| `fal.fal_foley` | Generate Foley audio for one short video clip via fal.ai's hunyuan-video-foley model. |
| `fal.h3_video` | Generate MiniMax H3 text-to-video or multimodal reference-to-video clips through fal.ai. |
| `foley.foley_review` | Build a static review.html pairing each tile clip with its generated Foley audio for sense-checking. |
| `foley.tile_video` | Crop a video into an MxN grid of overlapping spatial tiles plus first-frame PNGs. |
| `generation.generate_audio` | Generate audio from text prompts via local or cloud backends. v2: model→mode→backend with music mode. |
| `generation.generate_image` | Generate images from text prompts via local, cloud, or Codex backends. v2: model→mode→backend. |
| `generation.generate_image_openai` | Generate image files with OpenAI GPT Image models from a prompt file. |
| `generation.generate_video` | Generate videos from text prompts via local or cloud backends. v2: model→mode→backend with t2v/i2v/flf/v2v modes. |
| `iteration.assemble` | Adapt runtime-derived or file-backed iteration data into canonical iteration artifacts and render-ready hype inputs. |
| `iteration.experiment_import` | Import an unmanaged run root into an experiment without rewriting history or guessing ambiguous associations. |
| `iteration.experiment_prepare` | Normalize an experiment's provider manifests into a provider-independent review model with diagnostics. |
| `iteration.experiment_review` | Render a deterministic HTML gallery comparing provider outputs with prompt, parameters, warnings, and diagnostics. |
| `media.clip_extract` | Extract a clip segment from a video using ffmpeg stream copy. |
| `media.gif_search` | Search GIPHY for GIF or sticker assets and optionally download a selected rendition. |
| `media.speech_repair_lavasr` | Repair weak-mic speech with hotter pre-lift, fal.ai LavaSR, optional DeepFilterNet3, and a final loudness pass. |
| `moirae.moirae` | Run a Moirae screenplay through the terminal-as-cinema renderer to produce a video. |
| `reigh.open_in_reigh` | Copy or stage generated timeline+assets for handoff into a Reigh project. |
| `reigh.publish` | Publish a finished timeline + assets pair into a Reigh project via API. |
| `reigh.reigh_data` | Fetch canonical Reigh project data through the reigh-data Edge Function. |
| `reigh.spatial_audio_page` | Build a static page that mixes Foley tracks anchored to spatial rectangles via Web Audio. |
| `rendering.html_canvas_effect` | Scaffold a local Remotion HTML-in-canvas effect element. |
| `rendering.render` | Render a hype timeline to opaque MP4 or explicitly stamped alpha MOV through the selected backend. |
| `rendering.sprite_sheet` | Generate, slice, and preview GPT Image sprite sheets for batch image work. |
| `rendering.timeline_storyboard` | Build a static visual storyboard of image inputs associated with timeline shots. |
| `rendering.timeline_visualize` | Build a deterministic, agent-navigable evidence pack from managed timeline event logs. |
| `runpod.exec` | Execute a script on an existing RunPod pod and download artifacts. |
| `runpod.provision` | Provision a RunPod GPU pod and emit a pod handle for later exec/teardown. |
| `runpod.pull` | Pull artifacts from an existing RunPod pod into local storage. |
| `runpod.session` | Composite provision → exec → teardown session with guaranteed cleanup. |
| `runpod.teardown` | Terminate a RunPod pod. Idempotent. |
| `stream_content.clip_candidates` | Score transcript windows as publishable stream clip candidates. |
| `stream_content.segment_map` | Fuse OCR, transcript density, and scene cuts into a complete stream timeline. |
| `training.asset_cache` | Manage the repo-local hype asset cache (download, prune, list). |
| `training.pool_build` | Build the candidate clip pool from triaged source-video scenes. |
| `training.pool_merge` | Merge multiple candidate clip pools into a unified pool for arrangement. |
| `training.search_loras` | Search Hugging Face Hub for LoRAs associated with a base model. |
| `typed_timeline.map` | Map typed rows to a validated timeline JSON. |
| `understanding.audio_understand` | Inspect audio clips or sampled windows with an audio-understanding LLM. |
| `understanding.scene_describe` | Caption each detected scene with a vision model for downstream selection. |
| `understanding.understand` | Dispatch to the audio, visual, or video understanding executor based on --mode. |
| `understanding.video_understand` | Inspect synchronized audio+video windows with a video-understanding model. |
| `understanding.visual_understand` | Inspect images or sampled video frames with a vision LLM — free-text or JSON-schema-constrained. |
| `vibecomfy.run` | Run a VibeComfy / ComfyUI workflow JSON through the VibeComfy CLI. |
| `vibecomfy.validate` | Validate a VibeComfy / ComfyUI workflow JSON without executing it. |
| `video_editing.cut` | Build the Reigh-compatible hype timeline + assets + metadata JSON triple from arrangement. |
| `youtube.upload` | Upload a finished video to YouTube via the shared banodoco-social Zapier integration. |
| `youtube.youtube_audio` | Download a YouTube video's audio (MP3) or video (MP4) — by search query or direct URL. |

### Orchestrators

| id | short_description |
| --- | --- |
| `foley.foley_map` | Spatial Foley pipeline: tile a video, prompt a VLM, score Foley per tile, and emit a viewer. |
| `iteration.experiment_review_session` | Interactive rubric review session over a prepared experiment, reusing editorial.human_review with safe mounted media. |
| `stream_content.distill` | Distill a long event stream into segments, extracted blocks, candidates, and a review page. |
| `training.dataset_build` | Build a generic reviewed video training dataset from configured sources. |
| `training.training_run` | Run a generic LoRA training job from a prepared dataset manifest. |
| `typed_timeline.render` | Map typed rows then render via ffmpeg fast-path. |
| `video_editing.animate_image` | Two-stage Fal pipeline: edit a reference image with GPT Image 2, then animate it with WAN 2.2. |
| `video_editing.event_talks` | Orchestrate event-talk template, search, holding-screen, and render commands into a finished video. |
| `video_editing.hype` | Run the canonical hype editing pipeline end-to-end (transcribe → cut → render → validate). |
| `video_editing.iteration_video` | Discover runtime project runs, assemble render inputs, render, and finalize iteration video outputs. |
| `video_editing.logo_ideas` | Generate a grid of distinct logo concepts via Kimi K2 prompts + GPT Image 2 (or z-image) renders. |
| `video_editing.thumbnail_maker` | Plan source evidence and thumbnail generation candidates for a video/query pair. |
| `video_editing.vary_grid` | Iterative grid editor: take an existing grid image and emit a new grid of variations via fal. |

### Elements

| id | short_description |
| --- | --- |
| `animations/fade` | Fade in/out wrapper animation. |
| `animations/fade-up` | Fade up entrance animation. |
| `animations/scale-in` | Scale in entrance animation. |
| `animations/slide-left` | Slide left entrance animation. |
| `animations/slide-up` | Slide up exit animation. |
| `animations/type-on` | Typewriter-style text reveal animation. |
| `effects/audio-reactive-colour` | Fill the frame with colours selected by frozen integer-frame markers. |
| `effects/text-card` | Default text card effect for captions and titles. |
| `transitions/cross-fade` | Cross fade transition. |
| `transitions/fade` | Fade-through-black transition. |

<!-- END CAPABILITY INDEX -->

## Validate

```bash
pytest tests/v10/test_docs_cli_alignment.py -x -q
pytest --tb=no -q --no-header
```

## Upstream friction

When a workflow is awkward, brittle, or undocumented, tell the user directly.
Suggest the smallest durable fix; if the issue belongs upstream, recommend a
PR there.

## Begin

Ask the maker what they want to make or learn. If they want ideas, see
`docs/guides/ideas.md`.
