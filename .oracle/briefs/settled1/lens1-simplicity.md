# SETTLED-PLAN SENSE-CHECK — LENS 1: SIMPLICITY / KISS / YAGNI

You are an independent critic reviewing a plan BEFORE any execution. Your lens: streamline and challenge abstraction. The plan must not be rewritten — identify concrete simplifications with evidence, ranked by impact.

Wrap this lens: the outcome can be reached with less work, fewer steps, or fewer handoffs; every proposed abstraction/layer/interface/config surface is necessary, not speculative; existing mechanisms are reused instead of parallel ones; batches/dependencies/sync points form the simplest safe order; every retained element advances an agent-goal criterion and the North Star without reproducing an anti-pattern.

Deliver: RANKED concrete findings (each: what to simplify → where in the plan → why safe → what breaks if ignored). Verify claims against the actual repo where cheap (you have file+web tools; repo root = this project dir). Do NOT widen scope, do NOT invent architecture, do NOT rewrite the plan. End with your 3 biggest recommended cuts. <500 words.
===== NORTH STAR (complete; immutable) =====
---
type: anchor
anchor_type: north_star
slug: astrid-first
title: 'North Star: Astrid First'
created_at: '2026-08-13T20:01:16.984884+00:00'
---

# North Star: Astrid First

