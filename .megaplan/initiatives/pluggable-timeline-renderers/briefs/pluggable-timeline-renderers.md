# Brief: Pluggable Timeline Renderers

Status: prepared epic scope reference; no megaplan or chain has been launched.

Execution spec: `../chain.yaml`

North Star: `../NORTHSTAR.md`

This document records the whole-epic architecture and acceptance envelope. The
executable milestone briefs are `m1-renderer-kernel.md` and
`m2-renderer-developer-kit.md`.

## Outcome

Refactor Astrid's timeline rendering path so a trusted pack can contribute a
renderer that handles an entire timeline or selected hybrid segments without
editing Astrid core or the built-in rendering pack. Preserve
`rendering.render` as the stable public facade and preserve the behavior of
existing Remotion, FFmpeg, and hybrid invocations during migration.

A reviewer should be able to install or expose a fixture pack containing a
third renderer, select it by qualified ID, use it beside built-in renderers in
one deterministic render plan, and inspect validated output plus complete
provenance.

A renderer author should be able to scaffold an integration, wrap an existing
local command, pass contract and smoke tests, replay a failed request, and
render a supported timeline without learning Astrid's planner, project ledger,
registry internals, provenance implementation, or FFmpeg finalization path.

## Current state

The implementation is concentrated in
`astrid/packs/rendering/executors/render/run.py`.

- `render()` branches directly on `remotion`, `ffmpeg`, and `hybrid`, and
  rejects other engine values.
- The CLI independently closes `--engine` to those same three values.
- `engine=remotion` currently opportunistically routes eligible media-only
  timelines through FFmpeg.
- Hybrid planning identifies complex windows, emits only `ffmpeg` or
  `remotion` segment labels, renders each temporary timeline through concrete
  functions, and concatenates using FFmpeg.
- Segment concatenation currently hard-codes a 30 FPS normalization rather
  than deriving the output profile from the timeline.
- Remotion-specific serving, props, themes, element registry generation,
  effect asset staging, subprocess execution, cleanup, and provenance live in
  the same module as generic routing.
- FFmpeg support validation, command construction, audit events, and final
  concatenation also live in that module.

Astrid already has useful outer extension machinery:

- Pack discovery and precedence are shared across source, local, extra,
  environment, and installed packs.
- The executor registry discovers pack-provided capabilities and supports
  aliases and overrides.
- `rendering.render` declares backend-neutral timeline and asset-registry
  inputs and a rendered-video output.

The outer abstraction is not consistently honored. In particular,
`astrid/packs/video_editing/orchestrators/iteration_video/run.py` imports and
calls the concrete render module. Inspect all other direct imports, including
the cut and resume paths, before changing routing.

Existing hybrid test coverage is narrow: the provenance test patches the
planner and renderer rather than proving backend discovery, generic dispatch,
media-contract enforcement, or a real mixed-backend plan.

The working tree is already dirty, including relevant changes to
`rendering.render`. Treat all pre-existing modifications as user work. Do not
discard, reset, overwrite, or casually reformat them.

## Scope

### In scope

1. A backend-neutral render request/result and segment-artifact contract.
2. Trusted pack discovery, identity, validation, precedence, aliases, and
   inspection for render backends and finalizers.
3. Extraction of the current Remotion and FFmpeg implementations behind that
   contract without an initial behavior change.
4. A generic render service used by the `rendering.render` CLI/executor.
5. Explicit separation of backend selection, render planning, backend
   execution, segment validation, and final assembly.
6. A deterministic legacy-hybrid planner that preserves today's segment
   boundaries while dispatching by qualified backend ID.
7. A backend-neutral segment media profile covering frame bounds, duration,
   dimensions, FPS/time base, video format, and audio format.
8. Provenance schema evolution for full and segmented renders.
9. Migration of direct callers so registry overrides and installed packs affect
   every supported render entrypoint.
10. A versioned, language-neutral command/JSON request-result protocol, with a
    small optional Python SDK over the same wire contract.
11. A renderer developer kit with scaffold, validate, smoke-test, inspect, and
    replay commands plus committed minimal timeline fixtures.
12. A render context that provides asset materialization, allocated output
    paths, permission-aware subprocess execution, progress/logging,
    cancellation state, media completion/probing, and cleanup.
13. Explicit audio ownership modes: rendered, passthrough, or none, with Astrid
    responsible for final muxing when the renderer does not own audio.
14. Replayable failure bundles containing the request, resolved timeline and
    assets, backend configuration, logs, and partial/result metadata, with an
    opt-in keep-workdir mode.
