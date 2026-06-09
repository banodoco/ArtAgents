# Astrid <-> Reigh Sprint 08 Integration Contracts

This document pins the cross-repo contracts Astrid must follow while wiring
into Reigh's bidirectional timeline editing platform.

## Current Workspace Boundary

This Astrid checkout does not include the companion trees that own the live
Supabase SQL/RPC and canonical web-app write path:

- `reigh-app/`
- top-level `supabase/migrations/`

Because those trees are absent here, this document serves two roles:

1. It records previously verified cross-repo evidence and target contracts that
   Astrid must match.
2. It marks which deliverables are deferred companion work and therefore cannot
   be re-proven inside this repo alone.

For Milestone 6a, the active cleanup surface is the live Astrid runtime/spec/
doc/test tree plus this document and
`docs/architecture/timeline-event-sourcing/m6a-astrid-supabase-contract.md`.
Historical milestone records are archival exceptions. The only allowed
remaining wording-audit exceptions are:

- `docs/architecture/timeline-event-sourcing/m1-schema.md`
- `docs/architecture/timeline-event-sourcing/m2-clip-primitives.md`
- `docs/architecture/timeline-event-sourcing/m3-secondary-primitives.md`
- `docs/architecture/timeline-event-sourcing/m5-concurrency.md`
- `docs/architecture/timeline-event-sourcing/m6-reigh-sync.md`
- `docs/architecture/timeline-event-sourcing/chain.yaml`

Deferred companion work, which is named here but not claimed as complete in
this repo, includes:

- creating `public.timeline_events`
- implementing and granting `append_timeline_event(...)`
- migrating canonical `reigh-app` timeline writes, subscriptions, and history
- proving live server-side hashing, idempotency, rate limiting, RLS, and actor
  validation against the real database/RPC path

## Source Evidence

### Reigh Worker Orchestrator

- `/Users/peteromalley/Documents/reigh-workspace/reigh-worker-orchestrator/api_orchestrator/handlers/banodoco.py`
  - The module routes work to a `banodoco` worker pool and says the worker
    writes via `update_timeline_config_versioned`: lines 1-7.
  - Required SD-034 fields include `expected_version`, `correlation_id`, and
    `user_jwt`: lines 9-16 and 83-92.
  - The pool constant is `BANODOCO_POOL = "banodoco"`: line 48.
  - Claimable pool task types include `banodoco_timeline_generate`: lines 50-59.
  - Worker-unavailable timeout defaults to 30 seconds and is configurable with
    `BANODOCO_WORKER_UNAVAILABLE_TIMEOUT_SEC`: lines 25-28 and 61-64.
  - `is_worker_pool_available` applies the timeout and logs unavailability:
    lines 187-214.

### Reference Banodoco Worker

- `/Users/peteromalley/Documents/banodoco-workspace/banodoco-worker/worker.py`
  - Claim POST uses service-role auth and body fields `worker_id`, `run_type`,
    `worker_pool`, and `task_types`: lines 88-110.
  - The current reference claims both `banodoco_timeline_generate` and
    `banodoco_render_timeline`; Astrid' Sprint 08 worker side is scoped to
    `banodoco_timeline_generate`: lines 93-103 and 177-202.
  - Claimed tasks return `task_id`, `params`, `task_type`, and `project_id`:
    lines 181-200.
  - The generate task requires `correlation_id`, `timeline_id`, `project_id`,
    integer `expected_version`, and `user_jwt`: lines 205-230.
  - `user_jwt` is verified before work begins: lines 232-245.
  - Project ownership is a separate service-role read of `projects.user_id`,
    not a JWT claim: lines 247-271 and 335-350.
  - Pipeline execution and strict timeline validation happen before writing:
    lines 273-292.
  - Versioned write reports Title Case `Complete` or `Failed`: lines 294-332.

- `/Users/peteromalley/Documents/banodoco-workspace/banodoco-worker/worker_writes.py`
  - Writes use `update_timeline_config_versioned` through a service-role
    Supabase client, with JWT user id retained only for audit: lines 1-19 and
    174-197.
  - The write retry helper stamps and compares `correlation_id` for retry
    idempotency: lines 64-90 and 94-166.
  - Production RPC params are exactly `p_timeline_id`, `p_expected_version`,
    and `p_config` in the Reigh migration. The reference also contains an
    optional `p_audited_user_id` path at lines 211-214, but the current Reigh
    RPC signature does not accept that fourth arg, so Astrid must not send it.
    See lines 199-218 here and the migration lines 4-25 below.

