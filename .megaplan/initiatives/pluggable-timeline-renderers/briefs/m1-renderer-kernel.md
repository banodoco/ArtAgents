# Milestone M1: Renderer Kernel and Built-ins

## Outcome

Deliver the backend-neutral renderer kernel that lets trusted packs contribute
full-timeline or temporal-segment renderers through a versioned synchronous
command protocol. Move Remotion, FFmpeg, hybrid planning, and final assembly
behind the same contracts while preserving the public `rendering.render`
facade and legacy behavior.

The durable handoff to M2 is a frozen request/result contract, raw-command
fixture renderer, conformance suite, and contract reference that developer
tooling can wrap without redefining semantics.

## Scope

- Define backend, planner, finalizer, request, support-report, render-plan,
  segment-artifact, render-result, error, and provenance contracts.
- Decide whether implementations are filtered ordinary executor capabilities
  or a rendering-specific pack extension reusing shared discovery. Avoid a
  parallel plugin system and preserve pack permissions, precedence, aliases,
  and overrides.
- Define a versioned, language-neutral, synchronous command/JSON protocol.
- Discover and inspect trusted backend metadata without importing executable
  code.
- Extract Remotion rendering, FFmpeg media rendering, and FFmpeg finalization
  from the current monolithic executor.
- Replace concrete single-backend and hybrid branches with registry dispatch.
- Port current hybrid heuristics as a deterministic legacy planner using
  qualified backend IDs.
- Validate frame bounds, duration, dimensions, FPS/time base, video format,
  audio format, and output existence before finalization.
- Derive finalizer FPS from the timeline and avoid re-encoding already
  compatible artifacts where practical.
- Evolve provenance to record requested/resolved policy, backend identity and
  source pack, support decisions, segments, hashes, normalization, and
  finalizer.
- Migrate every supported direct caller to the public facade/service.
- Add a deterministic raw-command fixture backend and core contract,
  discovery, routing, hybrid, cleanup, failure, provenance, compatibility, and
  parity tests.
- Write the V1 contract reference consumed by M2.

## Locked decisions

- Backend, planner, and finalizer are separate.
- `hybrid` is a planner policy, not a backend.
- The timeline stays renderer-neutral.
- Backend IDs are qualified; legacy short engine names remain aliases.
- Unsupported requests fail closed unless an explicit planner fallback permits
  another backend.
- A backend owns complete pixels for its assigned temporal window.
- Every successful backend returns a validated primary video artifact.
- Result attachments are optional, named, preserved in provenance, and ignored
  safely by finalizers that do not understand them.
- Final assembly is an explicit contract; FFmpeg is only the first built-in
  finalizer.
- V1 execution is synchronous. Asynchronous remote-job semantics are deferred
  to a future protocol version.
- Preserve current `engine=remotion`, `engine=ffmpeg`, and `engine=hybrid`
  behavior during migration.
- Only trusted discovered packs can contribute executable implementations; no
  arbitrary CLI or timeline import paths.

## Open questions

- Ordinary executor capability versus rendering-specific pack extension.
- Nested execution and project-ledger ownership if ordinary executors are used.
- Minimal static capability vocabulary plus request-sensitive support probing.
- Namespaced backend configuration representation.
- Provenance-v1 compatibility fields and v2 namespace ownership.
- Exact compatibility mapping for the existing nominal-Remotion auto-FFmpeg
  optimization.
- Authoritative renderer parity fixtures and acceptable command/provenance
  parity where byte parity is unstable.

Resolve and document these before extraction. Do not reopen the locked
decisions.

## Constraints

- Preserve unrelated dirty-tree work.
- Keep pack discovery and error-envelope behavior consistent with Astrid core.
- Discovery/listing must not execute backend code.
- Maintain Remotion theme resolution, HTTP Range serving, element registry
  generation, effect asset staging, cleanup, audit lineage, and diagnostics.
- Maintain FFmpeg's current supported-timeline behavior; feature expansion is
  not part of M1.
- Visual-only backends are valid; audio ownership metadata must distinguish
  rendered, passthrough, and none even if M2 supplies ergonomic helpers.
- Backend-specific data remains namespaced and cannot pollute core schemas.
- No layer-level overlapping compositor.
- No production third-party or remote renderer.

## Touchpoints

- `astrid/packs/rendering/executors/render/run.py`
- `astrid/packs/rendering/executors/render/executor.yaml`
- `astrid/packs/rendering/pack.yaml`
- New renderer-kernel modules, likely under `astrid/core/rendering/`
- New built-in backend/finalizer modules under `astrid/packs/rendering/`
- Shared pack schema, discovery, permission, executor, or capability modules
  selected by the architecture decision
- Direct callers under `astrid/packs/video_editing/`
- Existing rendering, timeline, executor-registry, pack, and parity tests
- New `docs/contracts/render-backend-v1.md`

## Anti-scope

- Python SDK and `RenderContext` ergonomics
- Scaffold, smoke, and replay developer commands
- Production remote/asynchronous execution
- Layer/depth/matte composition
- New Remotion elements or timeline features
- Unrelated pack or runner refactors

## Done criteria

1. A fixture pack registers a raw command/JSON renderer without Astrid source
   edits.
2. The fixture renders a complete supported timeline through
   `rendering.render`.
3. A mixed plan assigns at least one window to the fixture and other windows to
   built-ins.
4. Planner and dispatch code contains no concrete backend branches outside
   built-in registration, legacy translation, and intentional tests/docs.
5. Unknown and unsupported backends return structured feature diagnostics and
   available alternatives.
6. Invalid duration, FPS, dimensions, video, or audio artifacts fail before
   final assembly.
7. Full Remotion, FFmpeg-only, legacy hybrid, and fixture renders emit valid
   reproducible provenance.
8. Existing engine invocations pass compatibility tests.
9. Installed pack discovery, aliases, and overrides affect every render
   entrypoint.
10. Optional attachments survive validation/finalization/provenance without
    requiring the default finalizer to understand them.
11. Remotion/FFmpeg parity, cleanup, audit, error, and typecheck gates pass.
12. `docs/contracts/render-backend-v1.md` completely specifies the wire schema,
    lifecycle, media/audio contract, discovery metadata, support reporting,
    errors, attachments, finalization, provenance ownership, and versioning.

## Handoff evidence

M2 must be able to cite:

- `docs/contracts/render-backend-v1.md`
- committed request/result JSON fixtures;
- the raw-command fixture renderer;
- passing core renderer conformance tests;
- the built-in backend registrations and generic service entrypoint.