15. Optional named render-result attachments so future compositors can consume
    alpha, depth, frame sequences, audio stems, or native project files without
    changing the V1 primary-video contract.
16. Unit, contract, integration, compatibility, and renderer-parity tests.
17. Agent-facing and developer-facing documentation for adding, debugging, and
    selecting a renderer backend.

### Out of scope

- Redesigning the timeline schema or embedding executable renderer selection in
  timeline JSON.
- Building a production-quality third renderer; use a deterministic fixture
  backend as the extensibility proof.
- Building overlapping layer-level multi-renderer composition. V1 backends own
  complete temporal windows.
- Building a production remote rendering service. The protocol and execution
  model remains synchronous in V1. Submit/status/cancel/resume is a future
  versioned protocol extension, not an implicit V1 requirement.
- Rewriting the Remotion composition or element system.
- Expanding FFmpeg feature support beyond what contract extraction or segment
  normalization requires.
- Replacing FFmpeg as the first shipped finalizer implementation.
- Changing unrelated executor, orchestrator, project, or pack behavior.
- Publishing, deployment, or cloud execution.

## Locked decisions

1. **Backend, planner, and finalizer are distinct concepts.** `hybrid` is a
   planning policy, not a renderer backend.
2. **The timeline remains backend-neutral.** Renderer selection is invocation
   or plan configuration, never an arbitrary module path stored in timeline
   data.
3. **Backends have qualified IDs.** Built-ins should resolve canonically as
   names such as `rendering.remotion` and `rendering.ffmpeg`; short legacy names
   remain compatibility aliases.
4. **Only trusted discovered packs contribute implementations.** Reuse existing
   pack permission, precedence, conflict, alias, and override semantics. Do not
   accept arbitrary CLI import strings.
5. **`rendering.render` remains the stable facade.** Existing pipelines should
   not need to know how a backend is loaded or invoked.
6. **Selection is deterministic and inspectable.** A render plan records the
   selected backend for every segment plus the capability evidence and reason.
7. **Unsupported requests fail closed by default.** Fallback occurs only when
   an explicit planner policy or ordered fallback list permits it.
8. **Every backend returns a validated artifact.** Finalizers consume declared
   media metadata rather than assuming that arbitrary MP4 files are compatible.
9. **Final assembly is explicit.** Ship an FFmpeg finalizer first, but keep
   finalization behind a contract so arbitrary backends do not become secretly
   coupled to inlined FFmpeg logic.
10. **Compatibility precedes semantic cleanup.** Preserve current
    `engine=remotion`, `engine=ffmpeg`, and `engine=hybrid` behavior during the
    initial rollout. A later deprecation may make explicit Remotion strict and
    move opportunistic selection to `planner=auto`.
11. **Provenance has core-owned keys and backend-owned fragments.** Backend
    fragments cannot overwrite core identity, routing, input, segment, or
    finalizer fields.
12. **No concrete backend imports outside the rendering implementation.**
    External callers use the capability runner or one public render service.
13. **The canonical interoperability boundary is language-neutral.** A
    versioned command/JSON request-result protocol is the source of truth;
    Python SDK types and helpers wrap it rather than replacing it.
14. **Developer complexity is progressive.** The minimum local synchronous
    renderer implements one render operation. Request-sensitive support and
    custom finalizers are optional layers exposed only when needed.
    Asynchronous remote jobs are explicitly deferred beyond V1.
15. **Astrid owns plumbing.** Core services own asset resolution, temporary
    workspace allocation, output probing and normalization, audio
    passthrough/muxing, hashes, core provenance, cleanup, and replay metadata.
    Backend authors return media plus a namespaced provenance fragment.
16. **Static capabilities are coarse discovery hints, not the final verdict.**
    A request-sensitive support probe returns structured supported/unsupported
    features, reasons, and alternatives.
17. **Failures are replayable.** Every failed backend invocation can retain or
    emit a self-contained request bundle and exact replay command without
    rerunning the editorial pipeline.
18. **Primary video is required; attachments are extensible.** V1 planners and
    finalizers operate on a validated primary video. Optional named attachments
    are preserved in results and provenance but need not be interpreted by the
    default finalizer.

## Open questions for the planner

Resolve these from the existing layering and record the decisions before
execution:

1. Should renderer implementations be ordinary executor capabilities selected
   through the existing executor registry, or a rendering-specific pack
   extension that reuses shared discovery primitives? Prefer the option that
   avoids a parallel plugin system while keeping nested execution and output
   handling coherent.
2. If ordinary executors are used, how should `rendering.render` invoke child
   backends without creating incorrect nested project runs, duplicate ledger
   ownership, or CLI recursion?
