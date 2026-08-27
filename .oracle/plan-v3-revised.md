Reading additional input from stdin...
2026-08-27T11:27:59.501201Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-27T11:27:59.501228Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-27T11:27:59.501231Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
OpenAI Codex v0.149.1
--------
workdir: /Users/peteromalley/Documents/reigh-workspace
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: high
reasoning summaries: none
session id: 01a042fa-0f05-75a0-ad04-7aa4ba599c43
--------
user
REVISION BRIEF (read-only)

You are the planner revising your own plan for the megado run on Astrid (worktree Astrid-megado). Exploration results are IN — all six areas returned verified file:line evidence.

INSTRUCTIONS
1) Integrate the verified corrections below into the tasklist/batches MINIMALLY (edit tasks/acceptance criteria only where required).
2) Explicitly reject any North Star anti-pattern; bias toward ELEGANCE and SIMPLICITY — cut anything not pulling its weight.
3) List any NEW areas worth exploring or potential issues introduced.
4) If nothing material changes, answer exactly: STABLE

VERIFIED CORRECTIONS TO INTEGRATE
A. Registry entries validating shape = {file: <absolute CAS path>, content_sha256} after `MediaService.import_file`; render path validates + rebases managed locators. Intro assets MUST be imported into managed media BEFORE render (repo-external in-place refs are rejected).
B. AssetEntry.generationId: no generation manifest exposes a usable generation id (only content_hash + PNG tEXt chunks with prompt/model/seed). Omit generationId usage; persist prompts + variants INSIDE storyboard records; document PNG tEXt as incidental provenance.
C. Parity-safe rule adopted: final-slides PNGs bake title/bullets/mink ⇒ for the intro application, image-asset sections compile to EXACTLY 3 clips/section (broll plate + caption + VO audio) + brand clip = 76 clips/50 assets, preserving the parity oracle vs main v13. Ordinary non-baked storyboards compile title/bullets/mink as live text clips instead.
D. alt_render (slides-pyramid-full pngs) become variants[] entries; active_index selects final-slides render.
E. Dead slide slug idea2_example has NO timeline segment — exclude from storyboard sections.
F. Schema/loader placement: astrid/core/storyboard/ (auto-packaged; jsonschema dep exists). Compiler stays unpackaged at scripts/build_storyboard.py. Storyboard JSON authored project-local (outside git), plus an evidence copy under .oracle/evidence/.
G. Timing independence: per-section timing.hold overrides + optional --vo-align plan.json snapping preserved as planned; shots registration (--register-shots) DEFAULT OFF for v1 (shots mount lacks update/delete; defer).

===== NORTH STAR =====
# North Star — Astrid unified execution

## The desirable end state

Astrid v10 as **ONE store and ONE execution path**: every durable fact lives in the
SQLite kernel (projects, timelines, shots, references, tasks, runs, media, evidence,
receipts, events); every capability invocation — executor or orchestrator — runs as a
kernel run+task (admit → claim → start → execute → complete|fail) with hash-chained
events, receipts, attempts/leases, and managed outputs. `sdk.invoke` is the thin
admission wrapper. The filesystem `run.json` is at most a derived projection of the
kernel run — never an independent authority. Docs describe exactly what ships; the
suite and empirical process runs prove it.

## Enduring qualities and invariants to preserve

- **Single authority**: the kernel writer + UnitOfWork + receipts + events is the only
  state. No second store, no silent divergence path, no eventlog-only escape for an
  existing kernel timeline.
- **Every run is observable**: leases, attempts, retries, expiry, and the full event
  chain make any execution auditable, resumable, and replayable.
- **Honest docs**: no overclaims (e.g. "admitted tasks run" only when a driver ships);
  documented limitations are real limitations.
- **Elegance**: KISS / YAGNI. One generic adapter beats 50 bespoke ones; relax the
  completion contract minimally; cut scope that isn't pulling its weight.
- **Verified empirically**: every claim backed by a runnable process, test, or probe —
  not narrative.

## Anti-patterns to avoid

- A second ledger that must be kept "consistent by convention."
- Kernel/eventlog divergence (orphaned receipts, silent downgrades).
- Ghost verbs or docs that claim behavior that does not exist.
- Per-executor adapters where one generic path would do.
- Scope creep disguised as architecture (serve/GPU supervision beyond what execution needs).

## What aligned progress looks like

Each batch leaves the kernel as the single execution authority: more invocation paths
admitted as kernel tasks, fewer places that write run.json, docs and tests converging
on one ledger, and every gate (suite, process runs, oracle review) passing before the
next batch starts.

===== AGENT GOAL =====
# Agent Goal — declarative storyboard layer (megado run)

[North Star](./northstar.md) — adopted in place from prior campaign; sha256 recorded in custody.md. This run advances the ONE-store principle by making the kernel-managed timeline the compiled output of a versioned storyboard source, with generations/prompts/variations first-class instead of sidecar convention.

## Objective
Deliver a general, versioned **storyboard data layer** plus compiler inside the Astrid repo, proven end-to-end by re-rendering the existing Astrid intro (astrid-intro project) from it.

Deliverables
- D1 `storyboard.schema.json` + loader/validator: meta(canvas/style) ; sections[] with nav tabs-state, ordered typed blocks: title, bullets, text, image(gen|asset), vo(text), video(gen|asset), mink slot directive {pose,anchor,scale}; every gen carries full spec {prompt,model,refs,seed?} and resolution fields (media_id|content_hash|path) + variants[] + active_index.
- D2 Enrichment/linkage conventions documented + implemented where cheap: vo blocks ↔ transcript timing (plan.json), images ↔ prompts persisted beside assets, timeline asset entries use AssetEntry.generationId when the image came from an Astrid generation, section→shot registration via `timelines shots` mount behind a flag.
- D3 Compiler `scripts/build_storyboard.py`: storyboard.json → managed timeline config+registry → `timelines save <slug>` (+`--render`). Timing model: default constant hold; `timing.hold` per block/section overrides; optional `--vo-align plan.json` snapping section starts to VO segment times (independent-of-length editing requirement).
- D4 Intro application: author `build/astrid-intro.storyboard.json` (25 slides: verbatim vo_text+captions from plan.json/captions, pyramid title/bullets equivalents, image=final-slides png as asset, original codex prompt preserved under history) → compile → save → render → open.

## Non-goals
No UI editor; no kernel core schema changes beyond using existing fields/mounts; no migration of other projects; English only; no style redesign.

## Model policy (user-pinned)
- Oracle/planner/[XHARD]: **grok-4.6** (grok CLI). Fallback if unavailable: GPT-5.6 Sol via `codex exec`.
- Explorer/normal executor: **GLM-5.3 Flash** (`launch_hermes_agent.py --model=zhipu:glm-5.3`, fallback `zhipu:glm-5.2`).
No automatic routing; pinned models authoritative unless evidence shows unavailability (then report + fallback as declared above).

## Done criteria
1. Validator accepts sample + intro storyboards; rejects malformed (missing nav/blocks/dup slug).
2. Compiler compiles intro storyboard to a NEW managed timeline; `timelines show` reports ≥76 clips… expected exact = current main content parity (76 clips/50 assets ± documented deltas).
3. Render of that timeline ≈177±3s, plays, contains all 25 slide visuals (spot-check 3 frames).
4. One regeneration variant demonstrably recorded (variant entry + picked active) without changing bytes of others.
5. Evidence matrix maps every criterion → command/path/result. grok oracle PASS per batch + final review (≤3 passes).

## Validation commands
- `python3 scripts/build_storyboard.py validate build/astrid-intro.storyboard.json`
- compile/save/render pipeline as in D3/D4 against ASTRID_PROJECTS_ROOT=/Users/peteromalley/Documents/reigh-workspace/astrid-intro-projects
- focused pytest for schema/validator (new tests/test_storyboard_schema.py)

## Sync/authorization
Commit batches on branch megado/oracle-run-storyboard; push that branch to origin authorized at finish. Opening local videos/files authorized. Never merge to main.

## Stop conditions
Blocked if grok AND codex both unavailable for oracle (report + halt after safe checkpoint). Escalate scope expansion beyond D1–D5.

===== CURRENT PLAN (tasklist tail) =====
# 1) TASKLIST

Execution policy: all implementation tasks are proposed **normal**, assigned to GLM-5.3 Flash with the declared GLM-5.2 fallback only upon demonstrated unavailability. No task meets the exceptional `[XHARD]` threshold: the work decomposes into bounded schema, compiler, SDK-linkage, fixture, and empirical-validation units whose failures are locally observable. Grok-4.6 performs each batch gate and final review, with the declared GPT-5.6 Sol fallback. Each batch ends in a reviewed commit; no dependent batch begins before its checkpoint is `PASS`.

## Batch 0 — Freeze compiler semantics and protect the baseline

Tasks:

- Reconcile `.oracle/custody.md`, current dirty paths, carried-forward fixes, branch/ref, and the external intro-project mount. Preserve unrelated work without folding it accidentally into storyboard commits.
- Verify the intro store’s exclusive-owner state before any later mutation; decide whether execution must stop the owner or use its supported route.
- Record settled answers for block-to-clip behavior, generation identity, prompt persistence, intro storyboard location, and rerun-safe shot registration.
- Lock a parity oracle from:
  - `build/slides-manifest.json`
  - `build/segments/plan.json`
  - `build/make_slide_html.py`
  - `build/build_timeline.py`
  - current kernel timeline `main`
- Define the exact timing rules: section-start calculation, default hold, section/block override precedence, VO-aligned starts, and how multiple video blocks within one section are placed.

Checkpoint acceptance criteria:

- Read-only probes confirm 25 sections, 76 clips, 50 assets, 177.53s authored duration, and current `main` version/content.
- The semantics above are written unambiguously and preserve exact intro parity without ignored renderable blocks or duplicated baked text.
- No intro kernel mutation occurred; protected dirty paths remain intact.
- Grok oracle `PASS`.

Classification: **normal** — contract reconciliation over existing, inspectable APIs and fixtures.

## Batch 1 — Versioned storyboard schema and reusable loader

Tasks:

- Add `astrid/core/storyboard/storyboard.schema.json` with an exact `schema_version` and strict object shapes for:
  - `meta.canvas` and `meta.style`
  - ordered `sections[]` with unique semantic slug
  - required navigation tab-state
  - section/block timing
  - ordered typed blocks: `title`, `bullets`, `text`, `image`, `vo`, `video`, and `mink`
  - `mink` directive `{pose, anchor, scale}`
  - asset and generation forms for image/video
  - complete generation specifications `{prompt, model, refs, seed?}`
  - exactly one resolution route from `media_id`, `content_hash`, or `path`
  - `variants[]`, `active_index`, and prompt/history provenance
  - VO text/caption plus the settled optional audio-resolution form required for intro parity
- Add `astrid/core/storyboard/{__init__.py,loader.py}` with `StoryboardValidationError`, deterministic JSON-schema errors, semantic duplicate-slug checks, active-index bounds, and storyboard-relative path resolution without mutating the authored document.
- Add a small general-purpose fixture such as `examples/storyboards/minimal.storyboard.json`.
- Add `tests/test_storyboard_schema.py` covering:
  - schema self-validation
  - valid minimal/sample storyboard
  - missing nav
  - missing/empty blocks
  - duplicate section slug
  - invalid block discriminator
  - incomplete generation spec
  - missing/ambiguous resolution
  - out-of-range `active_index`
- Verify the packaged wheel includes the schema.

Checkpoint acceptance criteria:

- The sample validates through the public loader.
- Every required malformed case fails with a deterministic path/message and no writes.
- Schema and loader ship in the installed package.
- No timeline/kernel schema changes were introduced.
- Focused pytest passes and Grok oracle `PASS`.

Classification: **normal** — established JSON-schema and semantic-validation patterns already exist in the repo.

## Batch 2 — Pure storyboard-to-timeline compiler and timing model

Tasks:

- Add `astrid/core/storyboard/compiler.py` with a pure `compile_storyboard(...) -> (config, registry, linkage_plan)` boundary.
- Compile deterministic tracks, clip IDs, registry keys, ordering, output canvas/fps, and timing without writing the kernel.
- Implement:
  - default constant section hold
  - section `timing.hold`
  - block `timing.hold`
  - settled override precedence
  - `--vo-align` input normalization for the intro’s `segments[].text/start/duration`
  - exact section-start snapping by slug
  - text/VO consistency checks
  - multiple video blocks per section
  - active-variant selection
- Compile VO into the settled audio/caption representation and preserve verbatim spoken/caption text.
- Map generation provenance into existing valid surfaces:
  - prompt/model/refs/seed in `clip.generation`
  - `generationId`/`variantId` in `AssetEntry` only when authentic
  - `content_hash` normalized to registry `content_sha256`
- Handle title/bullets/text/mink according to Batch 0’s parity-safe rule, ensuring ordinary non-baked storyboards produce edited material while the intro does not double-render content already baked into final-slide images.
- Validate compiled output with `canonical_timeline_config`/timeline validation and `validate_registry` before returning it.
- Add pure tests for deterministic compilation, stable IDs/order, timing precedence, VO alignment, multiple videos, active variants, invalid references, and repeat-byte equality.

Checkpoint acceptance criteria:

- The compiler produces render-valid timeline and registry objects without side effects.
- Timing changes alter timing only, not prompts or asset bytes.
- Switching one `active_index` changes only the selected asset/clip provenance.
- Multiple video blocks survive as distinct edited clips.
- Focused tests pass and Grok oracle `PASS`.

Classification: **normal** — deterministic transformation with canonical validators and golden tests.

## Batch 3 — Kernel linkage, managed media, shots, and executable script

Tasks:

- Add the thin checkout entry point `scripts/build_storyboard.py` with:
  - `validate <storyboard>`
  - compile/save arguments for project, new timeline slug/name, default hold, and projects root
  - `--vo-align <plan.json>`
  - `--register-shots`
  - `--render`
- Use `AstridClient.open(...)`; do not add a ninth gateway family.
- Implement resolution through sanctioned services:
  - `media_id` → same-project `client.media.show`
  - `content_hash` → normalized hash lookup through `client.media.list`
  - `path` → `client.media.import_file(..., realm="managed_local")`
- Emit renderable registry entries using a managed/project-owned locator, raw `content_sha256`, media type/probe metadata, and authentic generation/variant IDs. Never copy invalid `media_id`, `content_hash`, prompt, or history keys into `AssetEntry`.
- Preflight the full timeline and registry before mutation.
- For a new target: create a blank named timeline, then perform a version-1 CAS save so the required `timeline.saved` event exists. For reruns: show the existing target and CAS-save its returned version. Never overwrite `main`.
- Implement `--register-shots` behind the flag:
  - one deterministic/versioned project shot per section
  - ordered active image/video media items
  - rerun-safe reconciliation without duplicate/orphan growth
  - matching `pinnedShotGroups` linkage in the timeline
- Implement `--render` through the canonical managed `timeline_ref` execution path.
- Document transcript/image/generation/variant/shot/clip enrichment conventions and honest limitations, including generation-ID semantics and mink’s role.
- Add temporary-root integration tests for import/dedupe, create→save→show, CAS failure, validation-before-write, hash-prefix normalization, shot linkage, rerun behavior, and kernel receipts/events.

Checkpoint acceptance criteria:

- The exact validation command works:
  `python3 scripts/build_storyboard.py validate <storyboard>`.
- A temp-root compile yields one kernel timeline with a `timeline.saved` event and receipt; malformed input changes no kernel state.
- All referenced local media is kernel-managed and render containment passes.
- Flag-off creates no shots; flag-on creates linked, ordered, rerun-safe shots.
- Rendering is admitted as a kernel run/task through the existing generic capability handler.
- Focused tests pass and Grok oracle `PASS`.

Classification: **normal** — existing media, timeline, shot, render, UnitOfWork, and receipt APIs cover the work.

## Batch 4 — Author and lock the 25-section Astrid intro storyboard

Tasks:

- Author the approved `build/astrid-intro.storyboard.json` location from:
  - `slides-manifest.json` for consolidated VO/caption/image/prompt/history data
  - `plan.json` for order/start/duration
  - `make_slide_html.py` for title, bullets, and nav-state
  - `pyramid-prompts.txt` for prompt-order parity
- Include exactly 25 ordered unique sections.
- Preserve byte-identical VO and captions.
- Use `final-slides/<slug>.png` as each active image.
- Record `slides-pyramid-full/<slug>.png` as the historical/original Codex variant where applicable, preserve the complete original prompt/model history, and do not invent `generationId`.
- Include the settled pyramid title/bullet equivalents and mink directives without altering the existing visual design.
- Point VO blocks to the 25 existing WAV files.
- Extend `tests/test_storyboard_schema.py` or add a focused intro-parity test that loads the real storyboard and verifies all paths, prompt slugs, starts, durations, VO/caption equality, variants, and active indices.

Checkpoint acceptance criteria:

- Validator accepts both sample and intro storyboards.
- Exactly 25 active images and 25 VO assets exist.
- Section slug/order equals `plan.json`; prompt slug/order equals the 25 prompt records.
- Authored duration remains 177.53s and the chosen block mapping predicts 76 clips/50 active registry assets.
- No source PNG/WAV bytes changed.
- Focused tests pass and Grok oracle `PASS`.

Classification: **normal** — mechanical authoring from verified source maps with parity assertions.

## Batch 5 — Live compile, variant, and kernel-parity proof

Tasks:

- Confirm the intro store is safely writable through its exclusive owner.
- Set `ASTRID_PROJECTS_ROOT=/Users/peteromalley/Documents/reigh-workspace/astrid-intro-projects`.
- Run the required validator.
- Compile with `--vo-align` to a new slug such as `astrid-intro-storyboard`; exercise `--register-shots` only in its intended flag-on proof.
- Capture `timelines show`, `history`, receipts/events, media identities, and shots linkage.
- Assert from show JSON:
  - exactly 76 clips and 50 active registry assets, or an explicitly pre-approved/documented delta
  - 25 VO, 25 caption, 25 b-roll/slide clips, and one brand clip
  - exact section starts and verbatim caption/VO linkage
  - no mutation of `main`
- Demonstrate one variant selection change:
  - hash every source variant beforehand
  - change one section’s `active_index`
  - revalidate and CAS-recompile
  - prove no source bytes changed
  - prove the other 24 registry entries and clips remained identical
  - prove the chosen variant and active provenance are persisted

Checkpoint acceptance criteria:

- New kernel timeline exists with full receipt/event history and exact parity.
- Optional section shots are linked through `pinnedShotGroups`, not merely created at project scope.
- Variant evidence satisfies done criterion 4 without fabricated generation linkage.
- Source timeline `main` and all source media bytes remain unchanged.
- Grok oracle `PASS`.

Classification: **normal** — empirical SDK/CLI exercise with deterministic comparison scripts.

## Batch 6 — Render, evidence matrix, documentation convergence, and sync

Tasks:

- Render the new timeline through `timelines render`/`--render` using the shown pinned version and a fresh output name.
- Capture kernel run/task/attempt IDs, lifecycle events, receipt, managed outputs, hashes, and authority stamp.
- Use `ffprobe` to verify playable H.264/AAC output, 1920×1080/30fps where expected, and duration `177±3s`.
- Extract and open three representative frames near the midpoints of `open`, `idea2_contribute`, and `cta`. Also assert structurally that all 25 slide assets/clips occur; do not depend on unavailable vision-understanding.
- Run focused storyboard tests, relevant timeline/render integration tests, and one authoritative broad suite.
- Produce `.oracle/evidence/` artifacts and a matrix mapping every done criterion to command, path, result, and reviewer disposition.
- Reconcile docs so every stated capability ships and every limitation is explicit.
- Obtain the final Grok oracle review using one to three passes total; route accepted findings through normal rework and fresh review.
- Commit only reviewed paths, explicitly push `HEAD:megado/oracle-run-storyboard` to origin, never merge main, and open the final local video/workspace.

Checkpoint acceptance criteria:

- Render is playable, `177±3s`, and contains all 25 slide clips with three opened spot-check frames.
- Evidence matrix covers all five done criteria with command/path/result evidence.
- Tests and final oracle review pass; no North Star anti-pattern or undocumented limitation remains.
- Reviewed branch is pushed to the authorized ref only.

Classification: **normal** — standard render, inspection, evidence, documentation, and authorized Git operations.

# 2) ADDITIONAL AREAS TO EXPLORE before/during execution

1. `astrid/core/timeline/validators/registry.py`, `banodoco_schema.py`, `astrid/sdk/media.py`, and `managed_media_resolver.py`: prove the exact conversion from storyboard `media_id|content_hash|path` to a render-valid, project-owned registry entry.

2. `astrid/sdk/shots.py`, `astrid/packs/shots/repository.py`, and timeline `pinnedShotGroups`: verify deterministic rerun semantics because shots have no update/delete or unique-name guarantee.

3. Generation manifests in `astrid/packs/generation/executors/_common.py` and current kernel run/task/output identities: determine whether any field legitimately satisfies `AssetEntry.generationId`; otherwise omit it and document the limitation.

4. Intro `slides-manifest.json`, `make_slide_html.py`, `build_timeline.py`, and `plan.json`: settle title/bullets/mink materialization and timing without breaking the 76/50 parity oracle.

5. Intro kernel exclusive-owner/bridge state plus render asset containment: confirm the supported mutation route and that repo-external PNG/WAV files are imported into managed media before render.

6. `pyproject.toml`, `.gitignore`, `.oracle/custody.md`, and the external project mount: verify schema packaging, storyboard artifact custody, and separation of carried-forward dirty changes from storyboard commits.

# 3) OPEN QUESTIONS

1. How should title, bullets, text, and mink directives compile when the active `final-slides` PNG already contains them? The decision must avoid duplicate pixels while ensuring supported block types are not silently ignored.

2. What is the authoritative v10 meaning of `AssetEntry.generationId` when generation manifests expose kernel run/request identities but no canonical generation table ID? If none qualifies, may the intro leave it absent while retaining prompt/history and variant linkage?

3. Is `build/astrid-intro.storyboard.json` intentionally project-local under `/Users/peteromalley/Documents/reigh-workspace/astrid-intro-projects/astrid-intro/build/`, or must a reviewable source copy also live in a tracked repo path because top-level repo `build/` is ignored?

4. Does “prompts persisted beside assets” mean co-location inside storyboard variant records plus compiled `clip.generation`, or is a physical `<asset>.prompt.json` companion required? Any physical companion must be explicitly derived to avoid becoming a second authority.

5. For `--register-shots`, should recompilation reconcile stable per-section shots or create storyboard-versioned shots? Stable reconciliation is cleaner but needs explicit handling for removed/reordered media with the existing six-verb shots surface.

# 4) NORTH STAR check

This plan advances ONE-store execution by treating the storyboard as version-controlled declarative source and the kernel timeline as its only executable compiled state. Media enters through kernel import; timelines and shots mutate only through typed SDK services and UnitOfWork; render runs through the canonical kernel run/task lifecycle. Any compiled files are derived inspection artifacts, never authorities.

It explicitly avoids:

- **A second ledger:** no runtime storyboard database, independent eventlog, or authoritative compiled JSON is introduced. The storyboard is source; SQLite remains execution authority.
- **Kernel/eventlog divergence:** no direct SQLite, eventlog, receipt, registry-projection, or `run.json` writes; validation fails before SDK mutation, and there is no silent filesystem downgrade.
- **Ghost verbs or dishonest docs:** no ninth gateway family is added. The requested script, flags, schema, linkage behavior, and limitations are all exercised empirically before documentation claims them.
- **Per-executor adapters:** compilation uses one generic storyboard transformer and the existing media/timeline/shots services plus generic render capability handler.
- **Scope creep disguised as architecture:** no UI editor, kernel-core schema change, new execution supervisor, serve redesign, GPU management, other-project migration, localization, or style redesign is included.

The staged transcript→images→generations→variants→shots→clips enrichment remains traceable, timing stays independently editable, multiple video blocks remain supported, and future input formats can normalize through the loader boundary without adding a speculative plugin framework.

# 5) EFFORT ESTIMATE vs >2 weeks huge-run threshold

Best estimate: **9–12 engineering days**, including implementation, intro authoring, live render, oracle gates, likely rework, documentation, and evidence capture. This is at or below two working weeks, so it is **not currently a huge run** and does not activate periodic cumulative big-batch reviews.

If execution discovers that authentic generation linkage requires a kernel schema change, or rerun-safe shots require new verbs, that exceeds the frozen non-goals rather than silently expanding the estimate. The run should escalate/stop for scope reconciliation; if authorized scope later pushes the estimate above two weeks, mark it huge before the next batch and predeclare cumulative review boundaries.
tokens used
129,264
# 1) TASKLIST

Execution policy: all implementation tasks are proposed **normal**, assigned to GLM-5.3 Flash with the declared GLM-5.2 fallback only upon demonstrated unavailability. No task meets the exceptional `[XHARD]` threshold: the work decomposes into bounded schema, compiler, SDK-linkage, fixture, and empirical-validation units whose failures are locally observable. Grok-4.6 performs each batch gate and final review, with the declared GPT-5.6 Sol fallback. Each batch ends in a reviewed commit; no dependent batch begins before its checkpoint is `PASS`.

## Batch 0 — Freeze compiler semantics and protect the baseline

Tasks:

- Reconcile `.oracle/custody.md`, current dirty paths, carried-forward fixes, branch/ref, and the external intro-project mount. Preserve unrelated work without folding it accidentally into storyboard commits.
- Verify the intro store’s exclusive-owner state before any later mutation; decide whether execution must stop the owner or use its supported route.
- Record settled answers for block-to-clip behavior, generation identity, prompt persistence, intro storyboard location, and rerun-safe shot registration.
- Lock a parity oracle from:
  - `build/slides-manifest.json`
  - `build/segments/plan.json`
  - `build/make_slide_html.py`
  - `build/build_timeline.py`
  - current kernel timeline `main`
- Define the exact timing rules: section-start calculation, default hold, section/block override precedence, VO-aligned starts, and how multiple video blocks within one section are placed.

Checkpoint acceptance criteria:

- Read-only probes confirm 25 sections, 76 clips, 50 assets, 177.53s authored duration, and current `main` version/content.
- The semantics above are written unambiguously and preserve exact intro parity without ignored renderable blocks or duplicated baked text.
- No intro kernel mutation occurred; protected dirty paths remain intact.
- Grok oracle `PASS`.

Classification: **normal** — contract reconciliation over existing, inspectable APIs and fixtures.

## Batch 1 — Versioned storyboard schema and reusable loader

Tasks:

- Add `astrid/core/storyboard/storyboard.schema.json` with an exact `schema_version` and strict object shapes for:
  - `meta.canvas` and `meta.style`
  - ordered `sections[]` with unique semantic slug
  - required navigation tab-state
  - section/block timing
  - ordered typed blocks: `title`, `bullets`, `text`, `image`, `vo`, `video`, and `mink`
  - `mink` directive `{pose, anchor, scale}`
  - asset and generation forms for image/video
  - complete generation specifications `{prompt, model, refs, seed?}`
  - exactly one resolution route from `media_id`, `content_hash`, or `path`
  - `variants[]`, `active_index`, and prompt/history provenance
  - VO text/caption plus the settled optional audio-resolution form required for intro parity
- Add `astrid/core/storyboard/{__init__.py,loader.py}` with `StoryboardValidationError`, deterministic JSON-schema errors, semantic duplicate-slug checks, active-index bounds, and storyboard-relative path resolution without mutating the authored document.
- Add a small general-purpose fixture such as `examples/storyboards/minimal.storyboard.json`.
- Add `tests/test_storyboard_schema.py` covering:
  - schema self-validation
  - valid minimal/sample storyboard
  - missing nav
  - missing/empty blocks
  - duplicate section slug
  - invalid block discriminator
  - incomplete generation spec
  - missing/ambiguous resolution
  - out-of-range `active_index`
- Verify the packaged wheel includes the schema.

Checkpoint acceptance criteria:

- The sample validates through the public loader.
- Every required malformed case fails with a deterministic path/message and no writes.
- Schema and loader ship in the installed package.
- No timeline/kernel schema changes were introduced.
- Focused pytest passes and Grok oracle `PASS`.

Classification: **normal** — established JSON-schema and semantic-validation patterns already exist in the repo.

## Batch 2 — Pure storyboard-to-timeline compiler and timing model

Tasks:

- Add `astrid/core/storyboard/compiler.py` with a pure `compile_storyboard(...) -> (config, registry, linkage_plan)` boundary.
- Compile deterministic tracks, clip IDs, registry keys, ordering, output canvas/fps, and timing without writing the kernel.
- Implement:
  - default constant section hold
  - section `timing.hold`
  - block `timing.hold`
  - settled override precedence
  - `--vo-align` input normalization for the intro’s `segments[].text/start/duration`
  - exact section-start snapping by slug
  - text/VO consistency checks
  - multiple video blocks per section
  - active-variant selection
- Compile VO into the settled audio/caption representation and preserve verbatim spoken/caption text.
- Map generation provenance into existing valid surfaces:
  - prompt/model/refs/seed in `clip.generation`
  - `generationId`/`variantId` in `AssetEntry` only when authentic
  - `content_hash` normalized to registry `content_sha256`
- Handle title/bullets/text/mink according to Batch 0’s parity-safe rule, ensuring ordinary non-baked storyboards produce edited material while the intro does not double-render content already baked into final-slide images.
- Validate compiled output with `canonical_timeline_config`/timeline validation and `validate_registry` before returning it.
- Add pure tests for deterministic compilation, stable IDs/order, timing precedence, VO alignment, multiple videos, active variants, invalid references, and repeat-byte equality.

Checkpoint acceptance criteria:

- The compiler produces render-valid timeline and registry objects without side effects.
- Timing changes alter timing only, not prompts or asset bytes.
- Switching one `active_index` changes only the selected asset/clip provenance.
- Multiple video blocks survive as distinct edited clips.
- Focused tests pass and Grok oracle `PASS`.

