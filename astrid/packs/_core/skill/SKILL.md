---
name: "astrid"
short_description: "Astrid — file-based toolkit for agents to make video, image, and audio art alongside a human."
description: "Use for the Astrid repo: a file-based toolkit for agents to make art and creative work alongside a human. Video edits, generative timelines, image/audio/video understanding and generation — all behind one CLI gateway."
---

# Astrid

Astrid is a file-based toolkit for making video, image, and audio art alongside
a human. There are exactly two surfaces:

- **The CLI gateway** — `python3 -m astrid` owns the eight families: five
  product families (`projects`, `timelines`, `media`, `tasks`, `runs`) and
  three operational families (`serve`, `doctor`, `backup`), plus the two
  manifest-declared nested mounts (`timelines shots`, `media references`).
  One verb = one SDK call.
- **The SDK** — `import astrid` (`astrid.sdk.client.AstridClient`,
  `astrid.sdk.discover` / `get_capability` / `invoke`) is the sanctioned
  programmatic surface; every pack capability runs through it.

Nothing else is a command. `next`, `status`, `attach`, `setup`, `start`,
`ack`, `executors`, `orchestrators`, `elements`, `sessions`, `packs`, and
`skills` are not gateway verbs — the legacy task-mode CLI (attach/next/start/
ack) and the old filesystem task-run store are gone; use the eight-family CLI
and the SDK.

## When in doubt, run the census

```bash
python3 -m astrid --help          # the complete eight-family census
python3 -m astrid help            # same census, plus mounts and exit codes
python3 -m astrid --version       # the app name (importlib.metadata)
python3 -m astrid projects --help # inspect one family's verbs
```

`--help` prints exactly the eight families and the two nested mounts. There
is no other CLI surface to discover; when you do not know which family a
question belongs to, read the census first.

## Canonical bundled pack census

The canonical beta bundle contains 22 product packs. `_core` is deliberately
not one of them: it is irreducible, code-owned kernel guidance. The table is a
deterministic checked-in routing projection, sorted by pack id, with each
destination fixed to the owning pack's packaged `skill/SKILL.md`. Pack identity,
database ownership, documentation, and resource closure remain authoritative in
the canonical catalog and each strict-v2 `pack.yaml`.

<!-- BEGIN PACK CENSUS (deterministic checked-in routing projection) -->

| Product pack | Owning agent guidance |
| --- | --- |
| `blender` | [`skill/SKILL.md`](../../blender/skill/SKILL.md) |
| `comfy_wrap` | [`skill/SKILL.md`](../../comfy_wrap/skill/SKILL.md) |
| `editorial` | [`skill/SKILL.md`](../../editorial/skill/SKILL.md) |
| `fal` | [`skill/SKILL.md`](../../fal/skill/SKILL.md) |
| `foley` | [`skill/SKILL.md`](../../foley/skill/SKILL.md) |
| `generation` | [`skill/SKILL.md`](../../generation/skill/SKILL.md) |
| `iteration` | [`skill/SKILL.md`](../../iteration/skill/SKILL.md) |
| `media` | [`skill/SKILL.md`](../../media/skill/SKILL.md) |
| `moirae` | [`skill/SKILL.md`](../../moirae/skill/SKILL.md) |
| `references` | [`skill/SKILL.md`](../../references/skill/SKILL.md) |
| `reigh` | [`skill/SKILL.md`](../../reigh/skill/SKILL.md) |
| `rendering` | [`skill/SKILL.md`](../../rendering/skill/SKILL.md) |
| `runaway` | [`skill/SKILL.md`](../../runaway/skill/SKILL.md) |
| `runpod` | [`skill/SKILL.md`](../../runpod/skill/SKILL.md) |
| `shots` | [`skill/SKILL.md`](../../shots/skill/SKILL.md) |
| `stream_content` | [`skill/SKILL.md`](../../stream_content/skill/SKILL.md) |
| `timeline` | [`skill/SKILL.md`](../../timeline/skill/SKILL.md) |
| `training` | [`skill/SKILL.md`](../../training/skill/SKILL.md) |
| `understanding` | [`skill/SKILL.md`](../../understanding/skill/SKILL.md) |
| `vibecomfy` | [`skill/SKILL.md`](../../vibecomfy/skill/SKILL.md) |
| `video_editing` | [`skill/SKILL.md`](../../video_editing/skill/SKILL.md) |
| `youtube` | [`skill/SKILL.md`](../../youtube/skill/SKILL.md) |