- `/Users/peteromalley/Documents/banodoco-workspace/banodoco-worker/worker_jwt.py`
  - JWKS verification is the primary path and service-role fallback is
    documented but not the success path: lines 1-17.
  - JWKS URL resolution uses `REIGH_SUPABASE_JWKS_URL` or
    `{REIGH_SUPABASE_URL}/auth/v1/.well-known/jwks.json`: lines 55-64.
  - Successful verification checks signature, audience, expiry, and `sub`, then
    returns `VerifiedJwt(user_id, audience, raw_claims)`: lines 94-157.
  - The service-role fallback is separate and only checks token identity via
    `/auth/v1/user`: lines 160-204.

- `/Users/peteromalley/Documents/banodoco-workspace/banodoco-worker/worker_assets.py`
  - Asset registry entries may be HTTP URLs, storage keys, or local files:
    lines 1-11 and 165-229.
  - The default storage bucket is `timeline-assets`: line 46.
  - Storage downloads use service-role against Supabase storage REST:
    lines 117-145.
  - Registry resolution writes resolved `file` URLs into a copied registry:
    lines 232-268.

- `/Users/peteromalley/Documents/banodoco-workspace/banodoco-worker/worker_pipeline.py`
  - Generate tasks call the existing pipeline with `intent`, `brief_inputs`,
    `theme_id`, and optional `current_timeline`: lines 53-83.
  - The pipeline output is read from `hype.timeline.json`: lines 114-127.
  - Strict validation uses `banodoco_timeline_schema.validate_timeline`:
    lines 146-163.

- `/Users/peteromalley/Documents/banodoco-workspace/banodoco-worker/worker_remotion.py`
  - Render props are `{timeline, assets, theme}`: lines 13-25 and 113-124.
  - The Remotion composition id defaults to `TimelineComposition`: lines 78-88.
  - Rendering shells to `npx remotion render` and returns output path + sha256:
    lines 126-176.

- `/Users/peteromalley/Documents/banodoco-workspace/banodoco-worker/worker_health.py`
  - `/healthz` reports readiness gates: lines 1-8 and 43-59.
  - Readiness checks schema/theme and shared pipeline imports: lines 62-92.

### Reigh Edge Functions and Database

- `/Users/peteromalley/Documents/reigh-workspace/reigh-app/supabase/functions/claim-next-task/index.ts`
  - POST body supports `run_type: "banodoco-worker"`, `worker_pool`, and
    `task_types`: lines 21-33 and 56-73.
  - Service-role claim path maps `banodoco-worker` to dedicated pool filtering
    through `p_worker_pool` and `p_task_types`: lines 94-127.
  - The task response body contains `task_id`, `params`, `task_type`, and
    `project_id`: lines 181-200.
  - Verified commits: `f8599a887 fix(edge): claim-next-task supports
    worker_pool + banodoco-worker run_type`.

- `/Users/peteromalley/Documents/reigh-workspace/reigh-app/supabase/functions/task-status/index.ts`
  - GET accepts `?task_id=<uuid>` and JWT or service-role auth, and returns the
    poller-facing shape with optional `correlation_id`, `message`,
    `failure_code`, and `result`: lines 9-26.
  - Ownership is enforced before reading task status: lines 39-74.
  - Verified commits: `ee2e6f10c fix(edge): wire task-status GET endpoint for
    banodoco worker polling`.

- `/Users/peteromalley/Documents/reigh-workspace/reigh-app/supabase/functions/task-status/handler.ts`
  - Reads `tasks.id, status, result_data`: lines 52-66.
  - Hoists `correlation_id`, `message`, and `failure_code` from `result_data`
    and forwards remaining keys as `result`: lines 68-91.

- `/Users/peteromalley/Documents/reigh-workspace/reigh-app/supabase/functions/update-task-status/index.ts`
  - POST requires auth and accepts JWT user auth: lines 16-26.
  - It authorizes the task actor, validates transitions, builds a payload, and
    updates by role: lines 53-119.
  - Success response echoes `task_id` and Title Case `status`: lines 149-185.