Classification: **normal** — deterministic transformation with canonical validators and golden tests.

## Batch 3 — Kernel linkage, managed media, shots, and executable script

Tasks:

- Add the thin checkout entry point `scripts/build_storyboard.py` with:
  - `validate <storyboard>`
  - compile/save arguments for project, new timeline slug/name, default hold, and projects root
  - `--vo-align <plan.json>`
  - `--register-shots`
  - `--render`
- Use `AstridClient.open(...)`; do not add a ninth gateway family.
- Implement resolution through sanctioned services:
  - `media_id` → same-project `client.media.show`
  - `content_hash` → normalized hash lookup through `client.media.list`
  - `path` → `client.media.import_file(..., realm="managed_local")`
- Emit renderable registry entries using a managed/project-owned locator, raw `content_sha256`, media type/probe metadata, and authentic generation/variant IDs. Never copy invalid `media_id`, `content_hash`, prompt, or history keys into `AssetEntry`.
- Preflight the full timeline and registry before mutation.
- For a new target: create a blank named timeline, then perform a version-1 CAS save so the required `timeline.saved` event exists. For reruns: show the existing target and CAS-save its returned version. Never overwrite `main`.
- Implement `--register-shots` behind the flag:
  - one deterministic/versioned project shot per section
  - ordered active image/video media items
  - rerun-safe reconciliation without duplicate/orphan growth
  - matching `pinnedShotGroups` linkage in the timeline
- Implement `--render` through the canonical managed `timeline_ref` execution path.
- Document transcript/image/generation/variant/shot/clip enrichment conventions and honest limitations, including generation-ID semantics and mink’s role.
- Add temporary-root integration tests for import/dedupe, create→save→show, CAS failure, validation-before-write, hash-prefix normalization, shot linkage, rerun behavior, and kernel receipts/events.

Checkpoint acceptance criteria:

- The exact validation command works:
  `python3 scripts/build_storyboard.py validate <storyboard>`.
- A temp-root compile yields one kernel timeline with a `timeline.saved` event and receipt; malformed input changes no kernel state.
- All referenced local media is kernel-managed and render containment passes.
- Flag-off creates no shots; flag-on creates linked, ordered, rerun-safe shots.
- Rendering is admitted as a kernel run/task through the existing generic capability handler.
- Focused tests pass and Grok oracle `PASS`.

Classification: **normal** — existing media, timeline, shot, render, UnitOfWork, and receipt APIs cover the work.

## Batch 4 — Author and lock the 25-section Astrid intro storyboard

Tasks:

- Author the approved `build/astrid-intro.storyboard.json` location from:
  - `slides-manifest.json` for consolidated VO/caption/image/prompt/history data
  - `plan.json` for order/start/duration
  - `make_slide_html.py` for title, bullets, and nav-state
  - `pyramid-prompts.txt` for prompt-order parity
- Include exactly 25 ordered unique sections.
- Preserve byte-identical VO and captions.
- Use `final-slides/<slug>.png` as each active image.
- Record `slides-pyramid-full/<slug>.png` as the historical/original Codex variant where applicable, preserve the complete original prompt/model history, and do not invent `generationId`.
- Include the settled pyramid title/bullet equivalents and mink directives without altering the existing visual design.
- Point VO blocks to the 25 existing WAV files.
- Extend `tests/test_storyboard_schema.py` or add a focused intro-parity test that loads the real storyboard and verifies all paths, prompt slugs, starts, durations, VO/caption equality, variants, and active indices.

Checkpoint acceptance criteria:

- Validator accepts both sample and intro storyboards.
- Exactly 25 active images and 25 VO assets exist.
- Section slug/order equals `plan.json`; prompt slug/order equals the 25 prompt records.
- Authored duration remains 177.53s and the chosen block mapping predicts 76 clips/50 active registry assets.
- No source PNG/WAV bytes changed.
- Focused tests pass and Grok oracle `PASS`.

Classification: **normal** — mechanical authoring from verified source maps with parity assertions.

## Batch 5 — Live compile, variant, and kernel-parity proof

Tasks:

- Confirm the intro store is safely writable through its exclusive owner.
- Set `ASTRID_PROJECTS_ROOT=/Users/peteromalley/Documents/reigh-workspace/astrid-intro-projects`.
- Run the required validator.
- Compile with `--vo-align` to a new slug such as `astrid-intro-storyboard`; exercise `--register-shots` only in its intended flag-on proof.
- Capture `timelines show`, `history`, receipts/events, media identities, and shots linkage.
- Assert from show JSON:
  - exactly 76 clips and 50 active registry assets, or an explicitly pre-approved/documented delta
  - 25 VO, 25 caption, 25 b-roll/slide clips, and one brand clip
  - exact section starts and verbatim caption/VO linkage
  - no mutation of `main`
- Demonstrate one variant selection change:
  - hash every source variant beforehand
  - change one section’s `active_index`
  - revalidate and CAS-recompile
  - prove no source bytes changed
  - prove the other 24 registry entries and clips remained identical
  - prove the chosen variant and active provenance are persisted

Checkpoint acceptance criteria:

- New kernel timeline exists with full receipt/event history and exact parity.
- Optional section shots are linked through `pinnedShotGroups`, not merely created at project scope.
- Variant evidence satisfies done criterion 4 without fabricated generation linkage.
- Source timeline `main` and all source media bytes remain unchanged.
- Grok oracle `PASS`.

Classification: **normal** — empirical SDK/CLI exercise with deterministic comparison scripts.

## Batch 6 — Render, evidence matrix, documentation convergence, and sync

Tasks:

- Render the new timeline through `timelines render`/`--render` using the shown pinned version and a fresh output name.
- Capture kernel run/task/attempt IDs, lifecycle events, receipt, managed outputs, hashes, and authority stamp.
- Use `ffprobe` to verify playable H.264/AAC output, 1920×1080/30fps where expected, and duration `177±3s`.
- Extract and open three representative frames near the midpoints of `open`, `idea2_contribute`, and `cta`. Also assert structurally that all 25 slide assets/clips occur; do not depend on unavailable vision-understanding.
- Run focused storyboard tests, relevant timeline/render integration tests, and one authoritative broad suite.
- Produce `.oracle/evidence/` artifacts and a matrix mapping every done criterion to command, path, result, and reviewer disposition.
- Reconcile docs so every stated capability ships and every limitation is explicit.
- Obtain the final Grok oracle review using one to three passes total; route accepted findings through normal rework and fresh review.
- Commit only reviewed paths, explicitly push `HEAD:megado/oracle-run-storyboard` to origin, never merge main, and open the final local video/workspace.

Checkpoint acceptance criteria:

- Render is playable, `177±3s`, and contains all 25 slide clips with three opened spot-check frames.
- Evidence matrix covers all five done criteria with command/path/result evidence.
- Tests and final oracle review pass; no North Star anti-pattern or undocumented limitation remains.
- Reviewed branch is pushed to the authorized ref only.

Classification: **normal** — standard render, inspection, evidence, documentation, and authorized Git operations.

# 2) ADDITIONAL AREAS TO EXPLORE before/during execution

1. `astrid/core/timeline/validators/registry.py`, `banodoco_schema.py`, `astrid/sdk/media.py`, and `managed_media_resolver.py`: prove the exact conversion from storyboard `media_id|content_hash|path` to a render-valid, project-owned registry entry.

2. `astrid/sdk/shots.py`, `astrid/packs/shots/repository.py`, and timeline `pinnedShotGroups`: verify deterministic rerun semantics because shots have no update/delete or unique-name guarantee.

3. Generation manifests in `astrid/packs/generation/executors/_common.py` and current kernel run/task/output identities: determine whether any field legitimately satisfies `AssetEntry.generationId`; otherwise omit it and document the limitation.

4. Intro `slides-manifest.json`, `make_slide_html.py`, `build_timeline.py`, and `plan.json`: settle title/bullets/mink materialization and timing without breaking the 76/50 parity oracle.

5. Intro kernel exclusive-owner/bridge state plus render asset containment: confirm the supported mutation route and that repo-external PNG/WAV files are imported into managed media before render.

6. `pyproject.toml`, `.gitignore`, `.oracle/custody.md`, and the external project mount: verify schema packaging, storyboard artifact custody, and separation of carried-forward dirty changes from storyboard commits.

# 3) OPEN QUESTIONS

1. How should title, bullets, text, and mink directives compile when the active `final-slides` PNG already contains them? The decision must avoid duplicate pixels while ensuring supported block types are not silently ignored.

2. What is the authoritative v10 meaning of `AssetEntry.generationId` when generation manifests expose kernel run/request identities but no canonical generation table ID? If none qualifies, may the intro leave it absent while retaining prompt/history and variant linkage?

3. Is `build/astrid-intro.storyboard.json` intentionally project-local under `/Users/peteromalley/Documents/reigh-workspace/astrid-intro-projects/astrid-intro/build/`, or must a reviewable source copy also live in a tracked repo path because top-level repo `build/` is ignored?

4. Does “prompts persisted beside assets” mean co-location inside storyboard variant records plus compiled `clip.generation`, or is a physical `<asset>.prompt.json` companion required? Any physical companion must be explicitly derived to avoid becoming a second authority.

5. For `--register-shots`, should recompilation reconcile stable per-section shots or create storyboard-versioned shots? Stable reconciliation is cleaner but needs explicit handling for removed/reordered media with the existing six-verb shots surface.

# 4) NORTH STAR check

This plan advances ONE-store execution by treating the storyboard as version-controlled declarative source and the kernel timeline as its only executable compiled state. Media enters through kernel import; timelines and shots mutate only through typed SDK services and UnitOfWork; render runs through the canonical kernel run/task lifecycle. Any compiled files are derived inspection artifacts, never authorities.

It explicitly avoids:

- **A second ledger:** no runtime storyboard database, independent eventlog, or authoritative compiled JSON is introduced. The storyboard is source; SQLite remains execution authority.
- **Kernel/eventlog divergence:** no direct SQLite, eventlog, receipt, registry-projection, or `run.json` writes; validation fails before SDK mutation, and there is no silent filesystem downgrade.
- **Ghost verbs or dishonest docs:** no ninth gateway family is added. The requested script, flags, schema, linkage behavior, and limitations are all exercised empirically before documentation claims them.
- **Per-executor adapters:** compilation uses one generic storyboard transformer and the existing media/timeline/shots services plus generic render capability handler.
- **Scope creep disguised as architecture:** no UI editor, kernel-core schema change, new execution supervisor, serve redesign, GPU management, other-project migration, localization, or style redesign is included.

The staged transcript→images→generations→variants→shots→clips enrichment remains traceable, timing stays independently editable, multiple video blocks remain supported, and future input formats can normalize through the loader boundary without adding a speculative plugin framework.

# 5) EFFORT ESTIMATE vs >2 weeks huge-run threshold

Best estimate: **9–12 engineering days**, including implementation, intro authoring, live render, oracle gates, likely rework, documentation, and evidence capture. This is at or below two working weeks, so it is **not currently a huge run** and does not activate periodic cumulative big-batch reviews.

If execution discovers that authentic generation linkage requires a kernel schema change, or rerun-safe shots require new verbs, that exceeds the frozen non-goals rather than silently expanding the estimate. The run should escalate/stop for scope reconciliation; if authorized scope later pushes the estimate above two weeks, mark it huge before the next batch and predeclare cumulative review boundaries.

===== EXPLORATION FINDINGS (complete, all six) =====
===== area1-registry-resolution.txt =====
# AREA 1 — Registry resolution: verified facts

**1. `validators/registry.py`** — `validate_registry` (registry.py:33-80): registry must be `{"assets": {key: entry}}`; entry keys restricted to `_ASSET_ENTRY_ALLOWED` (imported from `banodoco_schema.py:364-381`); entry needs `file` **or** `url` (:44-45); `url` must be http(s) (:47); optional `origin`, `content_sha256` (64-hex, :54-58), `derivedFrom`, `url_expires_at`, `etag` checks. **`generationId`/`variantId` pass through unvalidated** (allowed, not checked).

**2. `banodoco_schema.py`** (lives at `astrid/core/timeline/banodoco_schema.py`, *not* under `validators/`): `SharedAssetEntry` TypedDict fields :119-133 (`file,url,etag,content_sha256,url_expires_at,type,duration,resolution,fps,origin,derivedFrom,generationId,variantId,thumbnailUrl`); timeline container validated via shared JSON-Schema package (`banodoco_timeline_schema`, :23-56, no silent fallback).

**3. `sdk/media.py`** — `MediaService.import_file` (:115-170): hashes/probes outside txn, derives deterministic media_id from `(core.media.import, project scope, key)` (:147-152), commits media row + location + receipt in one UoW (:154-163). `import_directory` = per-file child keys `parent#index` (:174-239). Project-scoped `show` (:254-262).

**4. Managed resolver** — `astrid/core/io/managed_media_resolver.py`: strict CAS locator shape `<root>/.astrid/media/sha256/aa/bb/<digest>` (:27-44); `resolve_owned_managed_media` (:59-127) fails closed unless kernel row (`media_locations.realm='managed_local'` joined to project, :97-104) exists, locator==canonical, bytes re-hash to digest (:118-126). `rebase_timeline_registry_managed_assets` (:130-176) refreshes stale `file` locators only, deriving digest from `content_sha256|sha256|hash` or the locator itself.

**5. media→render-valid entry**: `MediaService.import_file` → kernel media row + `managed_local` location; registry entry `{file: <absolute CAS path>, content_sha256: digest}` satisfies `validate_registry`; render path (`render/managed_timeline.py:209-232,297-320`) validates, checks clip-referenced asset ids exist, rebases locators via ownership check, writes `timeline.json/assets.json/authority.json` (:337-343). Alternative: `sources/`-relative `file` (`resolution.py:285-316`, contained-path fast path).

**Unknowns**: none material.

**Risks** (ranked): (1) absolute `file` locators are root-dependent — always pair with `content_sha256` so rebase works; (2) `sources/` files bypass digest verification (`resolve_asset_authorized_path` :302-307); (3) missing-asset check is clip-reference only — unreferenced entries silently kept.

**Approach (ONE-store/KISS)**: compiler emits `{file: managed_media_path(root, digest), content_sha256: digest, generationId?}`; import via `sdk media import-file` once per gen asset; rely on existing rebase at render. No new resolver code.
0

===== area2-shots-mount.txt =====
## area2-shots-mount — verified facts

**1. `astrid/sdk/shots.py` (`ShotsService`)**
- Six verbs only: `create`/`add_item`/`remove_item`/`reorder`/`list`/`show`; no SQL, no own writer — delegates to `ShotRepository` inside one `UnitOfWork` per mutation (shots.py:23–28, 121–130).
- Deterministic ids: shot id from `(shot.create, project scope, key)` (shots.py:114–119); item id from `(shot.add_item, scope, key)` (shots.py:171–176). Identical retry = receipt replay, zero rows.
- `show` enriches items with media path/name best-effort (shots.py:325–353).

**2. `astrid/packs/shots/repository.py`**
- `create`: receipt gate first, then project check, then duplicate-**id** rejection — uniqueness is by shot id, **not name**; duplicate names are legal (repository.py:606–677). One `BEGIN IMMEDIATE` txn: event stream + `shots` row + hash-chained `shot.created` + receipt (694–769).
- Method census: `create`/`add_item`/`remove_item`/`reorder`/`show`/`list` — **no shot update, no shot delete**. `remove_item` deletes only `shot_items`; media preserved via `ON DELETE RESTRICT` (36–40). `reorder` requires an exact permutation (47–56). Cross-pack currency is `media_id` only (8–10).

**3. `pinnedShotGroups`**
- Timeline-config top-level array `{shotId?, clipIds[], start?, end?}`; canonical/persisted by projection and Reigh bridge (banodoco_schema.py:350; projection.py:144–148; local_bridge.py:364–373; composer passthrough banodoco_composer.py:209–211).
- Parse semantics: missing shotId → synthesized `shot-{n}`; duplicate shotId raises; dangling clipIds → warnings, silently filtered; authored bounds else member-derived (timeline_visualize/model.py:425–488). Storyboard executor errors on unknown pinned shot (timeline_storyboard/run.py:348–350). Frozen form is `{shotId, clipIds}` pairs (frozen.py:1211–1214).
- Kernel shots and `pinnedShotGroups` are **unlinked namespaces**: CLI states a shot "is not implicitly attached to a timeline" (shots/cli.py:291–295); no kernel check that a pinnedShotGroups shotId exists in `shots`.

**4. Rerun/update/delete**
- Rerun = idempotent replay; changed request under same key → `ReceiptMismatchError` pre-mutation (repository.py:610–613). No mutation or deletion of shot facts exists.

**Unknowns:** DDL not read directly (RESTRICT claim from docstring); "flag" lives in the future compiler, not the CLI (mount is unconditional).

**Ranked approach (ONE-store/KISS):**
1. Compiler flag registers sections via `timelines shots create`+`add` with stable idempotency keys (e.g. `storyboard:<slug>:<section-id>`) → deterministic shot ids, idempotent recompiles.
2. Emit `pinnedShotGroups` entries `{shotId: kernel id, clipIds}` as derived timeline-config projection — kernel stays sole authority.
3. Do not invent update/delete; recompiles reuse deterministic ids (avoids orphan accumulation, the only cleanup gap).
0

===== area3-generation-id.txt =====
## Area 3 — generation-id: verified facts

**1. `_common.py`** (`astrid/packs/generation/executors/_common.py`)
- `build_generation_manifest` (:29–85) wraps `core/_shared/result_manifest.py:build_manifest` (:174) at `schema_version=2`.
- Manifest fields: `modality, model, mode_used, model_actual, execution, request, seed` (:55–63) + optional `dropped_features, applied_features, cost_usd, duration_ms, request_id, source_urls` (:64–75). Helpers: `_load_prompts` (:174), `_normalise_prompts` (:203), `_resolve_seed` (:162), `_manifest_path_for_run_dir` (:339) → `run_dir/manifest.json`.

**2. Manifest identities**
- Required core: `schema_version, kind, inputs, outputs, created, warnings` (`result_manifest.py:29–31`); outputs auto-enriched `path, content_hash (sha256:…), bytes, type` (:89–135).
- `request_id` = backend request id, optional. **No `generation_id`/`run_id` key exists in any manifest.** Only stable output identity = `content_hash`.
- PNG tEXt chunks: `astrid_prompt, astrid_model, astrid_model_actual, astrid_seed, astrid_request_id, astrid_created, astrid_loras` (`generation/skill/SKILL.md:173–179`).

**3. `AssetEntry.generationId` — nothing satisfies it.**
- Declared `banodoco_schema.py:131`, allowed `:377`. Sole code reference: `_PRESERVED_REGISTRY_FIELDS` (`cut/registry.py:18–27`) → `_carry_forward_registry_metadata` (:68–79) copies prior value matched by url/file. No Astrid writer ever sets it fresh.

**4. History fields (prompts/variants)**
- `manifest.json`: full canonical `request` (prompt, refs, seed) per run dir.
- `.astrid.variants.json` (`variants.py:18`): artifacts `{role: variant|other, group, group_index, duration, variant_meta, path}` (:292–300); refs `{run_id (ULID), artifact_index, kind, sha256, label}` (:309–319); append-only selections (`keep_selection` :119). Writers: `generate_image_openai/run.py:425`, `iteration_video/run.py:341`, `logo_ideas/run.py:511` — **core image/video executors don't write it**.
- OpenAI executor adds audit lineage prompt→asset (`generate_image_openai/run.py:360–389`).

**Unknowns:** intro project registry may hold externally-authored `generationId` values (outside repo, read-only).
**Risk:** using `content_hash` as generationId collides on identical bytes; kernel run id lives in run.json, not manifest.

**Approach (ONE-store/KISS):** compiler sets `AssetEntry.generationId` = kernel run id (survives cut carry-forward, registry.py:25); storyboard `variants[]/active_index` maps to variant-group artifacts + latest selection; prompts sourced from manifest `request` + tEXt. No new store.
0