<!-- END PACK CENSUS -->

## Bootstrap and the store

- `ASTRID_PROJECTS_ROOT` selects the projects root (default `<repo>/projects`
  from a checkout).
- The first product command lazily creates
  `$ASTRID_PROJECTS_ROOT/.astrid/astrid.sqlite3` — the SQLite kernel: 14 core
  tables plus the default-enabled timeline/shots/references pack tables (and
  optionally Runaway when explicitly composed), WAL mode, one exclusive-owner
  lock.
- `python3 -m astrid doctor --json` is the read-only health check. It reports
  `schema_versions`, media paths, a SQLite quick-check, and foreign-key status
  without repairing or rewriting data. On a pristine root it returns
  `state: "uninitialized"`, `ok: true`, and exit 0 with the create command;
  after initialization, `state: "ready"` means all checks pass and
  `state: "unhealthy"` means a real failure. A failing `schema_versions`
  check on an existing root means the database is newer or incompatible with
  this checkout.

## Start Here

The canonical clean-machine flow is:

```bash
python3 -m astrid doctor --json
python3 -m astrid projects create demo --name "Demo" --json
python3 -m astrid projects list --json
python3 -m astrid timelines create primary --project demo --name "Primary" --default --json
python3 -m astrid media import ./shot.png --project demo --json
python3 -m astrid tasks create --project demo --capability rendering.timeline_visualize \
  --spec '{"timeline_source": "..."}' --json
python3 -m astrid runs list --project demo --json
```

`media import` accepts existing files and directories. Video/audio containers
are strictly probed with `ffprobe` before import admission; a Git-LFS pointer
or other undecodable `.mp4`/`.wav` returns a typed validation error with no
media row, event, receipt, or managed bytes. If `ffprobe` is unavailable,
install it from the ffmpeg package and retry. Generic files retain the
extension-based import path.

Product commands need no configuration file, credentials, or hosted service.
`serve` is only needed when an HTTP editor client is used. Product and nested
mount commands support `--json` as the stable machine surface: exactly one
five-key envelope (`ok` / `data` / `error` / `receipt` / `idempotency_key`).
`doctor --json` is the deliberate exception: it emits its diagnostic object
(`state`, `checks`, `next_action`, `ok`), while `serve` and `backup` do not
offer `--json`. Exit codes are stable: `0` success, `1` typed SDK error, `2`
usage/parse error.

## Product families

| Family | Verbs | Notes |
| --- | --- | --- |
| `projects` | `create`, `list`, `show`, `update`, `select`, `current` | `select` sets a workspace/user routing preference; `current` reads it back; the slug is immutable |
| `timelines` | `create`, `list`, `show`, `save`, `archive`, `unarchive`, `history`, `diff`, `visualize`, `render` | `list --include-archived` is the recovery read; `unarchive` is safe to repeat; `visualize` emits a run-owned evidence pack and `render` accepts a pinned canonical timeline |
| `media` | `import`, `list`, `show`, `verify`, `relocate`, `relate` | `verify` checks every matching `--realm` location by default; use `--location-id` or `--locator` for one; `relocate` requires `--realm`; `relate` has the frozen five-kind `--kind` |
| `tasks` | `create`, `list`, `show`, `cancel`, `retry`, `events` | `create` admits one immutable task (`--capability` + JSON `--spec`) |
| `runs` | `list`, `show`, `cancel`, `retry-failed`, `events` | `retry-failed` is the batch-retry surface (all-failed-children or explicit `--task` subset) |

