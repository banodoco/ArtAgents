# Exhaustive QA map: capabilities, generation, rendering, packs, and operations

Date: 2026-08-23  
Scope: live agent usage of Astrid's SDK capability surface, generation and
rendering workflows, pack customization, local bridge, and backup/restore.  
This is an agent-journey map, not a claim that every journey passes. Existing
automated tests are regression guards only; the first wave should use the
commands and SDK as a maker/agent would, with a fresh isolated projects root.

## Operating rule for this wave

Every live probe must use a disposable root:

```bash
qa_root=$(mktemp -d /tmp/astrid-capops-XXXXXX)
export ASTRID_PROJECTS_ROOT="$qa_root"
python3 -m astrid doctor --json
python3 -m astrid projects create qa --name "Capability QA" --json
```

Do not invoke pack `run.py` modules directly. Their direct-entrypoint guard
rejects them; use `astrid.sdk.invoke(...)`, a typed facade, or the supported
gateway. Never expose credentials in logs. For generation, prefer dry-run or a
mocked/local deterministic backend in the first pass, then explicitly opt into
real cloud/GPU spend.

Capture for every live journey: the agent's initial goal and assumptions, the
discovery/lookup calls, exact command or SDK arguments, elapsed time, stdout /
stderr, typed error and recovery text, run/task IDs, manifest path, output
files and hashes, warnings/dropped features, provenance sidecar, event stream,
and the next read that proves persistence. Record the moment an agent hesitates
or guesses; that is UX evidence, not noise.

## Surface and authority map

| Surface | Agent entry point | Expected authority / evidence |
| --- | --- | --- |
| Capability inventory | `astrid.sdk.discover`, `get_capability` | Pack/capability DTOs, schemas, ports, aliases, provenance, trust/permissions, generation backend/mode/feature metadata. |
| Capability execution | `astrid.sdk.invoke`, `AstridClient.invoke` | One kernel admission path: run → child task → claim/start/execute → complete/fail; universal result manifest and final `run.json` projection. |
| Typed generation | `astrid.generate.image`, `.video`; audio via `invoke` | Model → mode → backend resolution, requirement validation, warnings, modality manifest, generated artifacts. |
| Typed rendering | `astrid.render`, `support`, `renderer_main`, `RenderContext`; `rendering.render` executor | RenderService plan, support decision, renderer/planner/finalizer resolution, output video, `.provenance.json`, replay bundle on failure. |
| Pack customization | `python3 -m astrid.core.pack.cli ...`; internal renderers CLI; local pack and `.overrides.json` | Discovery precedence, trust eligibility, aliases, forks, dirty state, override resolution evidence. The gateway has no `packs` family; `list`/`status`/`inspect` honor `ASTRID_PACKS_PATH` and repeatable `--pack-root`. |
| Product/bridge integration | `astrid serve`; HTTP bridge | Repository-backed project/timeline read/save and local asset serving; no hidden sidecar authority. |
| Operations | `doctor`, `backup create`, `backup restore` | Read-only diagnostics; staged/journaled database + managed-media backup and restore with integrity proof. |

The public CLI census intentionally has eight families (`projects`,
`timelines`, `media`, `tasks`, `runs`, `serve`, `doctor`, `backup`) and the
`timelines shots` / `media references` mounts. Generation, rendering, packs,
and elements are SDK/internal surfaces, not top-level gateway families. This
boundary is a major discovery test: an agent who tries `astrid generation`
must get a useful redirect to SDK discovery, not invent a legacy command.

## 1. Capability discovery and typed invocation

### Ordinary maker goals