3. What is the smallest manifest metadata/schema that expresses support for
   clip types, track types, overlays, transitions, speed changes, audio mixing,
   window rendering, and output profiles without predicting every future
   renderer feature?
4. Should backend-specific configuration be a scoped mapping keyed by backend
   ID, typed executor inputs, or both? It must not leak Remotion fields into the
   core request.
5. Which provenance-v1 fields must remain top-level for current consumers, and
   which can move into a namespaced Remotion fragment in schema v2?
6. What is the exact compatibility mapping for today's surprising
   `engine=remotion` auto-FFmpeg path, and what warning/deprecation path would
   eventually make explicit backend selection strict?
7. Which existing renderer-parity fixtures are authoritative enough to gate
   extraction, and where command/provenance parity is a better assertion than
   byte-for-byte video parity?
8. What is the smallest useful `RenderContext` surface, and which services
   belong in the Python SDK versus the language-neutral host protocol?
9. How should local-path, local-URL, cached, and remote-upload asset needs be
   represented so simple local renderers stay trivial while remote adapters do
   not reimplement asset staging?
10. Which renderer developer verbs belong under a new `astrid renderers`
    surface, and which should reuse generic capability list/inspect/validate
    behavior internally?

Do not reopen the locked decisions merely because multiple implementation
shapes are possible.

## Constraints

- Python remains compatible with the repository's supported versions.
- Preserve current pack loading priority, alias, override, permission, and
  error-envelope behavior.
- Backends may use subprocesses or remote services only through permissions
  declared by their owning pack.
- A renderer must not need Python. Node, Rust, Blender Python, Unreal tooling,
  shell commands, and remote-service wrappers must be able to implement the
  same wire protocol.
- Renderer discovery and inspection must not import or execute untrusted code
  merely to list metadata.
- Keep temporary files and cleanup ownership explicit on success and failure.
- Derive frame boundaries and output FPS from the canonical timeline canvas.
- Validate segment duration and audio/video presence before final assembly.
- Errors must name the backend, unsupported features, available alternatives,
  and a concrete recovery action.
- Preserve audit lineage from source timeline and assets through segments to
  the final render.
- Keep the required manifest concise. Optional capability or runtime fields
  must have defaults or appear only when the renderer uses that feature.
- Do not force visual-only renderers to synthesize audio.
- Compatible segment outputs should pass through without re-encoding; the
  finalizer records all normalization it performs.
- Backend configuration is namespaced by qualified backend ID and must not add
  backend-specific fields to core render contracts.
- Work around unrelated dirty-tree changes; do not fold them into this work.
- Prefer additive contracts and compatibility translation before removing
  legacy branches.

## Expected implementation shape

The planner may adjust filenames after inspecting current boundaries, but the
plan should account for these surfaces:

- New backend-neutral contract, errors, planning, registry/discovery, service,
  segment validation, and provenance modules, likely under
  `astrid/core/rendering/`.
- A public developer SDK surface, likely `astrid/sdk/rendering.py`, wrapping the
  exact request/result wire protocol and exposing helpers analogous to
  `RenderRequest`, `RenderContext`, `SupportReport`, and `VideoArtifact`.
- A renderer CLI surface for `create`, `list`, `inspect`, `validate`, `smoke`,
  and `replay`, implemented over shared capability discovery rather than a
  disconnected registry.
- Built-in implementations extracted under the rendering pack, likely
  `astrid/packs/rendering/backends/` and
  `astrid/packs/rendering/finalizers/`.
- A thin
  `astrid/packs/rendering/executors/render/run.py` facade with compatibility
  argument translation.
- Rendering pack manifest declarations and any shared pack schema/permission
  changes required by the chosen discovery representation.
- Migration of `iteration_video`, hype, cut, resume, and any other concrete
  render imports found by repository search.
- Dedicated core contract/discovery/planner/segment/provenance tests, a fixture
  third-party pack, raw-wire and Python-SDK conformance fixtures, replay-bundle
  tests, and extensions to the existing Remotion and parity suites.
- Committed minimal renderer fixtures that do not require the full editorial
  pipeline or heavyweight optional dependencies.
- Updates to the rendering skill, renderer `STAGE.md`, pack-authoring guidance,
  renderer-authoring quickstart, protocol reference, debugging guide, and
  compatibility notes.

## Required sequencing

1. M1 freezes the wire and kernel contracts, discovery representation,
   compatibility mapping, media/audio ownership, and provenance ownership.
2. M1 adds trusted discovery plus a raw-command fixture and core conformance
   tests.