- `/Users/peteromalley/Documents/reigh-workspace/reigh-app/supabase/functions/update-task-status/types.ts`
  - Allowed statuses are exactly `Queued`, `In Progress`, `Complete`, `Failed`,
    and `Cancelled`: lines 1-3.
  - `result_data` is an optional worker envelope persisted to `tasks.result_data`:
    lines 5-20.

- `/Users/peteromalley/Documents/reigh-workspace/reigh-app/supabase/functions/update-task-status/request.ts`
  - Requests require `task_id` and a valid status: lines 50-72.
  - `result_data` must be a JSON object when present and is passed through:
    lines 125-149.

- `/Users/peteromalley/Documents/reigh-workspace/reigh-app/supabase/functions/update-task-status/payload.ts`
  - `result_data` is written only when explicitly present: lines 38-45.

- `/Users/peteromalley/Documents/reigh-workspace/reigh-app/supabase/functions/update-task-status/transitions.ts`
  - Title Case status transitions are the only accepted transition graph:
    lines 1-20.

- `/Users/peteromalley/Documents/reigh-workspace/reigh-app/supabase/functions/reigh-data-fetch/index.ts`
  - `TIMELINES_SELECT` currently omits `config_version`, so T2 must add it:
    line 80.
  - Timeline reads select `TIMELINES_SELECT` from `timelines` by `project_id`
    and optional `timeline_id`: lines 555-569.
  - Non-service callers must pass project ownership verification before data is
    returned: lines 588-613.
  - Response returns `timelines` at top-level and under `data`: lines 725-787.

- `/Users/peteromalley/Documents/reigh-workspace/reigh-app/supabase/migrations/20260326100000_add_timeline_config_version.sql`
  - Adds `timelines.config_version`: lines 1-2.
  - Defines `update_timeline_config_versioned(p_timeline_id, p_expected_version,
    p_config)` with exactly three parameters and optimistic version matching:
    lines 4-22.
  - Grants execute to `authenticated` and `service_role`: lines 24-25.

### Reigh Editor Data Provider

- `/Users/peteromalley/Documents/reigh-workspace/reigh-app/src/tools/video-editor/data/DataProvider.ts`
  - Canonical interface includes `loadTimeline`, `saveTimeline`,
    `loadAssetRegistry`, `resolveAssetUrl`, optional `registerAsset`,
    `uploadAsset`, `saveCheckpoint`, `loadCheckpoints`, `loadWaveform`, and
    `loadAssetProfile`: lines 53-71.
  - There is no `save_waveform`, `save_profile`, or `load_profile` equivalent:
    lines 53-71.

- `/Users/peteromalley/Documents/reigh-workspace/reigh-app/src/tools/video-editor/data/SupabaseDataProvider.ts`
  - `loadTimeline` reads `config, config_version` and validates serialized
    timeline config: lines 51-71.
  - `saveTimeline` validates the config and calls either
    `update_timeline_config_versioned` or `update_timeline_versioned` depending
    on whether a registry is supplied: lines 74-110.
  - Asset registry load and URL resolution use `timelines.asset_registry` and
    the `timeline-assets` bucket: lines 192-224.
  - Uploads use storage path `${userId}/${timelineId}/${Date.now()}-${filename}`
    in `timeline-assets`, then `registerAsset`: lines 244-270.
  - `loadWaveform` and `loadAssetProfile` are stubs returning null: lines
    273-279.

- `/Users/peteromalley/Documents/reigh-workspace/reigh-app/src/tools/video-editor/data/AssetResolver.ts`
  - This file does not exist in the current `main` checkout or in
    `sprint-8-themed-render-via-orchestrator` (`git ls-tree` found only
    `DataProvider.ts` and `SupabaseDataProvider.ts` under this directory).
    The callable asset-resolution contract is therefore the `DataProvider`
    `resolveAssetUrl` method and the `SupabaseDataProvider` implementation
    cited above.

### Shared Banodoco Packages

- `/Users/peteromalley/Documents/banodoco-workspace/packages/timeline-ops/package.json`
  - Package name is `@banodoco/timeline-ops`, private, ESM, with package root
    exports pointing at `typescript/dist/src/index.js`: lines 1-18.
  - It depends on `@banodoco/timeline-schema` through a package-root file dep:
    lines 24-26.