| Goal | Agent journey | Evidence of a good experience |
| --- | --- | --- |
| “What can make an image/video/audio asset?” | `discover(include_installed=False)`; filter `generation_modes`, `generation_backends`, features; inspect `generation.generate_*` STAGE.md only after selecting a candidate. | Inventory is machine-readable, qualified IDs are obvious, unsupported cells are explicit, and the agent can choose model/mode/backend without source grepping. |
| “How do I run this editorial or render capability?” | `get_capability(id, kind=...)`; inspect required ports, output types, safety permissions, aliases and stage instructions; `invoke(..., dry_run=True)`. | Dry-run shows normalized command, destination, environment redaction, and validation without ledger or side effects. |
| “Run it for project `qa` and inspect the result.” | Create project; invoke with `project='qa'` and no `out`; inspect `InvocationResult`, manifest, run events, `client.runs.show`. | Outputs land in the project run tree; result IDs, output paths, receipts, attempts, and terminal status agree across SDK, CLI, and filesystem. |
| “Watch a long run.” | `read_events(..., verify=True)` for a completed run; `subscribe_events(..., follow=True)` while a live run executes. | Ordered hash-verified events expose admission, claim, start, progress, output, and failure/retry; corruption fails closed with a recovery action. |

### Tricky tasks

- Start from a natural-language goal with no known capability ID. Ask the
  agent to enumerate candidates, explain why it selected one, and identify
  missing credentials/binaries before invocation.
- Try bare IDs (`render`, `fade`) and wrong kinds (executor requested as
  orchestrator, element requested as executor). The agent should see qualified
  candidates and a next action, not a traceback.
- Resolve a deprecated alias and its canonical ID; compare returned handle
  provenance and alias metadata. Repeat through `invoke` and a typed facade.
- Invoke an element intentionally and verify a clear “elements are not
  invokable” explanation plus the render-oriented next step.
- Invoke without `kind`, without `project`, with an unknown project, with a
  project plus `out`, and with a changed request under the same idempotency
  identity. Check whether each failure tells the agent exactly what to change.
- Repeat an identical invocation. Verify deterministic idempotent replay does
  not create duplicate runs/media/events, then change one input and verify the
  mismatch is rejected before side effects.
- Cancel a running task/run, retry a failed task, and close a zero-child/all-
  terminal run. Confirm the next read and events explain terminal state.

### Friction hypothesis

Cold `sdk.discover(include_installed=False)` took about 30 seconds in the
isolated probe and returned 66 executors, 12 orchestrators, 15 elements, and
22 packs. A maker-facing agent may wait, repeat the scan, or fall back to
source-grepping. Measure cold vs warm discovery, serialize the inventory for
reuse, and test whether filtered discovery or cached metadata makes the next
decision feel immediate. Also test the mismatch between SDK's rich discovery
surface and the CLI's deliberately eight-family census; docs need to say
“generation/rendering are capabilities, not gateway verbs” at the point of
confusion.

### Existing guardrails to reuse later

`tests/test_sdk_public_surface.py`, `tests/test_capability_alias_resolver.py`,
`tests/core/test_capability_registry_kernel.py`,
`tests/core/test_executor_runner_errors.py`,
`tests/test_run_ledger_conformance.py`, and
`tests/core/test_generation_backend_registry.py` are useful regression guards,
but they do not replace the live discovery/hesitation study.

## 2. Image, audio, and video generation

The generation taxonomy is model → mode → backend. Current discovery reports
backends `cloud`, `codex`, `local`, `wavespeed`; modes include image `t2i`,
`i2i`, `edit`, `inpaint`, `outpaint`, `upscale`, video `t2v`, `i2v`, `flf`,
`v2v`, `video-edit`, and audio `music`, `tts`, `sfx`. Presence in the taxonomy
does not mean a model/backend cell is wired: the agent must inspect the model
registry and capability stage.

### Shared generation journey

1. Discover the modality/model/mode/backend cell and read that folder's
   `STAGE.md`.
2. Dry-run through the typed facade or `sdk.invoke`; verify resolved mode,
   execution backend, required inputs, command, and no ledger entry.
3. Run with a deterministic local/mock backend or an explicitly approved cloud
   credential; inspect the universal and modality manifest.