===== area4-intro-sources.txt =====
## area4-intro-sources — verified facts

**1. slides-manifest.json** (`build/slides-manifest.json`): header `video: astrid-intro-final.mp4`, `timeline: "main v13"` (:2-3); 25 slide entries (:5-379), uniform shape: `slug, start, duration, vo_text, caption, image(build/final-slides/<slug>.png), alt_render(build/slides-pyramid-full/<slug>.png), image_prompt, generator{tool,backend,style}` (:6-17). `vo_text==caption` in all entries shown; spot-checked `vo_text` identical to plan.json text for open/two_ideas/recap1/recap2. `image_prompt` = `pyramid-prompts.txt` line for that slug (prefix + per-slug "Visual:" mink prose). No structured pose/anchor/scale anywhere — mink pose is prose only (foundation-prompts.txt:1-20).

**2. build_timeline.py**: 4 tracks (brand/captions/broll visual + a1 audio, reversed z-order, :31-36); per segment: VO media clip w/ explicit from/to (:45-49), caption text clip VERBATIM from `s["text"]` (:54-68), broll media clip (:70-73); +1 brand wordmark clip (:75-80). Holds = `dur+GAP(0.35)`; FADE 0.2 (:25-26). Emits exactly **25×3+1=76 clips, 25×2=50 assets**, total 177.53s → `build/timeline/{timeline,assets}.json` sidecar (:94-95). Theme banodoco-default, 1920×1080@30 (:81-92).

**3. make_slide_html.py**: title/bullets source = `CONTENT` dict (:17-44); nav tab groups OVERVIEW/PILLAR1/PILLAR2 (:13-15) — matches tab states baked into prompts ("equally bright"/"1 highlighted"/"2 highlighted"). `idea2_example` (:30) is dead — no such segment.

**4. plan.json** (`build/segments/plan.json`): 25 segments `{index,slug,text,start,duration}`, `total:177.53` (:179). Starts are cumulative `dur+0.35` (0→5.664→7.625…); last cta 168.081+9.099=177.18. Em-dashes are `\u2014` — preserve verbatim.

**5. Parity-safe rule (recommendation)**: PNGs bake title/bullets/mink → storyboard carries title/bullets/mink as *declarative metadata* on the image block (regen spec only); compiler emits exactly 3 clips/section + brand = 76/50. `alt_render` = ready-made `variants[]` entry; `active_index`→final-slides satisfies criterion 4 byte-neutrally.

**Unknowns**: whether all 25 `vo_text` strings byte-match plan.json (spot-check only — assert in compiler). **Risk**: sidecar `build/timeline/` is a second ledger; D3 must emit managed timeline only.
0

===== area5-store-and-render.txt =====
**Area 5 — store & render: verified facts**

**1. Exclusive-owner/bridge state.** One `DatabaseOwnerLock` per DB: `fcntl.flock(LOCK_EX|LOCK_NB)` on `<root>/.astrid/astrid.sqlite3.lock`, process-lifetime (`astrid/core/store/ownership.py:19-25,66-69`). Standard composition acquires it *before* opening the writer and releases only after writer close (`astrid/core/application.py:38-46,146-150,317-328`). `astrid serve` is the owner until shutdown (`astrid/core/gateway/dispatch.py:190,244-245,289-292`); advertised at `GET /routes` (`local_bridge_server.py:67-75`). Documented as temporary SD3-m4 deviation; m6 loopback-RPC removal is future work (`ownership.py:11-15`).

**2. Mutation route while serve runs.** Exactly one: `POST /projects/:p/timelines/:t/save` (CAS, `expected_version`) — `local_bridge_server.py:924-975`; every other POST → 404 (:977). No HTTP route for media import, tasks, or runs. CLI/SDK writes compose the app → blocked with typed `unavailable` (`application.py:324-328`); timeline writes fail **closed**, refusing eventlog-only downgrade when the DB exists (`astrid/core/timeline/kernel_binding.py:146-171`). Read-only URIs bypass the lock (`core/migrations/runner.py:281`; used by resolver `io/managed_media_resolver.py:93`, database.py:88-90).

**3. Render asset containment.** Registry `file` refs anchor at `project_root/sources` only; absolute refs accepted only beneath that anchor; `..`/symlink escapes rejected (`core/timeline/resolution.py:179-226,250-282`). Kernel timelines may additionally use an exact managed CAS locator — only if the project's kernel media row owns the digest and bytes verify (`resolution.py:285-316`); snapshot resolution goes through this (`core/timeline/snapshot.py:462-466`). Render outputs are themselves published to managed CAS (`packs/rendering/executors/render/run.py:167-171`). **Repo-external PNG/WAV cannot be referenced in place.**

**4. Import-to-managed-media.** `prepare → stage (fsync) → re-hash verify → atomic publish` into `${root}/.astrid/media/sha256/…` (`core/io/media_import.py:835-1044`); `MediaRepository.import_prepared` commits media row + `media_locations` + `core.media` event in one UoW, publishing verified bytes before projections (`core/repositories/media.py:738,1842-1846`). SDK: `media.import_file`/`import_directory` (`sdk/media.py:115,174`). `external_local` reference-in-place exists but is explicit opt-in (`media_import.py:608-611,1047-1060`).

**Unknowns:** none blocking; serve-side task/run admission routes not found (appear not to exist).

**Risks (ranked):**
1. Serve holding the lock blocks the whole D3/D4 pipeline (save, media import, render admission) — no loopback RPC yet.
2. External assets referenced by path silently fail render resolution (unsupported), not imported.
3. `external_local` opt-in would create a second unmanaged authority — anti-North-Star.

**Suggested approach (ranked, KISS/ONE-store):**
1. Run compile/save/render with serve stopped; CLI composes the single writer.
2. Compiler imports every PNG/WAV via `sdk.media.import_file` (managed CAS), registry entries carry digest locators — no `sources/` copying, no `external_local`.
3. If serve must stay up, use only the timeline-save POST route; treat lock contention as a stop-and-retry, not a bypass.
0

===== area6-packaging-custody.txt =====
# area6-packaging-custody — verified facts

**1. Packaging (pyproject.toml) — no changes needed if placed under `astrid/`**
- `pyproject.toml:72-73` `packages.find include=["astrid*"]`: any module under `astrid/` auto-ships. Precedent validators: `astrid/core/contracts/{schema.py,schema_validators.py,capability_schema.py}`; precedent schema JSON: `core/rendering/schemas/v1/*.json` (`pyproject.toml:107`).
- `pyproject.toml:103` `"core/**/*.json"` and `:125` `"packs/**/*.json"` already cover a `storyboard.schema.json` placed in core or a pack.
- `pyproject.toml:17` `jsonschema>=4.0` already a dep — validator needs nothing new.
- `pyproject.toml:70` `include-package-data=false`: schema outside `astrid/` (root, `scripts/`, `build/`) will NOT ship. `scripts/build_storyboard.py` (D3) is fine unpackaged — `scripts/migrations` precedent (`pyproject.toml:218-221`).
→ Put D1 at `astrid/core/storyboard/` (schema+loader); zero pyproject edits. KISS.

**2. .gitignore vs project-local storyboard.json**
- Proven via `git check-ignore -v`: `build/astrid-intro.storyboard.json` hits `.gitignore:137` (`build/`) → **ignored**. D4's `build/…` path, if in-repo, is unversioned — contradicts "versioned storyboard source".
- Intro projects root (`…/astrid-intro-projects`) is outside the worktree → gitignore inapplicable; project-local storyboard there is naturally out-of-repo. Repo `/projects/` ignored at `.gitignore:43`.
- Plain `storyboard.json`/`examples/storyboard.json`: not ignored (no match).
→ Author in projects root; if an in-repo sample is wanted, use `examples/`, never `build/`.

**3. Separating carried-forward dirty fixes**
- Uncommitted mods are pre-storyboard fixes: media.py +18 (managed_local canonical-locator check), secrets.py (str|Path), remotion/run.py +21 (single registry per render), invocation.py +11 (raw-file idempotency warning), STAGE.md +6, plus their two test files (+32/+22).
- `.oracle/` is tracked; plan/agent_goal modified, `briefs|findings/storyboard/`, `receipts/` untracked; phase0 commit 89b813a4 set the precedent of committing oracle state.

**Ranked approach**: (1) commit the six fix files as one standalone carry-forward commit before batch 1, keeping each fix with its tests; (2) commit oracle state with megado batches per phase0 precedent; (3) place D1 under `astrid/core/storyboard/`, storyboard source in projects root.

Unknowns: none blocking. Risk: committing fixes into `build/`-ignored path silently loses the versioned source.
0
codex
Material changes are required. Unchanged task text remains as written; replace only the affected items below.

# 1) TASKLIST REVISIONS

## Batch 0 — Freeze compiler semantics and protect the baseline

Replace the unresolved-semantics task with these settled decisions:

- Record the parity-safe materialization rule:
  - `meta.style.text_materialization` is `"live"` by default and may be `"baked"`.
  - `"baked"` means title, bullets, and mink remain declarative storyboard data but do not create additional clips.
  - The intro uses `"baked"` because `final-slides` PNGs already contain those pixels.
  - Ordinary storyboards use `"live"` and compile title, bullets, text, and mink into live timeline clips.
  - Do not infer this from filenames or asset type.
- Record that `AssetEntry.generationId` is omitted in v1. No manifest field authentically satisfies it, and neither `content_hash` nor backend `request_id` may be repurposed.
- Record prompts, generation specs, history, and variants inside storyboard image/video records. PNG tEXt is incidental provenance only.
- Record that the canonical intro storyboard is project-local, with a hash-identical evidence snapshot under `.oracle/evidence/`.
- Defer shot registration from v1. Do not ship a no-op or misleading `--register-shots` flag.
- Lock the exact intro compiler oracle: 25 sections × three clips—image plate, caption, VO audio—plus one brand clip = exactly 76 clips and 50 active registry assets.
- Exclude `idea2_example`; it has no timeline segment.

Replace the semantics checkpoint with:

- Read-only probes confirm exactly 25 live sections, excluding `idea2_example`; 76 clips; 50 assets; and 177.53s authored duration.
- Intro compilation is fixed at exactly three clips per section plus the brand clip, with no duplicated baked title, bullets, or mink.
- Live-text compilation remains covered for an ordinary non-baked fixture.
- Generation identity, variant storage, managed-media requirements, artifact custody, and deferred shots are no longer open questions.

## Batch 1 — Versioned storyboard schema and reusable loader

Amend the schema task:

- Place the schema and loader exclusively under `astrid/core/storyboard/`; existing package discovery, JSON package-data rules, and `jsonschema` dependency require no `pyproject.toml` changes.
- Add a minimal `meta.style.text_materialization: "live"|"baked"` discriminator, defaulting to `"live"`.
- Require prompts, full generation specifications, history, `variants[]`, and `active_index` to live inside the relevant storyboard block.
- Do not add `generationId` to the storyboard contract merely to populate `AssetEntry`.

Add tests for:

- default live materialization;
- explicit baked materialization;
- active variant bounds and resolution;
- rejection of malformed inline prompt/variant records.

Acceptance criteria addition:

- The installed package contains `astrid/core/storyboard/storyboard.schema.json`.
- The schema introduces no second provenance store or physical prompt sidecars.

## Batch 2 — Pure compiler and timing model

Replace `astrid/core/storyboard/compiler.py` with:

- Keep the compiler as pure functions inside the unpackaged `scripts/build_storyboard.py`; do not create a packaged compiler module.
- Give the pure compilation boundary explicit, already-resolved media bindings. Each binding contains the owned managed locator and raw SHA-256 digest.
- Emit the minimal registry form:
  `{"file": "<absolute managed CAS path>", "content_sha256": "<64-hex digest>"}`.
- Rely on existing registry validation and managed-locator rebasing; add no resolver layer.
- Do not emit `AssetEntry.generationId`. Do not invent `variantId` merely to mirror storyboard array positions.
- Preserve generation specifications in storyboard records and, where supported, `clip.generation`; treat PNG tEXt only as supplementary diagnostic provenance.
- Select only the active variant for the compiled registry. Inactive variants remain in the storyboard and must not inflate the 50-asset parity count.
- Compile:
  - baked intro sections into exactly image plate + caption + VO audio;
  - live storyboards into live title/bullets/text/mink clips as applicable;
  - the brand element into one additional clip.
- Preserve default holds, per-section `timing.hold`, per-block `timing.hold`, and optional `plan.json` VO snapping as independent timing inputs.

Replace the compiler acceptance criteria with:

- Intro fixture compilation produces exactly 76 clips and 50 active registry entries.
- A non-baked fixture proves live text/mink materialization.
- Every registry asset has exactly the required managed locator and digest fields unless an existing validator requires an additional field.
- Switching one `active_index` changes only the selected binding/provenance for that section.
- Timing-only changes do not change prompts, variants, or media bytes.

## Batch 3 — Managed media, kernel linkage, and executable script

Remove all shot-registration implementation and tests.

Revise tasks to:

- Add the unpackaged `scripts/build_storyboard.py`, containing validation, pure compilation, save, VO alignment, and render orchestration.
- Do not expose `--register-shots` in v1. Document shot linkage as deferred because the mounted API lacks shot update/delete semantics. A ghost or no-op flag is explicitly rejected.
- Perform complete read-only storyboard/path/hash preflight before kernel mutation.
- Normalize every selected asset route to a project-owned managed binding:
  - `path`: call `MediaService.import_file(..., realm="managed_local")`;
  - `media_id`: resolve the same-project managed media record;
  - `content_hash`: locate the same-project managed media record by normalized digest.
- Import all repo-external intro PNG and WAV files before timeline save or render. Never reference them in place and never use `external_local`.
- Confirm each import yields the canonical CAS locator and digest, then emit only `{file, content_sha256}`.
- Validate the compiled config and registry before timeline mutation.
- Save only through the existing kernel timeline service with CAS; never write authoritative `timeline.json`, `assets.json`, event logs, receipts, or `run.json` directly.
- Render through the existing managed `timeline_ref` run/task path.

Revise integration tests:

- managed import and deduplication;
- canonical locator plus digest shape;
- stale-root locator rebasing during render;
- malformed storyboard causes no media or timeline mutation;
- successful media imports followed by a failed timeline CAS remain safe, deduplicated kernel facts on retry;
- create/save/show, CAS failure, receipts/events, and canonical render admission.

Acceptance criteria:

- All 50 selected intro assets are kernel-managed before render.
- Repo-external in-place references fail preflight.
- Render containment and managed-locator ownership checks pass.
- No shot rows or `pinnedShotGroups` are created in v1.

## Batch 4 — Author and lock the 25-section intro storyboard

Replace the location and source tasks with:

- Author the canonical storyboard project-locally outside the Astrid worktree, under the `astrid-intro` project’s build area.
- Copy a hash-identical, reviewable snapshot to `.oracle/evidence/astrid-intro.storyboard.json`. Mark it as evidence, never as compiler input or a second authority.
- Include exactly the 25 `plan.json` sections; explicitly exclude `idea2_example`.
- Set `meta.style.text_materialization` to `"baked"`.
- Preserve title, bullets, and mink directives as declarative records, while compiling none of them as additional intro clips.
- Store each `final-slides/<slug>.png` and `slides-pyramid-full/<slug>.png` as entries in the same image block’s `variants[]`; set `active_index` to the `final-slides` entry.
- Persist full prompts, model/backend information, refs, seeds when known, and history inside those variant/storyboard records.
- Document PNG tEXt prompt/model/seed data as incidental provenance, not authoritative input.
- Omit all `generationId` values.
- Point VO blocks to the existing WAV sources, which Batch 3 imports into managed media.

Acceptance criteria additions:

- Canonical and evidence-copy SHA-256 hashes match.
- The dead `idea2_example` slug is absent.
- Every section has an active final-slide variant and an alternate pyramid variant where available.
- The storyboard predicts exactly 76 clips and 50 active registry assets.

## Batch 5 — Live compile and parity proof

Remove:

- all `--register-shots` execution;
- shots capture;
- `pinnedShotGroups` acceptance criteria.

Revise the parity assertions to require exactly, without a pre-approved delta:

- 25 image-plate clips;
- 25 caption clips;
- 25 VO-audio clips;
- one brand clip;
- 50 active registry assets;
- no live title, bullet, or mink clips in the baked intro.

For the variant proof:

- Change one section’s `active_index` from its final-slide entry to its `slides-pyramid-full` entry.
- Prove the inactive variants never entered the original registry.
- Prove only that section’s selected image binding and corresponding clip provenance changed.
- Prove all other clips, registry entries, prompts, variant records, and source bytes remained identical.
- Do not claim or fabricate generation linkage.

## Batch 6 — Render, evidence, documentation, and sync

Add:

- Include the canonical storyboard hash and evidence-copy hash in the evidence matrix.
- Document that:
  - storyboard variants/prompts are authoritative source provenance;
  - PNG tEXt is incidental;
  - `generationId` is intentionally absent;
  - shot registration is deferred from v1;
  - repo-external media must be imported into managed CAS before render.
- Verify the final rendered timeline contains the exact 76/50 structure, not an allowed delta.

# 2) NEW AREAS / POTENTIAL ISSUES

1. Verify that read-only preflight can compute the prospective CAS locator and digest before import, so malformed or structurally invalid storyboards cannot leave partial media facts.

2. Test the partial-success boundary where managed imports succeed but timeline CAS save fails. This is acceptable only if retry deduplicates those kernel media facts and creates no parallel authority.

3. Define custody mechanically: the evidence copy should contain the canonical source path and SHA-256, and the compiler must reject or simply never consume `.oracle/evidence/` as input.

4. Confirm inactive variants are not emitted into the timeline registry. Otherwise the intro would exceed the exact 50-asset oracle even though only 50 assets are referenced.

5. Verify all 25 `slides-manifest.json` VO strings byte-match `plan.json`, not merely the spot-checked examples.

6. Test baked/live materialization explicitly to prevent a future compiler change from either duplicating baked pixels or silently dropping live storyboard text.

# 3) RESOLVED OPEN QUESTIONS

- Baked content uses one explicit storyboard-level materialization mode; no filename heuristic.
- `AssetEntry.generationId` is omitted.
- The canonical storyboard is project-local; `.oracle/evidence/` contains a hash-identical review snapshot.
- Prompts and variants live inside storyboard records; no `<asset>.prompt.json` sidecars.
- Shot registration is deferred from v1; no append-only approximation and no ghost flag.

# 4) NORTH STAR REJECTION

The following are explicitly rejected:

- treating `build/timeline/{timeline,assets}.json` as an authority;
- referencing repo-external intro media in place;
- using `external_local` to bypass managed ownership;
- synthesizing `generationId` from content hashes, request IDs, or run-directory metadata;
- adding physical prompt sidecars or another provenance ledger;
- shipping a no-op `--register-shots` flag;
- inventing shot update/delete behavior around an append-only mount;
- adding a packaged compiler layer when one checkout script is sufficient;
- allowing inactive variants to bloat the executable registry;
- accepting clip/asset-count deltas where the parity rule is now exact.

These cuts preserve the simplest design: one packaged schema/loader, one unpackaged compiler entry point, one managed-media path, and one kernel timeline execution authority.
tokens used
28,395
Material changes are required. Unchanged task text remains as written; replace only the affected items below.

# 1) TASKLIST REVISIONS

## Batch 0 — Freeze compiler semantics and protect the baseline

Replace the unresolved-semantics task with these settled decisions:

- Record the parity-safe materialization rule:
  - `meta.style.text_materialization` is `"live"` by default and may be `"baked"`.
  - `"baked"` means title, bullets, and mink remain declarative storyboard data but do not create additional clips.
  - The intro uses `"baked"` because `final-slides` PNGs already contain those pixels.
  - Ordinary storyboards use `"live"` and compile title, bullets, text, and mink into live timeline clips.
  - Do not infer this from filenames or asset type.