`projects select` persists a file-side routing preference (workspace scope by
default, or `--scope user`) without a database receipt. With
`ASTRID_PROJECTS_ROOT` set and no explicit `--cwd`, the workspace preference is
stored under that projects root, keeping disposable roots isolated; pass
`--cwd` when you intentionally want another workspace boundary.
`projects current`
resolves workspace before user scope, verifies the selected ref against the
kernel, and reports the selected project, canonical path, preference path,
and supplying scope. Project-scoped CLI commands may omit `--project` to use
that selection; an explicit `--project` always wins.

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

Both unarchive commands report `changed: false` when the item is already
active. An ambiguous reference name fails closed with candidate ids; retry
with one exact id from the inclusive list.

## Runs & tasks

There is no `runs create` verb anywhere: a run comes into existence through
the kernel, never by hand. Every capability invocation — including
`sdk.invoke(...)` and the typed facades — is admitted into the kernel as a
run with its ordered child tasks (`RunRepository.create` fan-out) and
executes through one lifecycle: admit → claim → start → execute →
complete|fail, with hash-chained events, receipts, attempts, and leases
recording each transition. Status is derived once, in the kernel:
`derive_run_progress_counts` recomputes a run's progress from its child
task rows at read time. The filesystem `<project>/runs/<id>/run.json` is a
write-once finalize-time projection of that state, stamped
`"authority": "kernel"` with `kernel_task_id` / `kernel_run_id` — never an
authority itself; see docs/contracts/run-ledger-contract.md for the
single-ledger contract. `client.tasks.create` admits standalone tasks that
belong to no run. The CLI `tasks`/`runs` families then list and drive that
work — `--project` takes the project slug or id:

```bash
python3 -m astrid tasks list --project demo --json
python3 -m astrid runs show <run_id> --project demo --json --evidence
python3 -m astrid runs cancel <run_id> --project demo --json
python3 -m astrid runs retry-failed <run_id> --project demo --json
```

A run with zero children (or a legacy all-terminal run) may require the
coordinator-only SDK transition `client.runs.close(project, run_id)`. There
is intentionally no operator CLI for `close`: operators should use
`runs cancel` or `runs retry-failed`; coordinators use `close` only when they
own the zero-child lifecycle. Terminal runs remain immutable and cannot be
relabelled.

For read-only event observation, `astrid.read_events(project, run_id,
projects_root=..., verify=True)` prefers a run's optional local
`events.jsonl` projection. When that file or run directory is absent — as is
normal after a portable backup/restore — it falls back to the canonical
SQLite `core.run` stream and returns `EventStreamRecord(source="kernel", ...)`.
The fallback preserves event ids, order, kinds, and integrity hashes and
fails closed with `CapabilityEventLogError` on a head, link, or hash mismatch;
it never creates a projection or treats filesystem files as status authority.

## Operational families

```bash
python3 -m astrid serve [--host HOST] [--port PORT] [--projects-root PATH]  # HTTP editor bridge
python3 -m astrid doctor [--json]                                           # read-only health check
python3 -m astrid backup create [--out PATH]                                # staged, validated backup
python3 -m astrid backup restore <BACKUP_PATH>                              # journaled restore
```

Backups are portable by default: readable `external_local` files are copied
once per content hash, while every original locator remains in the backup
manifest and restored media provenance. Restore rebases those locators to the
verified backup-owned bytes inside the destination root atomically. If an
external source is missing or changes while a backup is being created, the
backup fails before publication; if a backup snapshot is missing or mutated,
restore fails before touching the live root. Older backups without external
snapshots restore their database but report unresolved external locators.

## The SDK is the pack surface

Packs ship capabilities (executors, orchestrators, elements). They are not
gateway commands. Run them through the SDK:

```python
import astrid.sdk as sdk

result = sdk.discover(include_installed=False)   # in-tree pack inventory
cap = sdk.get_capability(
    "editorial.transcribe", kind="executor", include_installed=False,
)
result = sdk.invoke(
    "iteration.experiment_review",
    kind="executor",
    include_installed=False,
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
a canonical kernel slug/UUID/ULID and optionally enforces `expected_version`;
use `astrid timelines render <ref>` for the product CLI. Managed visualization
likewise resolves the canonical kernel timeline and pins its actual stream
head. There is no legacy filesystem authority.

### How capabilities execute

Every capability executes through one kernel path:

- **Admission + execution** — `sdk.invoke(...)` and the typed facades admit
  the invocation into the kernel (run + child task) and drive it through
  claim/start/execute to complete|fail. The pack's `run.py` executor remains
  the unit of work: the runner invokes it as a subprocess
  (`ASTRID_INTERNAL_INVOCATION=1`); every executor with a `runtime_module`
  works this way, outputs are file-based and returned in the
  `InvocationResult` manifest, and the finalize-time `run.json` projection
  lands under the project's `runs/<run-id>/` tree.
- **Custom drivers** — code that drives an admitted task with its own loop
  implements the kernel `TaskHandler` protocol (`astrid.core.task_executor`,
  `execute(task, staging_dir)`); the executor service wraps it with the
  same fences — status versions, leases, receipts — every other execution
  uses.
- **Never invoke `run.py` modules directly** — the canonical-entrypoint
  guard refuses it; `astrid.sdk.invoke` is the entry.

## Retired legacy surface

The legacy task-mode CLI (`attach`/`next`/`start`/`ack`, plus the retired
`executors`/`orchestrators` verb families) and the old filesystem task-run
store are gone — use the eight-family CLI and the SDK.
`text_analysis.summarize` and `builtin.agent_probe` were removed with the
task-mode runtime. Legacy pre-kernel data under `projects/` migrates with the
scripts in `scripts/migrations/v10/` (see its `MIGRATION.md`).

## Per-project plan.md

Every project has a `plan.md` at its root — a per-project markdown doc for
live, human/agent-readable working notes (current focus, open threads, key
decisions, scratch notes).

- **Read on create/show.** After `projects create` or `projects show`, read
  `<project>/plan.md` alongside the project row as part of orienting. New
  projects ship with an empty skeleton; that's fine.
- **Update when project-level state changes.** A new focus, a closed thread, a
  settled decision, a fresh open question. Don't log ephemeral per-run state.
- **Refactor when it grows tangled.** Promote stale items to an `## Archive`
  section, keep `## Current focus` short, and trim `## Open threads` past ~10
  entries. Treat it as a living doc, not an append-only log.

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
orchestrators, elements), optional bundled database ownership, structured agent
guidance, and pack-relative resources. Every capability lives in exactly one
pack under `astrid/packs/<pack>/`, declared in a strict-v2 `pack.yaml` manifest.
Capability ids are always qualified as `<pack>.<name>`; bare ids are rejected.
Executor folders use
`astrid/packs/<pack>/executors/<slug>/{executor.yaml,STAGE.md,run.py}` and
orchestrator folders use
`astrid/packs/<pack>/orchestrators/<slug>/{orchestrator.yaml,STAGE.md,run.py}`,
with optional local `src/` modules. Element folders live at
`astrid/packs/<pack>/elements/<kind>/<id>/{component.tsx,element.yaml}` where
kind is `effects`, `animations`, or `transitions`. Every bundled pack ships
`skill/SKILL.md`; a gitignored `local` pack holds user-owned forks.

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
result = sdk.discover(include_installed=False)   # full in-tree inventory, pack by pack
caps = sdk.get_capability(                       # typed lookup (raises on missing/ambiguous)
    "editorial.arrange", kind="executor", include_installed=False,
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
- Do not edit `$ASTRID_PROJECTS_ROOT/.astrid/astrid.sqlite3` or the event
  streams by hand; mutate through the CLI and SDK only.
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
    include_installed=False,
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
- [docs/guides/cli-journeys.md](../../../../docs/guides/cli-journeys.md) — the eight families, journeys, recovery
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
| `discord_local.command` | Preview, submit once, or recover one Discord generation as an experiment-ready run. |
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
| `iteration.assemble` | Adapt prepared iteration data into canonical iteration artifacts and render-ready hype inputs. |
| `iteration.experiment_import` | Import an unmanaged run root into an experiment without rewriting history or guessing ambiguous associations. |
| `iteration.experiment_prepare` | Normalize an experiment's provider manifests into a provider-independent review model with diagnostics. |
| `iteration.experiment_review` | Render a deterministic HTML gallery comparing provider outputs with prompt, parameters, warnings, and diagnostics. |
| `iteration.prepare` | Collect thread provenance, quality scores, and candidate runs into iteration prepare artifacts. |
| `media.clip_extract` | Extract a clip segment from a video using ffmpeg stream copy. |
| `media.gif_search` | Search GIPHY for GIF or sticker assets and optionally download a selected rendition. |
| `media.speech_repair_lavasr` | Repair weak-mic speech with hotter pre-lift, fal.ai LavaSR, optional DeepFilterNet3, and a final loudness pass. |
| `moirae.moirae` | Run a Moirae screenplay through the terminal-as-cinema renderer to produce a video. |
| `reigh.open_in_reigh` | Copy or stage generated timeline+assets for handoff into a Reigh project. |
| `reigh.publish` | Publish a finished timeline + assets pair into a Reigh project via API. |
| `reigh.reigh_data` | Fetch canonical Reigh project data through the reigh-data Edge Function. |
| `reigh.spatial_audio_page` | Build a static page that mixes Foley tracks anchored to spatial rectangles via Web Audio. |
| `rendering.html_canvas_effect` | Scaffold a local Remotion HTML-in-canvas effect element. |
| `rendering.render` | Render a hype timeline to an .mp4 output through the selected backend. |
| `rendering.sprite_sheet` | Generate, slice, and preview GPT Image sprite sheets for batch image work. |
| `rendering.timeline_storyboard` | Build a static visual storyboard of image inputs associated with timeline shots. |
| `rendering.timeline_visualize` | Build a deterministic, agent-navigable evidence pack from managed timeline event logs. |
| `runpod.exec` | Execute a script on an existing RunPod pod and download artifacts. |
| `runpod.provision` | Provision a RunPod GPU pod and emit a pod handle for later exec/teardown. |
| `runpod.pull` | Pull artifacts from an existing RunPod pod into local storage. |
| `runpod.session` | Composite provision → exec → teardown session with guaranteed cleanup. |
| `runpod.teardown` | Terminate a RunPod pod. Idempotent. |
| `seedance_local.reference_video` | Generate one Seedance 2.0 video from ordered local image references and/or a reference clip. |
| `stream_content.clip_candidates` | Score transcript windows as publishable stream clip candidates. |
| `stream_content.segment_map` | Fuse OCR, transcript density, and scene cuts into a complete stream timeline. |
| `training.asset_cache` | Manage the repo-local hype asset cache (download, prune, list). |
| `training.pool_build` | Build the candidate clip pool from triaged source-video scenes. |
| `training.pool_merge` | Merge multiple candidate clip pools into a unified pool for arrangement. |
| `training.search_loras` | Search Hugging Face Hub for LoRAs associated with a base model. |
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
| `video_editing.animate_image` | Two-stage Fal pipeline: edit a reference image with GPT Image 2, then animate it with WAN 2.2. |
| `video_editing.event_talks` | Orchestrate event-talk template, search, holding-screen, and render commands into a finished video. |
| `video_editing.hype` | Run the canonical hype editing pipeline end-to-end (transcribe → cut → render → validate). |
| `video_editing.iteration_video` | Prepare an iteration graph, assemble render inputs, render, and finalize iteration video outputs. |
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
| `effects/model-trends` | Animated stacked-area chart of model-family share-of-conversation, driven by Remotion frame. |
| `effects/neon-orbit-card` | DOM-to-canvas Remotion effect for post-processed cards. |
| `effects/sliding-media` | Full-screen media clip with slide-in/out motion. |
| `effects/text-card` | Anchored text card overlay with built-in fade in/out. |
| `effects/vibe-comfy-asset-overlay` | Asset-driven Vibe Comfy overlay with procedural noodle. |
| `effects/vibe-comfy-bumper` | Procedural Remotion bumper for Vibe Comfy. |
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