4. Check every output exists, hashes correctly, probes to the declared type,
   and is linked to the run/task/media ledger. Inspect warnings,
   `dropped_features`, actual endpoint/template, request ID, cost, and seed.
5. Re-run the same request and then one changed request; compare idempotency,
   output identity, and run/event counts.

### Image-specific tasks

| Task | Tricky/recovery variants | Evidence |
| --- | --- | --- |
| Text-to-image with `z-image`, `flux-dev`, or `qwen-image-2512` | Omit mode and rely on inference; force ambiguous backend; unsupported negative prompt; count >1; fixed seed; prompt file batch. | Resolved `t2i`, backend, output count, warning for dropped feature, stable seed and manifest. |
| Image-to-image | Provide one `image_ref`; use a missing path, directory, URL, corrupt image, or wrong model; compare inferred `i2i` vs explicit mode. | Preflight failure before network/import; resolved reference path; no partial output on invalid input. |
| Edit/inpaint/outpaint/upscale | Omit explicit mode (must fail for explicit-only modes); wrong model/mode pair; upscale without image; invalid factor/target. | Error says mode must be explicit and names available modes/required input. |
| OpenAI-specific image executor | Use `generation.generate_image_openai` with prompt file; missing key; one bad prompt in a batch; dry-run/no-open preset. | Prompt-file contract, partial manifest behavior, credential error without key leakage, output manifest. |

### Audio-specific tasks

- Generate music with Stable Audio, MiniMax, ACE-Step, and WaveSpeed cells;
  compare prompt-only, lyrics-required, and `instrumental=true` requests.
- Try reserved `tts`/`sfx` modes and verify “not wired this sprint” is
  actionable rather than presented as a selectable working mode.
- Omit prompt, supply unsupported lyrics to Stable Audio, invalid duration,
  unsupported format, and a prompts-file model override without explicit mode.
- Remove `FAL_KEY` / `WAVESPEED_API_KEY`, use a benign fake key only in an
  isolated environment, and verify a typed preflight/auth failure, no secret in
  stderr/manifest, and a recoverable instruction.
- Verify audio duration/codec metadata is best-effort but honest when ffprobe
  is absent, and verify partial-output manifests for one failure in a batch.

### Video-specific tasks

- Run `wan-2.2`/`ltx-2.3` across t2v, i2v, and flf cells; verify image-ref and
  image-end-ref inference and model-specific unavailable cells.
- Attempt `flf` without the end frame, i2v with an unreadable frame, cloud
  without `FAL_KEY`, local without ComfyUI, and unavailable `v2v`/`video-edit`.
- Use prompts-file entries with a model override but no matching explicit mode;
  compare the error to the documented FLAG-004 behavior.
- Verify output ffprobe metadata (duration, fps, resolution), partial manifest,
  source URL handling, cost/request ID, and that a real backend failure does
  not silently switch execution backends.

### Reproduced live friction

- The generation stage docs show direct `python -m astrid.packs...run` quick
  starts, but direct execution is rejected by the canonical-entrypoint guard
  with a message to use the SDK. An agent following the visible quick-start
  will hit a dead end. First-wave UX test: give a fresh agent only the stage
  snippet, observe the failure, then measure whether the recovery points to a
  runnable SDK call and how much guessing is needed.
- `sdk.generate.image(..., image_ref=...)` infers `i2i` even for an edit-only
  model and returns “model does not support i2i; available edit”. This is
  technically correct but ergonomically surprising; test whether discovery
  exposes explicit-only modes before the agent has to fail once.
- SDK generation dry-run correctly resolved image t2i and video i2v, but a
  video flf dry-run did not catch a missing end frame; the normalized command
  omitted the required `--image-end-ref`. The first real execution wave must
  assert requirements are enforced at the same boundary as dry-run, or clearly
  label dry-run as command-only validation.

## 3. Rendering lifecycle, provenance, and elements