- `/Users/peteromalley/Documents/banodoco-workspace/packages/timeline-ops/typescript/src/index.ts`
  - Source exports direct primitives including `addClip`, `moveClip`, and
    `setTimelineTheme`: lines 1-13.

- `/Users/peteromalley/Documents/banodoco-workspace/packages/timeline-schema/package.json`
  - Package name is `@banodoco/timeline-schema`, private, ESM, with package root
    exports pointing at `typescript/dist/src/index.js`: lines 1-18.

- `/Users/peteromalley/Documents/banodoco-workspace/packages/timeline-schema/typescript/src/index.ts`
  - Source exports schema and theme-resolution surfaces only: lines 1-2.

Important FLAG-014 note: package manifests are at the package roots, while
source files live under `typescript/src/index.ts`. Do not document or import
`packages/timeline-ops/src/index.ts` or `packages/timeline-schema/src/index.ts`;
those paths do not exist.

## Resolved Contracts

### 1. Worker Reception Model

Astrid implements the worker side of Reigh's existing banodoco worker pool.
It should poll `POST /functions/v1/claim-next-task` with:

```json
{
  "worker_id": "<stable worker id>",
  "run_type": "banodoco-worker",
  "worker_pool": "banodoco",
  "task_types": ["banodoco_timeline_generate"]
}
```

The endpoint supports `worker_pool` and `task_types` filtering, and maps
`banodoco-worker` to pool-specific RPC filtering. The reference worker currently
claims render tasks too, but AA's current sprint scope is only timeline
generation. AA must defensively reject any claimed task whose `task_type` is not
`banodoco_timeline_generate`.

### 2. JWT Authorization and Service-Role Write Split

`user_jwt` is an authorization input, not the DB write credential. AA must:

1. Verify `user_jwt` against Reigh Supabase JWKS, checking signature,
   `aud=authenticated`, expiry, and `sub`.
2. Use the verified JWT subject as the actor identity.
3. Perform an explicit service-role read of `projects.user_id` for the task's
   `project_id`, and require it to equal the verified JWT subject.
4. Use service-role only for the trusted worker write path.
5. Call `update_timeline_config_versioned` with exactly:

```json
{
  "p_timeline_id": "<timeline uuid>",
  "p_expected_version": 1,
  "p_config": {}
}
```

Do not pass `project_id` or `p_audited_user_id` to the current Reigh RPC.

### 3. Asset Upload and Resolution Contract

The storage bucket is `timeline-assets`.

Upload path shape is:

```text
${user_id}/${timeline_id}/${epoch_ms}-${filename}
```

The Reigh data provider registers the uploaded asset into the timeline's asset
registry after upload. Worker render resolution accepts HTTP URLs directly, or
downloads storage-key entries from `timeline-assets` using service-role into a
local temp path, then supplies Remotion-friendly `file` URLs.

### 4. Task Status, `result_data`, and Poller Readback

AA must never call `/functions/v1/task-status`; that GET endpoint is for
Reigh's poller. AA must write status through `/functions/v1/update-task-status`
with Title Case statuses only:

```text
Queued | In Progress | Complete | Failed | Cancelled
```

On success, AA writes:

```json
{
  "task_id": "<task uuid>",
  "status": "Complete",
  "result_data": {
    "config_version": 2,
    "correlation_id": "<correlation uuid>",
    "timeline_id": "<timeline uuid>"
  }
}
```

On failure, AA writes `status: "Failed"`, an error field matching the endpoint
contract used by implementation, and at minimum `result_data.correlation_id`.
The new `task-status` GET reads `tasks.result_data`, hoists
`correlation_id/message/failure_code`, and returns other keys under `result`.

### 5. Sequence Schema

Sequence support is deferred for this sprint. Mechanical search found
`SequenceDraft`, `validateSequenceDraft`, and `TRUSTED_SEQUENCE_CLIP_TYPES` in
`reigh-app/src/tools/video-editor/sequences/*`, not in
`@banodoco/timeline-schema`. The local `timeline-schema` package currently
exports only `./schemas.js` and `./resolveTheme.js`. AA should not implement
SequenceDraft support until that sequence module is published or otherwise made
consumable by AA.

## Shared Package Version Strategy

Use root `file:` dependencies in Astrid' root `package.json`:

```json
{
  "dependencies": {
    "@banodoco/timeline-ops": "file:/Users/peteromalley/Documents/banodoco-workspace/packages/timeline-ops",
    "@banodoco/timeline-schema": "file:/Users/peteromalley/Documents/banodoco-workspace/packages/timeline-schema"
  }
}
```

Do not point dependencies at `/typescript` subdirectories. The package root
`package.json` files own `main`, `types`, and `exports`. Source citations and
debugging should use `typescript/src/index.ts`.

## Pack Execution Modes: Managed vs Unmanaged

Every Astrid pack that produces timeline or arrangement state runs in one of
two modes:

### Managed mode (canonical event-sourced writes)

A pack is **managed** when it targets a project-bound canonical timeline
container. In managed mode:

- The pack receives `--project <slug>` and `--timeline-slug <slug>`.
- All timeline mutations go through the `EventLogBackend` selected for that
  timeline; the pack never writes `assembly.json`, `hype.timeline.json`,
  `timelines.config`, or arrangement blobs directly as canonical state.
- Compatibility blobs (derived surfaces) may be refreshed *after* event append,
  only through the projection/helper path.
- Every event carries an actor matching the m1 schema. The proximate writer
  wins; upstream human/agent provenance goes in `actor.via`.

Managed mode is the only path that closes the write-side bypasses targeted
by milestone m3.5. The `astrid timelines audit` command only checks
managed-path mutations; it does not flag compatibility blob writes that
follow an event append.

### Unmanaged mode (file-only artifact generation)

A pack is **unmanaged** when invoked as a standalone file-only tool:

- The pack writes run-local artifacts (e.g., `hype.timeline.json`,
  `hype.assets.json`) without any project or timeline container binding.
- No events are emitted; no canonical event stream exists.
- These runs are intentionally outside the event-sourcing boundary and are
  not subject to the m3.5 write-bypass audit.

This distinction is load-bearing: milestone m3.5 closes managed canonical
write bypasses only. Standalone file-only invocations remain unmanaged
artifact generation and are not required to emit events.

## Audit Scope (m3.5)

The bypass audit for m3.5 covers only **managed pack and worker write paths**:

- `video_editing.cut` with `--project` + `--timeline-slug`
- `editorial.refine` with `--project` + `--timeline-slug`
- `iteration.assemble` with `--project` + `--timeline-slug`
- `video_editing.hype` with `--project` (managed local mutations)
- `open_in_reigh` (cross-boundary bridge)
- `banodoco_worker` write-back

Unmanaged file-only invocations of these packs are not in audit scope.
The following sibling flows remain intentionally out of scope because they
write run-local pipeline artifacts rather than timeline-container state:
`editorial.arrange`, `training.pool_build`, `training.pool_merge`.

## Publish Remote Writes (m6 Scope)

The `builtin.publish` pack currently reads local timeline files (read-only)
and uploads assets + timeline config to Supabase via `submit_import()`. These
remote writes are **not** part of the m3.5 write-bypass migration:

- Publish does not write `assembly.json`, `hype.timeline.json`, arrangement
  blobs, or any other local canonical timeline state.
- The remote Supabase upload path (`submit_import`, asset storage writes) is
  m6 scope and will be migrated to event-based replay when the Supabase RPC
  implementation exists.
- For m3.5, publish is treated as a read-only projection consumer for local
  canonical state. Regression tests in `tests/test_publish.py` enforce this.

## Phase Gates and Follow-On Notes

- T2 must patch `reigh-data-fetch` so `TIMELINES_SELECT` includes
  `config_version`; without it, AA cannot load `expected_version` from the
  read side and Phase 2 cannot validate live optimistic writes.
- T2 PR: https://github.com/banodoco/reigh-app/pull/6. Current recorded state:
  OPEN draft, mergeable=MERGEABLE. Phase 2 DataProvider work remains
  hard-gated on this PR merging; do not work around a missing `config_version`
  read with another endpoint.
- Renderer parity goldens are not present yet; renderer parity tests should
  skip with an explicit reason when goldens are absent.
- Non-worker CLI writes must preserve the SD-009 auth boundary. Prefer PAT or
  user-JWT paths for user-owned authoring flows, reserving service-role for the
  trusted AA worker.
- `open_in_reigh` is the named cross-boundary bridge between LocalFs and
  Supabase. No other pack may invent a LocalFs-to-Supabase blob copy path.
  Post-m6, `open_in_reigh` will use true RPC replay; pre-m6 it stages bridge
  metadata as a compatibility measure.