3. M1 extracts Remotion, FFmpeg, and FFmpeg finalization behind the contracts
   without an initial routing behavior change.
4. M1 switches the facade to generic single-backend routing, ports hybrid
   planning, migrates callers, and closes parity/provenance/source-search gates.
5. M1 hands the frozen protocol reference, fixtures, tests, registrations, and
   generic service to M2.
6. M2 builds the Python SDK and four-file scaffold over the frozen protocol.
7. M2 adds list/inspect/validate/smoke/replay, RenderContext conveniences,
   replay bundles, audio helpers, attachment preservation, and exact CLI tests.
8. M2 completes the renderer-author quickstart and debugging documentation. If
   tooling exposes a kernel-contract defect, stop and revise M1 rather than
   creating SDK-only semantics.

Each step must leave the repository testable. Avoid a flag day where concrete
branches are removed before built-ins are registered and parity-proven.

## Done criteria

1. A fixture pack contributes a renderer without modifying Astrid core or the
   built-in rendering pack.
2. The fixture renderer can render a complete supported timeline through the
   normal `rendering.render` executor.
3. A deterministic mixed plan can assign at least one segment to that fixture
   renderer and other segments to built-in renderers.
4. Planner and dispatcher code contains no concrete Remotion/FFmpeg branches;
   built-in names occur only in registrations, implementations, legacy
   translation, and tests/docs that intentionally name them.
5. Unknown or unsupported backends fail with structured diagnostics and
   available alternatives.
6. Segment artifacts are rejected before assembly when FPS, duration,
   dimensions, codecs, or audio contracts are invalid.
7. The finalizer uses the timeline's real FPS and records any normalization.
8. Full Remotion, FFmpeg-only, legacy hybrid, and third-party renders emit one
   valid provenance sidecar with reproducible backend resolution.
9. Existing `engine=remotion`, `engine=ffmpeg`, and `engine=hybrid` CLI and
   executor workflows pass compatibility tests.
10. Executor aliases/overrides and installed pack discovery affect all render
    entrypoints; no supported caller bypasses the abstraction.
11. Remotion registry generation, theme handling, asset serving, effect asset
    staging, cleanup, audit lineage, and error reporting remain covered.
12. Relevant Python tests, renderer parity tests, and Remotion typechecking
    pass, with dependency-based skips documented rather than silently ignored.
13. Pack-authoring documentation contains a minimal third-renderer example and
    describes permissions, capabilities, selection, output contracts,
    provenance, and failure behavior.
14. The scaffolded local-renderer golden path requires only a concise manifest
    and one render implementation; it does not require custom registry,
    planner, project-ledger, provenance, cleanup, or finalization code.
15. Both a raw command/JSON renderer and a Python-SDK renderer pass the same
    contract fixtures.
16. `astrid renderers validate`, `smoke`, and `replay` provide actionable,
    backend-qualified diagnostics and do not require running the editorial
    pipeline.
17. A visual-only fixture proves `audio=passthrough` or `audio=none` without
    synthesizing an audio track inside the renderer.
18. A failed fixture render produces or preserves a replay bundle containing
    the resolved request, inputs, configuration, logs, partial result, and exact
    replay command.
19. A synthetic request-sensitive backend explains unsupported features and
    planner alternatives rather than returning a bare boolean or exception.
20. Optional result attachments survive validation, finalization, and
    provenance even when the default finalizer ignores their content.
21. Developer documentation demonstrates the path from scaffold to first
    successful render, keeps advanced support probing and custom finalization
    in separate progressive sections, and labels asynchronous jobs as deferred
    beyond V1.

## Epic decomposition and handoff

M1 freezes and implements the renderer-kernel boundary. Its durable handoff to
M2 is:

- the versioned request/result and segment-artifact schemas;
- the backend/planner/finalizer discovery and invocation contract;
- a raw-command fixture renderer and conformance tests;
- extracted Remotion and FFmpeg built-ins using the same boundary;
- a contract reference under `docs/contracts/`.

M2 may improve ergonomics around that contract but must not silently change it.
If M2 discovers a contract defect, the chain stops and M1 is amended and
re-reviewed rather than introducing an SDK-only semantic fork.

## Planning and review focus

The highest-risk failure is architectural success in the main CLI while a
direct caller or pack override still bypasses the registry. Critique and review
must therefore inspect import topology, registry precedence, nested execution
semantics, failure cleanup, and provenance consumers—not only the happy-path
fixture test.

Require the finalized megaplan to group work into independently reviewable
contract/discovery, built-in extraction, generic routing/hybrid, and
migration/verification commits or tasks. Do not permit a single monolithic
rewrite task.