### Maker journeys

| Goal | Journey | Evidence / friction to watch |
| --- | --- | --- |
| “Preview this timeline.” | Call `astrid.support(backend, timeline_path=..., assets_registry_path=...)`; use the support reasons to choose strict renderer or planner; invoke `rendering.render`. | Support report must say which asset/schema/tool requirement blocks or enables render. A qualified renderer must fail closed; legacy policy should explain auto-routing. |
| “Render a final video.” | Timeline + optional asset registry + theme → `astrid.render` or project-scoped executor → inspect `.mp4` and `.provenance.json`. | Output name, bytes, media profile, selected planner/renderer/finalizer, input hashes, trust evidence, audio ownership, element resolution, and cleanup. |
| “Why did render fail?” | Inspect typed renderer error and retained replay bundle; run renderer `replay` with pinned request/manifest digests. | Error is self-contained and redacted; replay does not require re-running the editorial pipeline or leaking local secrets. |
| “Add a visual element.” | Discover element (`effects/...`, `animations/...`, `transitions/...`), read manifest/STAGE, add it to a fixture timeline, render, inspect layer order and element asset staging. | Correct active-theme/local/builtin precedence; declared assets appear under render-hash staging and are cleaned afterward; unsupported/bad IDs fail clearly. |
| “Inspect a timeline without mutating it.” | Invoke `rendering.timeline_visualize` with cold selectors, then navigate using `agent-view/action-index.json` and `--from-view`/`--focus`. | Evidence pack is deterministic/read-only; timeline manifest and event logs are byte-stable; pages/filmstrip/diagnostics agree. |

### Adversarial render tasks

- Missing timeline, malformed JSON, missing `@banodoco/timeline-schema`, bad
  `assets_registry`, unknown asset key, unsafe path, remote URL without range,
  hash mismatch, and media that probes as the wrong type.
- Conflicting `engine` and `backend`; unqualified renderer selector; qualified
  renderer that reports unsupported; planner fallback only when explicitly
  allowed; invalid output name (`../evil.mp4`, non-`.mp4`).
- Overlapping visual tracks (`brand`, `captions`, `fx`, `broll`, `source`) to
  observe the reversed visual-track order. Ask the agent to predict the layer
  stack before rendering; compare prediction to frames.
- Render with custom theme, `theme_overrides`, local forked effect assets,
  audio-reactive effect, still/video/audio clips, and an empty registry.
- Kill/interrupt during asset staging, renderer execution, and finalization;
  rerun and verify cleanup, no mixed output, provenance linkage, and replay
  bundle retention.

### Rendering support probe

The live probe `python3 -m astrid.core.rendering.cli support rendering.ffmpeg
--json` returned `supported: false` with the concrete reason that an assets
registry is required. Remotion support reported the missing canonical timeline
schema package. This is useful behavior only if the agent is trained to treat
`reasons` as the next action; test whether a maker can fix the environment from
the report without source inspection.

Existing rendering suites to use later as guards include
`tests/packs/rendering/test_render_facade.py`, `test_render_facade_run_ownership.py`,
`tests/core/rendering/test_provenance.py`, `test_registry_matrix.py`,
`test_replay.py`, and the `timeline_visualize_*` tests.

## 4. Packs, aliases, forks, overrides, and trust

### Agent-shaped customization flow

1. Discover a capability and inspect its pack, source kind, permissions, trust,
   version, stage, and child graph.
2. Decide whether the change is a public rename (alias), a private behavior
   copy (fork), or transparent routing to an existing replacement (override).
3. Create or locate a local pack, fork shallow/deep as appropriate, edit only
   the fork, validate it, and inspect dirty/provenance state.
4. Set an override keyed by the canonical ID, then resolve both canonical and
   alias IDs. Render/invoke through each consumer and inspect resolution
   evidence (`requested`, alias chain, from/to override, source pack, digest,
   trust eligibility).