Normative source of truth: `docs/unified-data-model-plan-v10-20260813.md` (in this initiative's `docs/`). Plugin/generalization feedback source: `docs/openrouter-chat-20260814-plugin-data.md`. Vision anchor (the long-term destination this milestone serves, including the kernel-audit and promotion-candidate logic): `docs/unified-data-master-plan-20260814.md`. This North Star distills the durable end-state every milestone must preserve; milestone briefs narrow local scope without redefining this destination.

## End State

A standalone, local-first creative product named Astrid: one Python process owns one SQLite database (exactly the v10 20-table Astrid catalog) plus a managed media root, and is the single semantic writer for projects, tasks, runs, media, timelines, references, and shots. The catalog is deliberately layered: an agent-agnostic 14-table kernel (`schema_migrations`, projects, events/streams/receipts, runs/evidence, tasks/dependencies/attempts/outputs, and media/locations/relations) plus in-tree timeline (1 table), shots (2 tables), and references (3 tables) packs. Core table primitives are reusable; the domain data acts like a plug-in, so a future software-engineering agent can use the unchanged kernel with its own packs. The reigh web editor remains the frontend and talks to Astrid over the existing bridge wire contract (loopback; CAS timeline saves; asset Range serving), which must keep working through and after the milestone. Zero-config setup: install, `astrid serve`, open the editor, pair, work — no accounts, billing, cloud services, or provider secrets required for the core journey.

The model's one-sentence foundation: **tasks execute; everything else is an event; every exact asset is media; references add project semantics to media.**

**Vision anchor.** The master plan (above) is the durable vision: a plug-in data substrate reusable across agents — this milestone is its first, proving composition. Kernel citizenship is audited, not assumed: each of the 14 kernel tables earns its keep as an agent-agnostic primitive (migration bookkeeping, project scope, events/receipts, runs/evidence, tasks/dependencies/attempts/outputs, media/locations/relations — provenance and observation, not domain semantics). The six pack tables (timeline, shots, references) are deliberately NOT kernel today; their *patterns* (whole-document CAS; ordered exact-media containers) are promotion candidates that move into the kernel only when at least two real compositions prove the common need (kernel-evolution rule) — then the generalized primitive is promoted and Astrid's packs become thin aliases over it. Promotion is earned by a second composition's requirement, never assumed from resemblance.

## Non-Negotiables

- Exactly the v10 20-table Astrid schema: kernel 14 + timeline 1 + shots 2 + references 3; no plan/step tables, no legacy/session/thread/lease tables, no dormant platform tables (accounts, billing, sharing, sync, remote worker). Catalog tests assert the core tables plus the tables declared by installed packs, rather than hardcoding 20 as a universal kernel catalog.
- `schema_migrations` is pack-aware from creation: `pack TEXT NOT NULL DEFAULT 'core'` and `PRIMARY KEY (pack, version)`. Core and packs migrate independently, forward-only, in declared dependency order.
- Kernel DDL does not hardcode pack vocabulary: `event_streams.stream_type` has no closed `CHECK`; repositories validate stream types against the startup registry populated by `register_pack()`. Event and command kinds are registered and namespaced (`timeline.saved`, `shot.item_added`, `reference.primary_changed`).
- Media is kernel citizenship, including the `task_outputs.media_id` coupling. Source files, diffs, logs, and creative assets share the same exact-byte primitive; media must not be demoted into a domain pack.
- Plugin laws: packs may FK into kernel tables, but kernel tables never FK into pack tables and refer to pack subjects only through `events.subject_type`/`subject_id`; cross-pack references use only kernel currencies such as `media_id` and `task_id`.
- Packs never own a writer. Each registers repositories with the one kernel write queue and receives a UoW handle inside the kernel's `BEGIN IMMEDIATE`, including project-sequence allocation, stream-head CAS, event append, and receipt writing.
- Kernel-evolution rule: a table enters the kernel only when at least two real compositions prove the same semantic need and implementing it separately would break atomicity or interoperability. The current 14 kernel tables are the audited, earned set; timeline/shots/references stay packs until promotion is earned by a second composition.
- Every pack command passes the reusable kernel conformance kit: idempotent replay, mismatched-key rejection, statement-boundary crash injection, and same-project assertions. In-tree packs have manifests declaring ID/version/dependencies, migrations, stream/event/command kinds, repositories, conformance, and CLI/bridge mounts.
- Task/event principle: a task exists only for immutable executable work with exclusive claim or fenced attempts; every other meaningful mutation is an append-only, hash-chained, project-ordered event. Events, heads, projections, outputs, associations, and the command receipt commit or roll back atomically (one writer queue, `BEGIN IMMEDIATE`).
- Terminal immutability and attempt fencing: terminal tasks never resurrect; stale attempts never win; materialization is exactly-once (receipts, idempotent replay, mismatched-key rejection).
- Timeline whole-document CAS: document + asset registry advance together against the stream head; stale saves return 409 with no mutation. The current editor's provider/persistence tests must pass against the repository-backed bridge (the "editor contract/provider" lane).
- Media identity is verified byte SHA-256; paths/URLs/source IDs are replaceable locations/aliases, never identity. Exact placements and reference associations never inherit invisibly across variants.
- Single writer: repositories are the only semantic writers; bridge, CLI, SDK, executor, media import all route through them. FSA and Supabase do not exist as authorities.
- The Reigh timeline-sync requirement stays live: the existing editor↔Astrid bridge contract keeps working through the milestone (ordinary editor tests as the gate — no continuity ceremony).
- References (characters/places/objects/clothing) are project-scoped, media-associated (canonical/used_as_input/depicts/inspired_by), linkable, event-backed projections.

## Explicit Non-Goals

- No legacy data import beyond `media import` (bytes only). No project/history/run-dialect/timeline-chain/audit import, no aliases, no parity/cutover machinery.
- No plan/step/orchestration machinery (group/repeat/for_each/supersede, run_steps, fake parent tasks) — replaced by runs that directly group immutable tasks + `task_dependencies`.
- No editor FSA persistence; no Supabase; no remote GPU execution; no hosting/Turso; no experiments/publish/accounts/billing/tenancy/sync/replication.
- No new editor features; no `scheduling`/duration commitments in documents.
- No speculative catalog tables; packs/components/elements/models stay file-side manifests.
- No dynamic plugin discovery/loader at GA and no third-party install/uninstall platform. Establish `core/` + in-tree `packs/{timeline,shots,references}` boundaries and one explicit startup registration path now; extract/share the kernel and add a loader only when a second agent is real (boundary now, loader later).

## Allowed Temporary Bridges

- During m1–m3, the existing file-backed timeline code may remain in the tree for reference, but no supported write path may use it once its repository route lands; delete the old authority in m6 (teardown).
- A bounded "editor contract adapter" may translate repository errors to the frozen wire shapes (409/422/404) — it is a thin mapping, not a second backend.
- Decision artifacts (media root/layout, fan-out limits, closed vocabularies, platform matrix) may be recorded in the initiative's docs before the milestone that consumes them; they are prep, not scope changes.

## Drift Signals

- Any table added beyond the 20 (especially plan/step/legacy/catalog/dormant-platform tables) without a v10 amendment.
- A receipt/event that can be lost or duplicated on retry; an idempotency mismatch that mutates state; a crash path that yields neither old nor complete.
- The editor's provider tests failing against the repository bridge, or a save path that bypasses repositories.
- Media referenced by path/URL instead of media ID; path hashes treated as content identity.
- A kernel table foreign-keying into a pack table; a pack reaching directly into another pack instead of using kernel currencies or a declared dependency; hardcoded pack stream-type/event-kind/command-kind enums in kernel DDL.
- A pack opening a transaction or owning a writer instead of using the kernel UoW; a pack command bypassing the kernel conformance kit; deleting a pack breaks the kernel test suite.
- Work that "preserves" old Astrid data, dialects, threads, sessions, or plans; a second writer; a browser-required acceptance item (except the frozen editor test lane).
- "It works locally" accepted without crash injection, backup/restore proof, or the GA acceptance items 1–12 in v10 §5.3.

===== AGENT GOAL (frozen contract) =====
# Agent Goal — shots as sub-timelines (Phase A) + ffmpeg text rendering

[North Star](./northstar.md). This run advances the ONE-store kernel principle by making
storyboard sections first-class kernel citizens: real `shots` rows owning their own
`timelines` documents, parent timeline referencing them as composite `shot` clips, and
render-prep expansion producing byte-equivalent flat output — proven by re-rendering the
Astrid intro through the extended ffmpeg backend (no Remotion in the path).

## Context

- Plan doc: `docs/storyboard-pipeline.md` — "Shots projection & sub-timeline plan" (Phases A/B/C).
- Verified facts from Phase 2 exploration (`.oracle/findings/`):
  - `shots`/`shot_items` tables + `ShotsService` (idempotency keys, metadata_json, item positions, multi-item shots) exist and are renderer-neutral (`astrid/packs/shots/`, `astrid/sdk/shots.py`).
  - Plugin law: shots pack must never FK/import the timeline pack; shot↔timeline-document link lives in `shots.metadata_json` (data, not FK).
  - Timeline clip schema has no children; a `shot` clip type is required.
  - The current intro render is static slides + text overlay + VO with hard cuts; **zero** animation (fade effects declared but unimplemented in Remotion). Entirely ffmpeg-replicable.
  - `rendering.ffmpeg` backend exists, currently `media_only`; `rendering.remotion` selector is an ffmpeg-first auto-routing pair. Extend ffmpeg's capabilities (text clip support) rather than add a new backend.
  - Render routing: `_translate_legacy_selector` in `astrid/core/rendering/service.py`; per-candidate `support()` checks.
- In-flight (protect, not part of this run): Remotion self-hosted fonts fix (`remotion/src/fonts.ts`).

## Objective

Deliver Phase A of the shots projection + sub-timeline plan, plus the ffmpeg text-rendering
extension, so the storyboard pipeline renders end-to-end without Remotion.

Deliverables
- A1 **Shot registration**: storyboard sections → `shots` rows + `shot_items` via `ShotsService` with deterministic idempotency keys (`<project>:shot:<slug>`, items `:image`/`:vo`); metadata carries slug, nav, prompt.
- A2 **Shot sub-timelines**: per shot, a `timelines` row whose document is the section composition (broll plate + caption text + VO audio, 3 clips); `timeline_document_id` recorded in the shot's `metadata_json` (data, not FK — plugin law).
- A3 **Parent compiled as shot clips**: compiler emits 25 `shot` clips (+ brand wordmark) instead of 75 flat clips; each `params.shot_id` → real kernel shot id; `at`/`hold` placement in parent document.
- A4 **Render-prep expansion** in the kernel timeline layer: resolve `shot` clips via `timeline_document_id`, splice sub-clips at the shot's `at` window (offset + clamp to hold). Expanded document byte-equivalent (modulo clip ids) to today's flat compile output — the existing golden parity test becomes the expansion test.
- A5 **ffmpeg text extension**: `rendering.ffmpeg` accepts text clips — rasterize text to transparent PNG (PIL), overlay with `enable=` timing + fade envelope; update `renderer.yaml` capabilities (clip_types: media+text, text_overlay, fade_envelope) and `support.py`. Intro renders via ffmpeg: seconds, no Chrome/webpack/CDN.
- A6 **End-to-end proof**: storyboard → compile (shots + shot-clip parent) → save to kernel → render via ffmpeg → open. Golden parity maintained: 76 clips / 50 assets / 177.53s ±0.5 (from expansion).

Non-goals
- Phase B (Reigh editor integration onto shot documents) — separate future run; exploration finding `.oracle/findings/reigh-app-shot-structures.md` preserved as input.
- Phase C (renderer-native nested compositing) — explicitly deferred until Phase A green + concrete limitation hit.
- No UI editor changes; no kernel core schema changes; no `pinnedShotGroups` changes; no storyboard v1 schema changes.
- No Remotion work beyond preserving the in-flight font fix.

## Model policy (user-pinned)

- Oracle / planner / [XHARD]: **grok-4.6** (grok CLI, `--reasoning-effort high`). Fallback if unavailable: GPT-5.6 Sol via `codex exec`. No automatic routing.
- Explorer / normal executor: **DeepSeek V4 Flash 0731** (`launch_hermes_agent.py --model="deepseek:deepseek-v4-flash"`, toolsets file,web,terminal). No automatic routing.
- Pinned models authoritative unless evidence shows unavailability (then report + fall back as declared above).

## Done criteria

1. Shot registration idempotent: running the compiler twice yields the same 25 shots / 50 items (no duplicates, receipts replay-safe).
2. Each shot's `metadata_json` carries `timeline_document_id` resolving to a real `timelines` row (25 sub-documents).
3. Parent timeline = 25 `shot` clips + wordmark; `timelines show` reports counts consistent with the golden test (76 clips / 50 assets post-expansion, 177.53s ±0.5).
4. Render-prep expansion test: expanded document byte-equivalent (modulo clip ids) to current flat compile output — golden parity test green.
5. Intro renders through ffmpeg text extension: `astrid timelines render ... --backend rendering.ffmpeg` succeeds; output ≈177±3s, 3 spot-check frames show captions; no Remotion invocation in the path.
6. Evidence matrix maps every criterion → command/path/result. grok oracle PASS per batch + final review (≤3 passes).

## Validation commands

- `python3 scripts/build_storyboard.py validate --story storyboards/astrid-intro.storyboard.json`
- compile with shots projection enabled (project astrid-intro)
- `python3 -m pytest tests/ -k storyboard -x -q` (schema + compiler golden/expansion)
- `astrid timelines show main --project astrid-intro` counts
- `ASTRID_PROJECTS_ROOT=... astrid timelines render main --project astrid-intro --backend rendering.ffmpeg --output-name shot-pipeline.mp4`
- `ffprobe` duration; frame extraction spot-checks

## Sync/authorization

- Commit batches on branch `megado/oracle-run-storyboard` (this worktree).
- Push that branch to origin authorized at finish. Never merge to main.
- Opening local videos/files authorized. Local-only: no deploy, no Supabase, no remote.
- The in-flight Remotion fonts fix (`remotion/*`, `remotion/public/`) is protected: do not revert or commit it as part of this run's batches unless required by a batch's own scope.

## Stop conditions

- Blocked if grok AND codex both unavailable for oracle (report + halt after safe checkpoint).
- Escalate scope expansion beyond A1–A6 (e.g. Phase B/C asked mid-run).
- Failed if a done criterion is reproducible-unmet after rework; `undetermined` if evidence insufficient.
===== PLAN SNAPSHOT (immutable; sha256 d35a66f5a9f42fd11182d7fc3eef13fc28e1f101261c9034d5587736fc42fc6b) =====
# Plan — shots as sub-timelines (Phase A) + ffmpeg text rendering

This plan covers the frozen agent goal A1–A6 only. It supersedes `.oracle/plan.md` v8 (completed storyboard compiler). Phase B/C, Remotion, editor UI, kernel DDL, `pinnedShotGroups`, and storyboard v1 schema redesign are out of scope.

**Models (user-pinned):** planner/oracle/[XHARD] = grok-4.6; executor/explorer = DeepSeek V4 Flash 0731. No automatic routing.

**Classification:** every task is `normal`. None meets the [XHARD] bar: each is a bounded mechanical change with file-level tests; the plugin-law and splice rules are decided here, not left as executor judgment.

**Huge-run:** **no.** Best-effort implementation effort **4–6 working days** (one executor stream). Under the 2-week threshold; no cumulative big-batch review policy.

**North Star (this run):** storyboard sections become pack-citizen shots that own timeline documents; the parent timeline is a CAS document of `shot` clips; renderers still see a flat document. Application code (compiler/CLI) is the only composer; repositories remain the only writers.

---

## Settled design (do not relitigate in execution)

### Plugin law

- Shots pack does **not** import or FK the timeline pack. Association is data: `shots.metadata_json.timeline_document_id`.
- Timeline/core must **not** import the shots pack. Expansion does **not** `SELECT` from `shots`.
- Dual-write (intentional, not an FK):
  - shot metadata: `{slug, nav, prompt, timeline_document_id}`
  - parent clip `params`: `{shot_id, timeline_document_id}`
- Expansion trusts **clip params** `timeline_document_id` (parent document is the CAS authority). Shot metadata is the shot-side record for Phase B.
- No new tables, no `shot.update` command, no shots→timeline pack dependency, no kernel FK into packs.

### No metadata-update command (YAGNI)

`ShotsService` has create/add_item/remove_item/reorder only. Create request hash includes metadata (`repository.py:638-646`). Therefore:

1. Create-or-save the **sub-timeline first**.
2. Create the shot with **complete** metadata including `timeline_document_id`.
3. `add_item` image then vo.

Timeline id is stable because `TimelinesService.create` derives it from `(command_kind, project_id, idempotency_key)`.

### Sub-timeline identity

| | value |
|---|---|
| slug | `shot-{section_id with `_` → `-`}` (timeline slug grammar `^[a-z0-9]+(?:-[a-z0-9]+)*$`, `repository.py:176`) |
| name | section id (original, underscores ok) |
| create key | `{project}:shot-timeline:{section_id}` |
| shot create key | `{project}:shot:{section_id}` |
| item keys | `{project}:shot-item:{section_id}:image` and `:vo` |
| `set_default` | false |

Intro ids (`two_ideas`, `idea1_vc`, …) are unique after hyphenation. Fail closed on collision.

### Recompile

- Timeline: `show(slug)` → if missing `create`; if present `save` with `expected_version` (content may change; create identity includes config, so never `create` again with a mutated document).
- Shot create / add_item: same keys, identical request → receipt replay; changed media_id/metadata under the same key → `idempotency_mismatch` (fail closed). Frozen intro is identical-input replay.
- Parent `main`: `timelines save` CAS as today.

### Documents

**Sub-timeline** (local time, 3 clips, at=0):

- tracks: `captions` (visual), `broll` (visual), `a1` (audio) — no brand
- `vo_{slug}` media a1, `from=0` `to=duration`
- `cap_{slug}` text captions, `hold=duration+GAP`, same styling as today (`_CAPTION_*` in `scripts/build_storyboard.py`)
- `broll_{slug}` media broll, `hold=duration+GAP`
- registry: the section's img + vo assets only

**Parent** (global time):

- tracks unchanged: brand, captions, broll, a1
- clips: `brand_wordmark` + 25 `clipType: "shot"` on track `broll`
- shot clip:

```json
{
  "id": "shot_<section_id>",
  "at": <section start>,
  "track": "broll",
  "clipType": "shot",
  "hold": <duration+GAP>,
  "params": {"shot_id": "<kernel shot id>", "timeline_document_id": "<timelines.id>"}
}
```

- registry: full 50 assets (same as today's flat compile)
- brand stays on the parent, never inside a shot

`clipType` is an open string (`validators/timeline.py:191-196`). `shot` is valid at authoring. Render admission (`managed_timeline.py:86-132`) currently rejects it — expansion **must run before** `validate_managed_render_snapshot`.

### Expansion (`astrid/core/timeline/expand_shots.py`)

Pure function, no pack imports:

```python
def expand_shot_clips(
    config: Mapping,
    registry: Mapping,
    *,
    load_timeline: Callable[[str], tuple[Mapping, Mapping]],
) -> tuple[dict, dict]:
    ...
```

Rules:

1. Pass through non-shot clips (brand).
2. For each `clipType=="shot"`: require `params.shot_id` and `params.timeline_document_id` (non-empty strings). `load_timeline(timeline_document_id)` → `(sub_config, sub_registry)`.
3. Nested `shot` clips → fail closed.
4. For each sub-clip: `new_at = parent.at + sub.at`; clamp so `end <= parent.at + parent.hold` (hold on text/stills; `to-from` on audio). Drop sub-clips with non-positive duration after clamp.
5. Preserve sub-clip `id`s (`vo_*` / `cap_*` / `broll_*`) — they are globally unique by slug. Comparison against today's flat compile is then id-stable; still assert modulo ids as the frozen criterion requires.
6. Do not merge registries if parent already has all assets (intro). If a sub-clip asset is missing from parent, copy from sub-registry (fail closed if still missing).
7. Replace the shot clip with the spliced sub-clips; do not leave the `shot` placeholder.
8. One level only. Deterministic clip order: brand first, then sections in parent shot-clip order, each section's vo/cap/broll as in the sub-doc.

**Hook (managed render only):** `astrid/sdk/invocation.py:_prepare_managed_render_inputs` after `resolve_managed_render_snapshot` (line 709) and **before** `validate_managed_render_snapshot` (line 715). Loader: `SELECT document_json, asset_registry_json FROM timelines WHERE id=?` on the same sqlite already opened in `resolve_managed_render_snapshot` — add a sibling helper there, pass into expand. Do **not** expand the stored kernel document. Do **not** expand the editor/bridge load path. File-mode `timeline=<path>` has no sibling loader: if it contains `shot` clips, fail closed with a typed error telling the caller to use `timeline_ref`.

`timelines show` stays the **stored** parent (26 clips). CLI `_cmd_show` (`packs/timeline/cli.py:128`) additionally prints a derived `expanded` summary `{clips, assets, duration}` when any clip is `shot`, by calling expand with a show-based loader. Do not change `TimelineReadModel`.

### Compiler split

- `compile_storyboard(...)` remains the **flat** emitter (today's 76-clip document). Keep it as the expansion expected document. Fix image resolution: `image.path` XOR active `image.variants` via existing unused `_variant_import_path` (`build_storyboard.py:466`). Loader already accepts both (`loader.py:154-176`). Intro JSON uses path; golden fixture uses variants. This is not a schema change.
- New `project_shots(...)` (same module or `astrid/core/storyboard/project_shots.py`): given flat section facts + `AstridClient`, performs the kernel writes and returns `{section_id: {shot_id, timeline_document_id}}`.
- New `compile_shot_parent(flat_config, id_map) -> parent_config`: replaces per-section vo/cap/broll with one shot clip; keeps brand.
- CLI: `compile --shots` (requires `--project`) runs imports → project_shots → write parent sidecars. Default without `--shots` stays flat so file-only compiles keep working.

Extract `_section_clips` from the current inline loop (`build_storyboard.py:268-377`) so flat compile, sub-docs, and tests share one emitter.

### ffmpeg (intro-shaped, not a general compositor)

Today's backend cannot render the intro even after expansion: `clip_types:[media]`, exactly one visual track, no visual overlap, no `hold` on media, no `effects`, no `clipType=text` (`support.py:228-231,282-283,306-316,191-196`).

Relax **only** this shape (YAGNI: no overlapping videos, no x/y transforms, no speed, no transitions):

1. `clipType` `media` and `text` (keep rejecting everything else except the existing audio-reactive special case).
2. Visual **media** clips: still sequential, no-gap, no-overlap. Duration = `hold` for stills (no `from`/`to`); `from`/`to` for motion pictures as today.
3. Extra visual tracks allowed **iff** they contain only text clips (brand, captions).
4. Text clips ignored by the sequential visual-media coverage check.
5. `effects.fade_in` / `effects.fade_out` allowed **only** on text. Same keys on media still fail closed (`test_ffmpeg_support.py` case `"effects"` stays red for media).
6. Text `params` may include `anchor, offsetX, offsetY, maxWidth, weight, textShadow` (intro frozen params). Other media params still rejected.

**Render path** (`command.py:build_filter_graph`, not a new backend, not the compositor finalizer):

1. Rasterize each text clip to a transparent PNG with Pillow (`pyproject.toml` already has `pillow>=12.2,<13`). Helper: `astrid/packs/rendering/backends/ffmpeg/text.py`.
2. Base video: stills as `-loop 1 -t HOLD -i img.png`, concat in `at` order (same concat model as today).
3. Overlay each text PNG: `overlay=x:y:enable='between(t,at,at+hold)'` plus fade alpha from `effects` (formula in `docs/ffmpeg-text-extension.md`).
4. Audio: unchanged sequential concat (`command.py:285-333`). No `amix`.
5. Anchor → x/y: `bottom-center` + `offsetY=56`; `top-right` + `offsetX=48, offsetY=40`; wrap at `maxWidth` by pixel width.

Font: system fallbacks (Helvetica/Menlo/DejaVuSansMono/Arial). Do **not** touch `remotion/*`. If no truetype font is found, `support()` fails closed with a reason (tests that don't encode may inject a font path). Pixel-perfect Remotion match is **not** a criterion; captions visible on 3 frames is.

`--backend rendering.ffmpeg` is a qualified selector (`service.py:184-189`): support must return `supported=True` or the render hard-fails. Do not change default auto-route.

Update `renderer.yaml`: `clip_types: [media, text]`, `features.media_only: false`, `text_overlay: true`, `fade_envelope: true`. Flip `test_support_rejects_non_media_timeline` / `unknown_clip_kind` so a **bare** `clipType=text` on the only visual track is still unsupported (no plate); add a stills+text fixture that **is** supported.

---

## Additional areas to explore (only these)

Phase 2 already verified shots mount, ffmpeg capabilities, and render routing. Remaining gaps are small; explore before freezing the tasklist, not as architecture:

1. **`build_filter_graph` still-image input argv** (`command.py:351-401`, `:161-283`) — confirm how `-loop 1 -t` splices into the existing unique-asset `-i` list when the same PNG is not reused (intro: 25 distinct stills).
2. **Managed-render SQL loader** — `resolve_managed_render_snapshot` (`managed_timeline.py:247-275`) currently loads one row; confirm adding `load_timeline_document(conn, id)` there vs a second connection.
3. **Compiler golden currently vs `image.path`** — `compile_storyboard` reads `image["path"]` (`:273`) while `test_compiler_golden` fixtures are variants-only. Confirm whether that test is red in this tree; the path-OR-variant fix is in B3 regardless.
4. **Temp-project test helper** — reuse `compose_standard_application` / `AstridClient.open` patterns from `tests/sdk/test_shots.py` and `tests/v10/_m7_fixture.py`; do not invent a third harness.
5. **Caption wrap on the longest intro VO** — one offline PIL wrap of `cta` / `idea2_contribute` to pick wrap algorithm (greedy pixel-width). Not a product surface.

No further exploration of Reigh nesting, Remotion, or Phase C.

---

## Open questions (settled here unless evidence contradicts)

| Q | Decision |
|---|---|
| Where does expansion read `timeline_document_id`? | Clip params. Shot metadata is the shot-side copy. |
| New `shot.update`? | No. |
| `timelines show` 76 clips? | Stored document stays 26. CLI prints derived `expanded` counts. Pytest expansion test is the 76-clip proof. |
| Expand file-mode renders? | No. Fail closed on leftover `shot` clips. |
| Default compile output? | Flat unless `--shots`. Validation commands pass `--shots`. |
| ffmpeg overlapping visual media? | Still rejected. |
| New backend / compositor finalizer for intro? | No. Extend `rendering.ffmpeg`. |
| Change default render auto-route? | No. A6 passes `--backend rendering.ffmpeg`. |
| Storyboard v1 path vs variants? | Compiler consumes both; do not rewrite intro JSON or bump schema. |
| Nested shots? | Fail closed (Phase C). |

---

## Tasklist

Parallel: **B1 ∥ B2**. B3 after B2. B4 after B1+B3.

### Batch 1 — A5 ffmpeg text + stills + overlay

**NS:** single renderer contract; extend existing backend; no second authority.

| ID | Task | Class | Files | Acceptance |
|---|---|---|---|---|
| T1 | Rasterize text clips (Pillow): wrap, anchor, shadow, font fallback | normal | `astrid/packs/rendering/backends/ffmpeg/text.py` (new); tests under `tests/packs/rendering/` | Unit: PNG is RGBA, non-empty alpha, wrap respects maxWidth; missing font → explicit error |
| T2 | `support.py` intro-shaped relaxation | normal | `support.py`; `renderer.yaml`; `test_ffmpeg_support.py`; `test_ffmpeg_backend.py` | Stills (`hold`) + text overlays + extra text-only visual tracks + text fades → `supported=True`. Existing fail-closed cases still fail: speed, crop, transforms, media effects, visual **media** overlap/gap, unknown clip kinds other than text, `clipType=text` with **zero** visual media. `media_only` feature false when text present |
| T3 | `build_filter_graph`: looped stills + overlay chain + fade alpha; audio concat unchanged | normal | `command.py`; `run.py` only if protocol path needs a temp dir for PNGs | Filtergraph contains `overlay` + `enable=between`; stills use `-loop`; audio still `concat=a=1` not `amix`. Existing media-only tests green (`test_ffmpeg_backend.py`, `test_ffmpeg_support.py`) |
| T4 | Live encode of a 2-section stills+text+wav fixture | normal | same + a small committed fixture PNG/WAV if needed | ffmpeg argv runs; duration ≈ sum(holds); 1 extracted frame has non-black caption pixels |

**Checkpoint B1:** `pytest tests/packs/rendering/test_ffmpeg_support.py tests/packs/rendering/test_ffmpeg_backend.py -q` green; new stills+text tests green; `renderer.yaml` declares `text`. No Remotion files touched.

### Batch 2 — A4 render-prep expansion

**NS:** kernel/timeline layer expands; shots pack untouched; no new tables.

| ID | Task | Class | Files | Acceptance |
|---|---|---|---|---|
| T5 | `expand_shot_clips` pure function + clamp/offset/nested-fail tests | normal | `astrid/core/timeline/expand_shots.py`; `tests/core/timeline/test_expand_shots.py` | Fixture: 2 shot clips + brand → expanded vo/cap/broll + brand. Offset/clamp proven. Missing params / nested shot / missing loader id fail closed. Byte-equivalent to a canned flat doc **modulo clip ids** (and equal including ids if ids preserved) |
| T6 | Hook: expand after snapshot resolve, before render admission; SQL loader by timeline id | normal | `managed_timeline.py`; `invocation.py:709-715`; `tests/packs/rendering/test_managed_timeline_render.py` | Snapshot with `clipType=shot` becomes flat before `_validate_render_element_clip_types`. Stored sqlite document unchanged. Unknown `clipType=shot` **without** expand still fails admission (file-mode / tests that skip expand) |
| T7 | CLI `timelines show` derived expanded counts | normal | `packs/timeline/cli.py` `_cmd_show` | Human/JSON extra `expanded: {clips, assets, duration}` when shot clips present; `TimelineReadModel` unchanged |

**Checkpoint B2:** expand unit tests green; managed-render test proves expand-before-validate; `pytest tests/packs/rendering/test_managed_timeline_render.py -q` green.

### Batch 3 — A1–A3 compiler shots projection

**NS:** compiler is application-layer; writes only through `client.shots` + `client.timelines` + `client.media`; plugin law.

| ID | Task | Class | Files | Acceptance |
|---|---|---|---|---|
| T8 | Resolve image as `path` XOR active variant (`_variant_import_path`); extract `_section_clips` | normal | `scripts/build_storyboard.py` | Flat compile works for intro JSON (path) and golden fixture (variants). No storyboard schema change |
| T9 | Sub-doc builder (local at=0, 3 clips, 2-asset registry) | normal | same | One section → 3 clips at 0; hold/to match flat compile's per-section durations |
| T10 | `project_shots` via SDK: create-or-save timeline, create shot with full metadata, add_item ×2 | normal | `scripts/build_storyboard.py` or `astrid/core/storyboard/project_shots.py`; `tests/test_compiler_shots.py` (temp project) | 2-section fixture → 2 shots, 4 items, 2 timeline rows. Second run: same ids, no extra rows (receipt replay / save). `show` metadata has `timeline_document_id` resolving to that row. Compiler does not import `astrid.packs.timeline` from `astrid.packs.shots` |
| T11 | Parent emitter: 25 shot clips + brand; CLI `--shots` | normal | `build_storyboard.py`; CLI parser | Parent `len(clips)==26`, clipTypes `{shot×25, text×1}`. `--shots` writes that sidecar |
| T12 | Golden becomes expansion test | normal | `tests/test_compiler_golden.py` | Keep flat compile assertions (76/50/177.53±0.5) on `compile_storyboard`. New test: `--shots` parent + in-memory expand == flat **modulo clip ids**. Track order, caption text, holds, brand hold preserved |

**Checkpoint B3:** `pytest tests/ -k storyboard -x -q` green (schema + golden + shots projection + expansion). Twice-compile on a temp project: 25 shots / 50 items, no duplicates.

### Batch 4 — A6 end-to-end proof

**NS:** one store; repositories only; ffmpeg path; no Remotion; no deploy.

| ID | Task | Class | Files | Acceptance |
|---|---|---|---|---|
| T13 | Compile intro with `--shots` against `ASTRID_PROJECTS_ROOT` for `astrid-intro`; save parent `main` | normal | commands only; evidence under `.oracle/evidence/` | 25 shots, 50 items, 25 sub-timelines, parent 26 clips |
| T14 | `astrid timelines render main --backend rendering.ffmpeg --output-name shot-pipeline.mp4` | normal | evidence | Exit 0; no Remotion/webpack/Chrome in the command/process; `ffprobe` duration ≈177±3s |
| T15 | Frame spot-checks (open, idea1_vc, cta_agents) | normal | `ffmpeg -ss … -frames:v 1` + evidence notes | Captions visible on all 3 frames |
| T16 | Evidence matrix + `docs/storyboard-pipeline.md` Phase A marked done; `docs/ffmpeg-text-extension.md` current | normal | those docs; `.oracle/evidence/final-matrix.md` | Every done criterion maps to command/path/result. Protected `remotion/*` not in the batch diff |

**Checkpoint B4:** all six agent-goal done criteria evidenced. Oracle final review (≤3 passes). Push `megado/oracle-run-storyboard` (no merge to main). Open the mp4.

---

## Validation commands (from agent goal)

```bash
python3 scripts/build_storyboard.py validate --story storyboards/astrid-intro.storyboard.json
ASTRID_PROJECTS_ROOT=<root> python3 scripts/build_storyboard.py compile \
  --story storyboards/astrid-intro.storyboard.json \
  --vo-align <plan.json> --project astrid-intro --shots \
  --out build/storyboard-compiled
python3 -m pytest tests/ -k storyboard -x -q
astrid timelines show main --project astrid-intro   # stored 26 + expanded 76/50/177.53±0.5
ASTRID_PROJECTS_ROOT=<root> astrid timelines render main \
  --project astrid-intro --backend rendering.ffmpeg --output-name shot-pipeline.mp4
ffprobe -show_entries format=duration -of default=nw=1:nk=1 <mp4>
```

---

## North Star alignment and anti-patterns

**Advances**

- Shots pack used as designed (exact-media items, receipt idempotency, opaque metadata).
- Timeline pack used as designed (slug create, whole-document CAS save).
- Application compiler is the composer; one writer queue; media identity is SHA-256 / `media_id`.
- `shot` clip is timeline-document data, not a new table — promotion not assumed.
- Renderers unchanged in contract: they receive a flat expanded document.
- Reigh bridge/editor load path not rewritten (Phase B).

**Must not**

- Add tables beyond the v10 20; add `shot.update`; FK shots→timelines or timeline→shots.
- Import `astrid.packs.timeline` from `astrid.packs.shots` (tested).
- Put expansion in the shots pack or in ffmpeg (that's Phase C).
- Treat path/URL as media identity; write kernel ids back into the storyboard JSON.
- Open a pack-owned transaction; bypass `ShotsService`/`TimelinesService`/`MediaService`.
- Add a `rendering.ffmpeg-text` backend or route intro through the compositor finalizer.
- Touch `remotion/*` / `remotion/public/` (in-flight fonts fix).
- Expand on the bridge save/load path (would flatten shot clips for the editor).
- Phase B `pinnedShotGroups` / shot editor; Phase C nested renderer compositing.
- Accept “it rendered” without crash-safe receipts on the shot/timeline creates (replay test) or without the expansion golden.

---

## Effort and [XHARD]

| Batch | Effort | [XHARD]? |
|---|---|---|
| B1 ffmpeg | 1.5–2.5 d | **no** — support relaxation + overlay graph is specified; existing fail-closed suite catches over-accept |
| B2 expansion | 0.5–1 d | **no** — pure function + one hook |
| B3 compiler | 1–2 d | **no** — SDK calls with documented keys; temp-project tests |
| B4 e2e | 0.5–1 d | **no** — commands already in the goal |
| **Total** | **4–6 d** | **0 [XHARD] tasks** |

Not a huge run.

**Why A5 is not [XHARD]:** the intro shape is enumerated; `support.py` gates are listed; tests already parametrize unsupported semantics; a mistake that over-accepts is caught by `test_support_fails_closed_for_every_unsupported_semantic`; a mistake that under-accepts fails T4.

**Why A4 is not [XHARD]:** splice arithmetic and the plugin-law loader callback are decided; expansion is unit-testable without sqlite.

If B1's first executor attempt breaks the media-only suite, oracle reworks the brief — do not escalate to [XHARD] for size or one miss.

===== EXPLORATION EVIDENCE (shared) =====
# Exploration evidence (Phase 2, verified 2026-08-28) — shared context for settled-plan wave

Source files: `.oracle/findings/ffmpeg-shots/area1-shots-mount.txt`, `area2-ffmpeg-capabilities.txt`, `area3-render-routing.txt`, `.oracle/findings/reigh-app-shot-structures.md`. Key facts the plan relies on:

1. **Shots mount**: `shots` (id, project_id FK→projects, name, sort_key UNIQUE/project, metadata_json, timestamps) + `shot_items` (id, shot_id FK→shots, media_id FK→media, sort_key, source_frame, metadata_json) — `astrid/packs/shots/migrations/0001_initial.sql:17-37`. ShotsService: create/add_item/remove_item/reorder/list/show, all with idempotency keys; items are media-kind-agnostic, multiple per shot. No post-create metadata update (create hash includes metadata; same key + different request → ReceiptMismatchError).
2. **Plugin law**: shots pack "never FK's to or imports the timeline pack" (`astrid/packs/shots/repository.py:8-10`); conformance test `test_shot_repository_has_no_timeline_dependency` asserts DDL has no `timelines` and `astrid.packs.timeline` not imported.
3. **Clip schema**: `clipType` is an OPEN string (JSON-schema `type: string`; `timeline.schema.json:28-30,431-432`); Python `ClipType` Literal is a type alias, not a runtime enum. Authoring validator keeps unregistered types opaque. Render admission (`managed_timeline.py:86-132`) rejects non-builtin clip types; builtins media|video|image|audio|effect-layer + text alias. `shot` would pass authoring, fail admission → expand before `validate_managed_render_snapshot`.
4. **Text clip shape** (Remotion + fixtures): `clipType: "text"`, `text.{content,fontSize,color,align,bold}`, `params.{anchor,offsetX,offsetY,maxWidth,textShadow,weight}`, `effects.{fade_in,fade_out}` (seconds).
5. **ffmpeg backend** (`astrid/packs/rendering/backends/ffmpeg/`): currently `media_only` (renderer.yaml:14-22), support.py rejects text/hold/effects/overlap/speed/crop/transforms/multi-visual-track; filtergraph in `command.py:build_filter_graph` uses per-clip trim/setpts/scale/pad/fps + `concat=v=1`; audio uses `atrim`+volume+`concat=a=1` with anullsrc gaps (no amix). No ARG_MAX bounds tests.
6. **Render routing** (`astrid/core/rendering/service.py:152-209`): `--backend rendering.ffmpeg` = strict single target → `_unsupported_report` hard-raises if unsupported. Legacy `remotion`/None = ordered pair (ffmpeg, remotion) + auto_route; falls through only on unsupported/binary_missing. No change to auto-route in this run.
7. **Current intro output**: static slides + text overlay + VO, hard cuts; zero animation (fade effects unimplemented in Remotion); fully ffmpeg-replicable (frames md5-identical).
8. **Compiler** (`scripts/build_storyboard.py`): flat 76-clip emitter (vo a1 media, cap captions text, broll broll media, brand brand text); GAP=0.35; VO holds = duration+GAP; no-VO = default_hold; golden test 76 clips / 50 assets / 177.53±0.5; No `--shots` flag today. Image resolution uses `image.path` directly; variants-only golden fixture also exists; `_variant_import_path` helper is dead code.
9. **Kernel render-prep**: `_prepare_managed_render_inputs` (invocation.py:612) → resolve_managed_render_snapshot (managed_timeline.py:235) → validate_managed_render_snapshot (182) → materialize (326, writes as-is). No nested expand anywhere. `timelines show` reports stored doc; slug≠id (id is UUID from (command, project, idempotency)).
10. **reigh-app** (Phase B input only): no nested timelines; PinnedShotGroup = soft-tag {shotId, trackId, clipIds[], mode, videoAssetKey, imageClipSnapshot[]}; EffectLayerSequence = only clip-contains-children pattern. NOT in this run's scope.