## Identity Concepts: Navigating the Four Identifiers

Users and developers encounter four distinct timeline-related identifiers.
Each serves a different purpose:

| Concept | Format | Where | Example |
|---|---|---|---|
| **Managed local binding** | `--project <slug>` + `--timeline-slug <slug>` | Child-pack CLI args | `--project my-show --timeline-slug ep01` |
| **Project-run identity** | `run.timeline_id` = 26-char Crockford ULID | `run.json` top-level field | `01JQXYZ...` |
| **Event-stream UUID** | `metadata.timeline_event_stream_id` = RFC 9562 UUID v7 | `run.json` → `metadata` sub-key | `018f4a3c-...` |
| **Remote executor routing** | `--project <uuid>` + `--timeline-id <uuid>` | Executor CLI args (reigh-app UUIDs) | `--project a1b2c3d4-... --timeline-id e5f6a7b8-...` |

- **Managed local binding** — Used by child packs (cut, refine, assemble) in
  managed mode. Tells the pack to write canonical events through the event
  gateway targeting a specific project-timeline container. Both flags must
  be present together or both absent.
- **Project-run identity** — Every run record stores a `timeline_id` ULID.
  This is always a 26-char Crockford ULID, never a UUID. It identifies the
  timeline *container* (directory), not the event stream.
- **Event-stream UUID** — Stored in `run.metadata.timeline_event_stream_id`.
  This is the RFC 9562 UUID v7 from the timeline's `assembly.identity.json`.
  It is the `timeline_id` used by backend append/read operations.
- **Remote executor routing** — Used by the executor CLI (`astrid executor run`)
  in UUID handoff mode. The executor completes locally, emits bridge metadata,
  and does NOT push to Supabase. Actual Supabase replay is deferred to m6
  (`open_in_reigh` bridge).

**Do not confuse these:**
- `--timeline-slug` (child packs) ≠ `--timeline-id` (executor UUID mode).
  Child packs intentionally do NOT accept `--timeline-id` — it is reserved
  for executor UUID routing.
- `run.timeline_id` (ULID container) ≠ `metadata.timeline_event_stream_id`
  (UUID event stream). One is a container ID; the other is the event stream
  identifier.

## Bypass Audit Results (m3.5)

Audit completed against in-scope managed write paths. Every surviving
`save_timeline` / `save_arrangement` call is either:

1. **A compatibility artifact write after managed event emission**
   (event-stream-first, artifact is derived output). Examples:
   - `cut/run.py:1273` — `save_timeline` after `_emit_cut_managed_events()`
   - `refine/run.py:593,626` — `save_arrangement`/`save_timeline` after
     `_emit_refine_managed_events()`
   - `assemble/run.py:187-188` — `save_timeline` after
     `_emit_assemble_managed_events()`
   - `hype/run.py:1366` — `save_arrangement` after gateway event emission

2. **An unmanaged artifact write in run-local pipeline mode** (no project
   or timeline binding exists). Example:
   - `cut/run.py:1059` — `save_timeline` in `write_resume_outputs()` writing
     to a local `out_dir`

No `SupabaseDataProvider.save_timeline()` calls remain on any in-scope
pack or worker write path:
- `open_in_reigh/run.py` — emits bridge metadata only; `save_timeline` call
  removed
- `executor/cli.py` — `_push_run_to_supabase()` removed; UUID handoff
  metadata only
- `banodoco_worker.py` — worker adapter uses `pack_write_gateway`;
  `SupabaseDataProvider` only used for task client operations

`verify_chain()` passes for all managed fixtures (tested via
`test_managed_write_paths.py` and `test_edit_helpers.py`).

The `project/cli.py` `SupabaseDataProvider.save_timeline()` path is the
reigh-app web UI edit surface — out of m3.5 scope (m6).

## M6a Status Note

Within this repo, Supabase event-log work is limited to Astrid-side contract
and transport scaffolding. Live parity with SQL/RPC behavior is deferred until
the owning `reigh-app/` and top-level `supabase/migrations/` trees are mounted
and tested in a companion workspace. Any remaining references in this document
to `update_timeline_config_versioned` describe either legacy compatibility
evidence or current companion-repo behavior, not the final event-first end
state.