5. Remove the override or discard/re-fork; verify builtin behavior returns and
   no stale registry cache remains.

### Tricky pack tasks

- Alias chains and cycles; deprecated alias still resolves with metadata;
  bare/unqualified alias; alias pointing to absent target.
- Shallow fork of an orchestrator with child references; deep fork of the
  child graph; element fork (shallow only); overwrite existing fork; upstream
  change after fork; dirty vs conflict state.
- Override canonical renderer/planner/finalizer separately; alias resolves
  before override; invalid/missing/ineligible target fails closed; facade
  `rendering.render` cannot be accidentally replaced by a renderer-kind entry.
- Competing source/installed/extra/local pack precedence; malformed external
  pack must be skipped for inspection without shadowing an executable pack.
- Trust/permissions: an agent should see disclosure-only permissions and stop
  before executing a pack requiring unavailable or unapproved capabilities.

### Reproduced discovery friction

The pack docs describe aliases/forks/overrides, but packs are managed by the
internal module CLI (`python3 -m astrid.core.pack.cli`), not a gateway family;
`python3 -m astrid packs ...` is intentionally rejected. The supported list/
status/inspect commands accept `ASTRID_PACKS_PATH` or repeatable `--pack-root`,
while there is no `fork` or `override` verb. The element CLI explicitly says the override subcommand was removed. A
live agent needs a discoverable supported workflow (internal API/file contract,
or a clear command) rather than being sent from docs to a nonexistent command.
First wave should give an agent the alias-vs-fork-vs-override question and
observe whether it can complete it without source grepping.

Relevant later guards: `tests/packs/test_pack_discovery.py`,
`test_pack_resolver.py`, `test_pack_local_priority.py`,
`test_pack_rendering_extensions.py`, `tests/test_capability_alias_resolver.py`,
`tests/test_dirty_fallback.py`, and `tests/core/test_elements_cli.py`.

## 5. Serve/API integration boundary

`astrid serve --no-open-editor` composes the repository-backed bridge at the
canonical `.astrid/astrid.sqlite3` store. The live HTTP routes are:

```text
GET   /health
GET   /projects
GET   /projects/:project/timelines
GET   /projects/:project/timelines/:timeline
POST  /projects/:project/timelines/:timeline/save
GET   /projects/:project/timelines/:timeline/assets/:key
HEAD  /projects/:project/timelines/:timeline/assets/:key
OPTIONS any path
```

Agent/browser tasks:

- Start on a cold root, parse the readiness line, call health/projects/list,
  load by slug/UUID/ULID, save valid timeline documents, reload, and compare
  config version/history with CLI/SDK.
- Save stale versions concurrently; malformed body, boolean version, bad
  registry shape, missing project/timeline, unknown route, and schema-incompatible
  payload should return typed status/body and zero unintended writes.
- Exercise CORS allowed/unknown origins, OPTIONS, GET vs HEAD, full/ranged /
  open-ended/suffix asset requests, ETag/304, unsatisfiable range/416, unsafe
  path, HTTP-only locator, unverified/tampered media, and missing asset key.
- Explicitly test that serve has no shots/references/media routes and that an
  editor does not silently assume those exist.
- Restart the bridge and prove persisted state comes from the repository,
  never sidecar/FSA fallback. Hold a second owner and verify the lock failure
  is typed and recoverable.

Live smoke result: an isolated server returned a ready line, 200 health,
project list, empty timeline list, and 404 JSON for `/bad`, then exited cleanly.
The remaining high-value work is browser-like saves, range requests, contention,
and cross-checking those reads against product CLI/SDK.

## 6. Doctor, backup, restore, and disaster recovery

### Ordinary operational goals