- Record that `AssetEntry.generationId` is omitted in v1. No manifest field authentically satisfies it, and neither `content_hash` nor backend `request_id` may be repurposed.
- Record prompts, generation specs, history, and variants inside storyboard image/video records. PNG tEXt is incidental provenance only.
- Record that the canonical intro storyboard is project-local, with a hash-identical evidence snapshot under `.oracle/evidence/`.
- Defer shot registration from v1. Do not ship a no-op or misleading `--register-shots` flag.
- Lock the exact intro compiler oracle: 25 sections × three clips—image plate, caption, VO audio—plus one brand clip = exactly 76 clips and 50 active registry assets.
- Exclude `idea2_example`; it has no timeline segment.

Replace the semantics checkpoint with:

- Read-only probes confirm exactly 25 live sections, excluding `idea2_example`; 76 clips; 50 assets; and 177.53s authored duration.
- Intro compilation is fixed at exactly three clips per section plus the brand clip, with no duplicated baked title, bullets, or mink.
- Live-text compilation remains covered for an ordinary non-baked fixture.
- Generation identity, variant storage, managed-media requirements, artifact custody, and deferred shots are no longer open questions.

## Batch 1 — Versioned storyboard schema and reusable loader

Amend the schema task:

- Place the schema and loader exclusively under `astrid/core/storyboard/`; existing package discovery, JSON package-data rules, and `jsonschema` dependency require no `pyproject.toml` changes.
- Add a minimal `meta.style.text_materialization: "live"|"baked"` discriminator, defaulting to `"live"`.
- Require prompts, full generation specifications, history, `variants[]`, and `active_index` to live inside the relevant storyboard block.
- Do not add `generationId` to the storyboard contract merely to populate `AssetEntry`.

Add tests for:

- default live materialization;
- explicit baked materialization;
- active variant bounds and resolution;
- rejection of malformed inline prompt/variant records.

Acceptance criteria addition:

- The installed package contains `astrid/core/storyboard/storyboard.schema.json`.
- The schema introduces no second provenance store or physical prompt sidecars.

## Batch 2 — Pure compiler and timing model

Replace `astrid/core/storyboard/compiler.py` with:

- Keep the compiler as pure functions inside the unpackaged `scripts/build_storyboard.py`; do not create a packaged compiler module.
- Give the pure compilation boundary explicit, already-resolved media bindings. Each binding contains the owned managed locator and raw SHA-256 digest.
- Emit the minimal registry form:
  `{"file": "<absolute managed CAS path>", "content_sha256": "<64-hex digest>"}`.
- Rely on existing registry validation and managed-locator rebasing; add no resolver layer.
- Do not emit `AssetEntry.generationId`. Do not invent `variantId` merely to mirror storyboard array positions.
- Preserve generation specifications in storyboard records and, where supported, `clip.generation`; treat PNG tEXt only as supplementary diagnostic provenance.
- Select only the active variant for the compiled registry. Inactive variants remain in the storyboard and must not inflate the 50-asset parity count.
- Compile:
  - baked intro sections into exactly image plate + caption + VO audio;
  - live storyboards into live title/bullets/text/mink clips as applicable;
  - the brand element into one additional clip.
- Preserve default holds, per-section `timing.hold`, per-block `timing.hold`, and optional `plan.json` VO snapping as independent timing inputs.

Replace the compiler acceptance criteria with:

- Intro fixture compilation produces exactly 76 clips and 50 active registry entries.
- A non-baked fixture proves live text/mink materialization.
- Every registry asset has exactly the required managed locator and digest fields unless an existing validator requires an additional field.
- Switching one `active_index` changes only the selected binding/provenance for that section.
- Timing-only changes do not change prompts, variants, or media bytes.

## Batch 3 — Managed media, kernel linkage, and executable script

Remove all shot-registration implementation and tests.

Revise tasks to:

- Add the unpackaged `scripts/build_storyboard.py`, containing validation, pure compilation, save, VO alignment, and render orchestration.
- Do not expose `--register-shots` in v1. Document shot linkage as deferred because the mounted API lacks shot update/delete semantics. A ghost or no-op flag is explicitly rejected.
- Perform complete read-only storyboard/path/hash preflight before kernel mutation.
- Normalize every selected asset route to a project-owned managed binding:
  - `path`: call `MediaService.import_file(..., realm="managed_local")`;
  - `media_id`: resolve the same-project managed media record;
  - `content_hash`: locate the same-project managed media record by normalized digest.
- Import all repo-external intro PNG and WAV files before timeline save or render. Never reference them in place and never use `external_local`.
- Confirm each import yields the canonical CAS locator and digest, then emit only `{file, content_sha256}`.
- Validate the compiled config and registry before timeline mutation.
- Save only through the existing kernel timeline service with CAS; never write authoritative `timeline.json`, `assets.json`, event logs, receipts, or `run.json` directly.
- Render through the existing managed `timeline_ref` run/task path.

Revise integration tests:

- managed import and deduplication;
- canonical locator plus digest shape;
- stale-root locator rebasing during render;
- malformed storyboard causes no media or timeline mutation;
- successful media imports followed by a failed timeline CAS remain safe, deduplicated kernel facts on retry;
- create/save/show, CAS failure, receipts/events, and canonical render admission.

Acceptance criteria:

- All 50 selected intro assets are kernel-managed before render.
- Repo-external in-place references fail preflight.
- Render containment and managed-locator ownership checks pass.
- No shot rows or `pinnedShotGroups` are created in v1.

## Batch 4 — Author and lock the 25-section intro storyboard

Replace the location and source tasks with:

- Author the canonical storyboard project-locally outside the Astrid worktree, under the `astrid-intro` project’s build area.
- Copy a hash-identical, reviewable snapshot to `.oracle/evidence/astrid-intro.storyboard.json`. Mark it as evidence, never as compiler input or a second authority.
- Include exactly the 25 `plan.json` sections; explicitly exclude `idea2_example`.
- Set `meta.style.text_materialization` to `"baked"`.
- Preserve title, bullets, and mink directives as declarative records, while compiling none of them as additional intro clips.
- Store each `final-slides/<slug>.png` and `slides-pyramid-full/<slug>.png` as entries in the same image block’s `variants[]`; set `active_index` to the `final-slides` entry.
- Persist full prompts, model/backend information, refs, seeds when known, and history inside those variant/storyboard records.
- Document PNG tEXt prompt/model/seed data as incidental provenance, not authoritative input.
- Omit all `generationId` values.
- Point VO blocks to the existing WAV sources, which Batch 3 imports into managed media.

Acceptance criteria additions:

- Canonical and evidence-copy SHA-256 hashes match.
- The dead `idea2_example` slug is absent.
- Every section has an active final-slide variant and an alternate pyramid variant where available.
- The storyboard predicts exactly 76 clips and 50 active registry assets.

## Batch 5 — Live compile and parity proof

Remove:

- all `--register-shots` execution;
- shots capture;
- `pinnedShotGroups` acceptance criteria.

Revise the parity assertions to require exactly, without a pre-approved delta:

- 25 image-plate clips;
- 25 caption clips;
- 25 VO-audio clips;
- one brand clip;
- 50 active registry assets;
- no live title, bullet, or mink clips in the baked intro.

For the variant proof:

- Change one section’s `active_index` from its final-slide entry to its `slides-pyramid-full` entry.
- Prove the inactive variants never entered the original registry.
- Prove only that section’s selected image binding and corresponding clip provenance changed.
- Prove all other clips, registry entries, prompts, variant records, and source bytes remained identical.
- Do not claim or fabricate generation linkage.

## Batch 6 — Render, evidence, documentation, and sync

Add:

- Include the canonical storyboard hash and evidence-copy hash in the evidence matrix.
- Document that:
  - storyboard variants/prompts are authoritative source provenance;
  - PNG tEXt is incidental;
  - `generationId` is intentionally absent;
  - shot registration is deferred from v1;
  - repo-external media must be imported into managed CAS before render.
- Verify the final rendered timeline contains the exact 76/50 structure, not an allowed delta.

# 2) NEW AREAS / POTENTIAL ISSUES

1. Verify that read-only preflight can compute the prospective CAS locator and digest before import, so malformed or structurally invalid storyboards cannot leave partial media facts.

2. Test the partial-success boundary where managed imports succeed but timeline CAS save fails. This is acceptable only if retry deduplicates those kernel media facts and creates no parallel authority.

3. Define custody mechanically: the evidence copy should contain the canonical source path and SHA-256, and the compiler must reject or simply never consume `.oracle/evidence/` as input.

4. Confirm inactive variants are not emitted into the timeline registry. Otherwise the intro would exceed the exact 50-asset oracle even though only 50 assets are referenced.

5. Verify all 25 `slides-manifest.json` VO strings byte-match `plan.json`, not merely the spot-checked examples.

6. Test baked/live materialization explicitly to prevent a future compiler change from either duplicating baked pixels or silently dropping live storyboard text.

# 3) RESOLVED OPEN QUESTIONS

- Baked content uses one explicit storyboard-level materialization mode; no filename heuristic.
- `AssetEntry.generationId` is omitted.
- The canonical storyboard is project-local; `.oracle/evidence/` contains a hash-identical review snapshot.
- Prompts and variants live inside storyboard records; no `<asset>.prompt.json` sidecars.
- Shot registration is deferred from v1; no append-only approximation and no ghost flag.

# 4) NORTH STAR REJECTION

The following are explicitly rejected:

- treating `build/timeline/{timeline,assets}.json` as an authority;
- referencing repo-external intro media in place;
- using `external_local` to bypass managed ownership;
- synthesizing `generationId` from content hashes, request IDs, or run-directory metadata;
- adding physical prompt sidecars or another provenance ledger;
- shipping a no-op `--register-shots` flag;
- inventing shot update/delete behavior around an append-only mount;
- adding a packaged compiler layer when one checkout script is sufficient;
- allowing inactive variants to bloat the executable registry;
- accepting clip/asset-count deltas where the parity rule is now exact.

These cuts preserve the simplest design: one packaged schema/loader, one unpackaged compiler entry point, one managed-media path, and one kernel timeline execution authority.