| Goal | Journey | Proof |
| --- | --- | --- |
| “Is this root usable?” | `doctor --json` before and after project/media creation. | Six checks: Python, data paths, media paths, SQLite quick check, FK integrity, schema versions; no repair/write. |
| “Protect this project.” | Import representative media; `backup create --out <dir> --json`; inspect `backup.json`, DB, managed media. | Metadata version/time/pack migrations/media count/SQLite pages; media bytes and hashes; secrets/staging/cache/logs/packs excluded. |
| “Recover after loss.” | Destroy only the disposable root's live DB/media; `backup restore`; reopen client/CLI; inspect projects, media, timeline and doctor. | Staged validation, journal/recovery boundaries, exact IDs/content, quick check/FK/schema all pass. |
| “Reject a bad restore safely.” | Corrupt backup DB, metadata, media, FK, schema version, missing files; restore into populated root with/without `--force`. | Typed validation error; live DB/media byte-identical; no partial swap; next retry works. |

The isolated smoke created one project and one managed media file, backed up to
`astrid.sqlite3` + `media/` + `backup.json`, restored into a fresh root, and
doctor reported quick check/FK/schema success. Follow-up live tasks must cover
same-destination backup overwrite, hard-death boundaries, lock contention,
WAL/SHM presence, symlinks, very large files, secret-like filenames/content,
missing/corrupt journal, and restore while a second client is open.

## 7. Critical reproduced cross-surface finding

In an isolated root, this sequence succeeded:

```text
projects create qa                    → .astrid/astrid.sqlite3
sdk.invoke(generation.generate_audio, project='qa', project_root=root)
                                         → root/kernel.sqlite3
runs show <returned run id> --project qa → not_found
```

The SDK invocation returned `ok=false` for missing-input/credential cases,
but `InvocationResult.error` was `None`, and the returned run ID was not
visible to the product `runs` family. Inspecting the root showed both
`.astrid/astrid.sqlite3` and `kernel.sqlite3`. The implementation currently
has separate `_kernel_invoke` and application-store path choices while
`astrid.core.kernel.read` has compatibility logic for both. This is a
P0 integration journey: any agent that invokes a capability and then follows
the documented “inspect with runs show/events” recovery path can be told that
its run does not exist. First execution wave should reproduce this with a
successful deterministic local executor, a failed credential preflight, and
an orchestrator; assert one canonical store, shared run/task/media/events,
and non-null structured failure detail.

Do not paper over this in a QA report by reading both DBs. The user-visible
contract is one ledger and one next action.

## Prioritized first execution wave

1. **Ledger continuity (P0):** fresh root; project create; one dry-run and one
   successful deterministic SDK executor; then `runs list/show/events`, typed
   client reads, manifest, and filesystem projection. Repeat failed generation
   and orchestrator. Record whether all surfaces see one run.
2. **Discovery-to-action (P0):** cold/warm discovery timing; natural-language
   model/mode/backend selection; stage guidance; dry-run vs real preflight;
   direct-run quick-start recovery; missing credentials/binaries with safe
   messages.
3. **Render proof (P0):** support report → render → ffprobe/output/provenance;
   no-schema/no-assets/unsupported backend; replay retained failure; layered
   elements and asset cleanup.
4. **Bridge parity (P1):** serve readiness/health, valid/stale/malformed saves,
   range/HEAD/ETag asset reads, restart and concurrent saves; compare to the
   product timeline/CLI view.
5. **Pack UX (P1):** alias/fork/override decision task, local precedence,
   dirty detection, trust fail-closed behavior, and doc/CLI path completion.
6. **Operational recovery (P1):** doctor before/after; backup/restore round
   trip; corruption and hard-death recovery; lock contention and secret
   exclusion.
7. **Creative stress (P2):** image/audio/video modality matrix, partial
   batches, unsupported features, fixed seeds, media import → timeline →
   render → provenance, then archive/backup/restore and replay.

For each wave, turn any observed friction into a small reproducible agent task
with a pass criterion and a regression guard. Keep fixes separate from this
map so the next Luna wave can retest the same user journey rather than merely
re-run unit tests.
