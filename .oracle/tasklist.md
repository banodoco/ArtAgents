# Renderer Tasklist

## Batch 1 — Baseline, contracts, and discovery

**Checkpoint:** The oracle reviews the characterized legacy behavior, all 18 frozen decisions, wire schemas, pack-extension loading, trust eligibility, precedence, aliases, overrides, and compatibility mappings. Batch 2 cannot begin until the oracle returns `PASS`.

**Acceptance criteria:**

- `.oracle/baseline.md` records the dirty-tree snapshot, baseline failures/skips, production callsite inventory, empty Sprint 08 fixture state, all three legacy engines, nominal-Remotion FFmpeg routing, audio specialization, v1 provenance fields, transition units, and standalone versus attached run ownership.
- `docs/contracts/render-backend-v1.md` preserves locked decisions 1–18 from `.megaplan/initiatives/pluggable-timeline-renderers/briefs/pluggable-timeline-renderers.md` and the resolved decisions in `.oracle/plan.md`.
- Python DTOs and versioned JSON fixtures round-trip identically; unknown versions, invalid half-open frame bounds, duplicate attachment names, traversal, and backend attempts to overwrite core fields fail structurally.
- `extensions.rendering` schema and runtime normalization agree exactly; manifests are containment-checked and statically inspectable without importing backend code.
- Renderer, planner, and finalizer registries use `DiscoveredPack.priority_index`; aliases resolve before overrides, ineligible candidates cannot shadow trusted implementations, and executor/orchestrator default registries receive `OverrideStore(project_root)`.
- Active trusted installs, corrupt/mismatched installs, inactive revisions, explicit-extra roots, environment denial, conflicts, cycles, and invalid override targets produce the specified inspectable/executable states.
- `ffmpeg`, `remotion`, qualified built-in IDs, and `hybrid` retain the frozen compatibility meaning; `hybrid` is never registered as a renderer.
- Existing rendering, pack, executor, iteration, Hype, and audio-reactive suites remain at the recorded baseline.

### Tasks

- [ ] **T1.1 — Characterize and record the baseline** Add `.oracle/baseline.md` and `tests/packs/rendering/test_legacy_renderer_characterization.py` covering legacy routing, props/theme/registry/staging/environment behavior, every v1 provenance key, transition units, run ownership, and the complete caller inventory; acceptance: `pytest -q tests/packs/rendering/test_legacy_renderer_characterization.py tests/packs/rendering tests/packs/test_audio_render.py`.
- [ ] **T1.2 — Freeze language-neutral contracts and schemas** Add `astrid/core/rendering/{__init__,contracts,errors,provenance}.py`, `astrid/core/rendering/schemas/v1/*.json`, raw JSON fixtures, and `docs/contracts/render-backend-v1.md` defining `RenderRequest`, `SupportReport`, `RenderPlan`, `FrameWindow`, profiles, audio ownership, artifacts, attachments, results, failures, and provenance v2; acceptance: `pytest -q tests/core/rendering/test_contracts.py tests/core/rendering/test_schema_roundtrip.py`.  [HARD]
- [ ] **T1.3 — Add the exact rendering pack extension** Update `astrid/core/pack/schemas/v1/pack.json`, `permissions.py::_optional_pack_extensions`, `_common.py::{PACK_ALIAS_KINDS,PackAliasKind}`, `alias_resolver.py::extract_pack_aliases`, and `registry.py::pack_rendering_manifest_paths` for renderer/planner/finalizer manifests and aliases; acceptance: `pytest -q tests/packs/test_pack_yaml_schema.py tests/packs/test_pack_rendering_extensions.py tests/test_canonical_aliases.py`.  [HARD]
- [ ] **T1.4 — Build trusted rendering registries** Implement `astrid/core/rendering/registry.py::{RendererRegistry,PlannerRegistry,FinalizerRegistry,load_default_registries}` over `CapabilityRegistry`, `AliasResolver`, `OverrideStore`, `discover_pack_metadata()`, and derived execution eligibility; retrofit `execution/{executor,orchestrator}/registry.py::load_default_registry`; acceptance: `pytest -q tests/core/rendering/test_registry.py tests/test_override.py tests/packs/test_pack_discovery_metadata.py`.  [HARD]
- [ ] **T1.5 — Lock the discovery and eligibility matrix** Add static no-import, precedence, conflict, alias, override, cycle, permission, explicit-extra, active/inactive install, corrupt trust-record, and ineligible-shadowing cases under `tests/core/rendering/test_registry.py` and `tests/fixtures/renderer_packs/discovery/`; acceptance: that test module passes without executing fixture commands.

## Batch 2 — Command protocol and host-owned plumbing

**Checkpoint:** The oracle reviews the complete four-verb transport, raw non-SDK fixture, process cleanup, asset/cache behavior, canonical profile, artifact enforcement, and locked publication protocol. Batch 3 cannot begin until the oracle returns `PASS`.

**Acceptance criteria:**

- Commands execute as `<command> render|support|plan|finalize --request <absolute> --result <absolute>` with `shell=False`, pack-root `cwd`, sanitized environment, absolute paths, binary preflight, timeout, captured logs, and authoritative result-file parsing.
- Missing binaries, nonzero exits, timeout, interruption, absent/malformed results, absent/empty outputs, and incompatible protocol versions map to renderer-qualified structured failures; process groups are terminated and reaped on interruption.
- The raw fixture imports no Astrid SDK, produces a deterministic two-second artifact from generated media, works from an explicit extra root and trusted active install, and never creates `run.json`.
- Asset-cache layout, URL keys, resume/drift metadata, locking, and `EphemeralSession` behavior remain unchanged behind the compatibility wrapper.
- Only invocation-staged assets are served from `127.0.0.1` on port `0`; Range requests work and the server always shuts down, closes, and joins.
- The canonical resolved profile comes from the merged theme/timeline canvas and includes dimensions, rational FPS/time base, codecs, pixel format, audio rate/layout, and duration tolerance.
- Artifact validation rejects missing, empty, escaped, symlinked, hash-mismatched, profile-incompatible, duration-invalid, and audio-ownership-invalid outputs while preserving valid named attachments.
- Publication locks each output, renames the video first, and atomically writes its hashed provenance sidecar last; crash-orphan recovery never treats an incomplete pair as committed.

### Tasks

- [ ] **T2.1 — Implement command transport and process lifecycle** Add `astrid/core/rendering/transport.py::CommandTransport` with four protocol verbs, binary preflight, sanitized subprocess execution, timeouts, process sessions, process-group cleanup, result parsing, and structured failure mapping; acceptance: `pytest -q tests/core/rendering/test_transport.py`.  [HARD]
- [ ] **T2.2 — Add the raw protocol fixture pack** Create `tests/fixtures/renderer_packs/raw_command/{pack.yaml,renderer.yaml,backend.py}` plus versioned text-only and generated-media requests, without committed MP4s or SDK imports; acceptance: `pytest -q tests/core/rendering/test_raw_command_fixture.py tests/packs/test_git_pack_install.py`.
- [ ] **T2.3 — Extract the reusable asset cache** Move reusable code to `astrid/core/rendering/asset_cache.py` while retaining `astrid/packs/training/executors/asset_cache/run.py` as a compatible CLI wrapper; acceptance: `pytest -q tests/test_asset_cache.py tests/test_url_pipeline_smoke.py`.
- [ ] **T2.4 — Implement invocation-scoped asset materialization** Add `astrid/core/rendering/assets.py::{AssetMaterializer,InvocationAssetServer}` and replace `_classify_assets`, `_server_root_for`, and broad-root serving with contained hardlink/copy staging, remote-URL preservation, Range support, and deterministic cleanup; acceptance: `pytest -q tests/core/rendering/test_assets.py`.  [HARD]
- [ ] **T2.5 — Resolve profiles and validate artifacts** Add `astrid/core/rendering/{profile,artifacts}.py::{resolve_render_profile,validate_render_result}`, extend `astrid/core/media.py` probing fields, and cover audio ownership, attachments, hashes, duration, containment, and profile checks; acceptance: `pytest -q tests/core/rendering/test_profile.py tests/core/rendering/test_artifacts.py tests/core/util/test_media.py`.  [HARD]
- [ ] **T2.6 — Add locked video-plus-sidecar publication** Implement `astrid/core/rendering/publication.py::publish_render_result` with per-output locking, atomic sidecar commit marking, conservative previous-output handling, and orphan recovery; acceptance: `pytest -q tests/core/rendering/test_publication.py`.  [HARD]

## Batch 3 — Built-in renderer and finalizer extraction

**Checkpoint:** The oracle reviews the Remotion, FFmpeg, and FFmpeg-finalizer implementations behind the shared manifests and wire protocol, including concurrency, strict support diagnostics, audio semantics, real FFmpeg output, and facade compatibility. Batch 4 cannot begin until the oracle returns `PASS`.

**Acceptance criteria:**

- `rendering.remotion`, `rendering.ffmpeg`, and `rendering.ffmpeg-finalizer` are statically registered through `astrid/packs/rendering/pack.yaml` and their manifests.
- Remotion preserves `TimelineComposition`, merged themes, props, registry state/hashes, source-pack and effect lineage, effect staging, sanitized environment, cleanup, and output validation.
- One non-recursive cross-process lock spans registry-state reads, all registry/shim/theme-pointer writes, active-theme selection, the complete Remotion render, and the `gen-types` writer path.
- Strict FFmpeg support fails closed for unknown kinds, invalid bounds, visual gaps/overlaps, speed, transforms, crop, effects, transitions, opacity, discarded visual audio, overlapping audio, fades, missing streams, and missing binaries.
- FFmpeg implements exact track-volume × clip-volume gain, track mute, clip `volume: 0`, supported sequential audio mixing, stream-copy behavior, and explicit audio ownership without renderer-synthesized silence.
- The finalizer probes every segment, stream-copies only complete profile matches, otherwise normalizes dimensions, rational FPS/time base, codecs, pixel format, audio rate/layout/presence, and records each normalization.
- Existing compatibility tests, Remotion typecheck, an available Remotion fixture render, and a real FFmpeg render pass.

### Tasks

- [ ] **T3.1 — Extract `rendering.remotion`** Move Remotion helpers from `executors/render/run.py` into `astrid/packs/rendering/backends/remotion/`, add `renderer.yaml` and the raw-command adapter, and relocate private-helper tests while retaining a thin facade suite; acceptance: `pytest -q tests/packs/rendering/test_remotion_backend.py tests/packs/rendering/test_remotion_render_contract.py`.  [HARD]
- [ ] **T3.2 — Enforce the Remotion outer lock** Add `backends/remotion/lock.py::remotion_render_lock`, route registry generation and full renders through it, and update `scripts/gen_effect_registry.py`, `scripts/gen_remotion_types.py`, and `remotion/package.json` so `gen-types` uses the same non-recursive writer entrypoint; acceptance: `pytest -q tests/packs/rendering/test_remotion_locking.py tests/packs/rendering/test_render_remotion_registry.py`.  [HARD]
- [ ] **T3.3 — Extract the FFmpeg backend and pure builders** Move media rendering and `audio_reactive_colour.py` into `astrid/packs/rendering/backends/ffmpeg/`, add `renderer.yaml`, and expose pure support/command/filter builders; acceptance: `pytest -q tests/packs/rendering/test_ffmpeg_backend.py tests/packs/rendering/test_audio_reactive_colour.py`.  [HARD]
- [ ] **T3.4 — Implement strict FFmpeg support and audio semantics** Implement `backends/ffmpeg/support.py::support` and exact gain/mute/source-bound/stream/fade/transform rejection rules with request-sensitive optimization and specialization evidence; acceptance: `pytest -q tests/packs/rendering/test_ffmpeg_support.py tests/packs/test_audio_render.py`.  [HARD]
- [ ] **T3.5 — Extract `rendering.ffmpeg-finalizer`** Move `_concat_segments()` into `astrid/packs/rendering/finalizers/ffmpeg/`, add `finalizer.yaml`, and implement complete profile comparison, normalization, audio-mode handling, attachment preservation, and cleanup; acceptance: `pytest -q tests/packs/rendering/test_ffmpeg_finalizer.py`.  [HARD]
- [ ] **T3.6 — Register and smoke the built-ins** Update `astrid/packs/rendering/pack.yaml` and built-in manifest tests for static discovery, required binaries, no-import inspection, real FFmpeg rendering, Remotion cleanup, and optional dependency reporting; acceptance: `pytest -q tests/packs/rendering tests/packs/test_audio_render.py` and `cd remotion && npm run typecheck`.

## Batch 4 — Generic routing, provenance, and hybrid planning

**Checkpoint:** The oracle reviews the generic `RenderService`, facade/output behavior, additive provenance v2, and half-open-frame hybrid planner/dispatcher. The review explicitly searches generic code for concrete backend branches. Batch 5 cannot begin until the oracle returns `PASS`.

**Acceptance criteria:**

- `RenderService` performs legacy translation → alias → override → winner → eligibility → support → invoke/validate → audio/finalize → publish in that order.
- Qualified `rendering.remotion` and `rendering.ffmpeg` are strict; legacy `remotion` retains characterized policy, legacy `ffmpeg` is strict, and `hybrid` selects `rendering.legacy_hybrid`.
- `output_name` uses existing input placeholders and cache/CAS identity, rejects separators/traversal/non-MP4 extensions, preserves declared output names, and leaves Hype’s default `hype.mp4` sentinel unchanged.
- Every Remotion, FFmpeg, optimized FFmpeg, audio-reactive, hybrid, and single-segment path produces exactly one video and one committed sidecar.
- Provenance v2 records routing, aliases, overrides, trust, manifests, requests, support, alternatives, inputs, artifacts, profiles, audio, normalization, attachments, segments, and backend fragments while preserving every listed v1 top-level projection.
- Hybrid plans use integer `[start_frame,end_frame)` windows from the canonical profile, preserve characterized transition units/handles, use support reports for assignments, and never recursively call `render()`.
- Empty, single, multiple, all-FFmpeg, and mixed raw-fixture/built-in plans pass; failures clean temporary artifacts and maintain aligned segment provenance.

### Tasks

- [ ] **T4.1 — Implement the generic `RenderService`** Add `astrid/core/rendering/service.py::RenderService` with the frozen selection order, eligibility/support checks, invocation, artifact enforcement, audio completion, finalization, and publication; acceptance: `pytest -q tests/core/rendering/test_service.py`.  [HARD]
- [ ] **T4.2 — Make the facade neutral and output-name aware** Reduce `astrid/packs/rendering/executors/render/run.py` to a facade adapter, update `executor.yaml` with neutral selector/config/`output_name` inputs and placeholder outputs, make parsing order-independent, and remove `executor/runner.py::_normalize_render_command_compat` after its characterization passes; acceptance: `pytest -q tests/packs/rendering/test_render_facade.py tests/core/rendering/test_output_name.py`.
- [ ] **T4.3 — Emit additive provenance v2** Implement core-owned provenance assembly and namespaced backend fragments in `astrid/core/rendering/provenance.py`, retaining all v1 projections and lock-aware conservative cleanup; acceptance: `pytest -q tests/core/rendering/test_provenance.py`.  [HARD]
- [ ] **T4.4 — Port `rendering.legacy_hybrid`** Add `astrid/packs/rendering/planners/legacy_hybrid/{planner.yaml,run.py}` implementing canonical-profile frame windows, transition/handle behavior, support-based assignment, explicit renderer IDs/finalizer, non-recursive dispatch, and normalized segment provenance; acceptance: `pytest -q tests/core/rendering/test_legacy_hybrid.py`.  [HARD]
- [ ] **T4.5 — Lock the routing and hybrid matrix** Add strict/legacy selector, alias/override, trust denial, unsupported-alternative, output-name, every built-in path, raw mixed-plan, audio-control, failure-cleanup, attachment, sidecar, and crash-recovery cases; acceptance: `pytest -q tests/core/rendering/test_service.py tests/core/rendering/test_legacy_hybrid.py tests/core/rendering/test_provenance.py`.

## Batch 5 — Caller migration, semantic parity, and M1 freeze

**Checkpoint:** The oracle reviews the attached-child helper, every production caller, override propagation, one-ledger guarantees, semantic parity fixtures, CI/package data, and the complete M1 verification matrix. M2 cannot begin until the oracle returns `PASS`.

**Acceptance criteria:**

- The attached-child helper requires a validated parent project/run and unique step, scopes and restores all three `ASTRID_TASK_*` variables, preserves caller-selected output, honors facade overrides, and falls back to public `RenderService` only without a project ledger.
- Iteration produces `iteration.mp4` and `iteration.mp4.provenance.json` directly; Hype retains `hype.mp4`; cut/resume preserve deprecated `--renderer`; every migrated path creates only its intended ledger.
- Executor overrides affect attached facade calls; renderer/planner/finalizer overrides affect facade and public-service calls; removal of the executor runtime cache prevents stale in-process resolution.
- Repository searches find no production concrete-renderer import or `-m ...render.run` spawn outside manifests, backend implementations, and explicitly allowlisted tests/debug tools.
- Semantic parity covers Remotion, FFmpeg, nominal-Remotion→FFmpeg, all-FFmpeg hybrid, mixed hybrid, raw renderer, audio controls, invalid artifacts, failures, standalone/attached ownership, and default/non-default output names.
- The normal parity suite fails on empty fixtures, has no environment self-skip, generates tiny media instead of committing MP4s, runs a real FFmpeg render, and treats Remotion typecheck as blocking.
- Contract, pack-author, skill, stage, bridge, compatibility, and audio-semantics documentation is complete; schemas, manifests, fixtures, and scaffold resources are present in installed wheels.
- Targeted suites, full non-opt-in pytest, semantic parity, real FFmpeg, `make check`, `make ci`, wheel smoke, and Remotion typecheck pass.

### Tasks

- [ ] **T5.1 — Add attached-child render invocation** Implement `astrid/core/rendering/attached.py::invoke_attached_render` over existing task/executor primitives with validated ownership, unique step IDs, scoped environment restoration, retained outputs, overridden `rendering.render`, and public-service fallback only when unbound; acceptance: `pytest -q tests/core/rendering/test_attached_render.py tests/test_task_env_contract.py`.  [HARD]
- [ ] **T5.2 — Migrate iteration and cut callers** Update `iteration_video/{run.py,plan_template.py}` and `cut/{run.py,resume.py}` to use attached facade/public service as specified, declare the iteration sidecar, remove rename-only behavior and broken imports, and preserve the deprecated selector; acceptance: `pytest -q tests/packs/iteration/test_iteration_video.py tests/packs/video_editing/test_cut_render_migration.py`.  [HARD]
- [ ] **T5.3 — Migrate Hype, human-notes, and canonical callers** Update `hype/{steps.py,plan_template.py}` and `editorial/executors/human_notes/run.py`, preserve `tools/render_and_check.py`, and add override/single-ledger coverage; acceptance: `pytest -q tests/packs/hype tests/packs/editorial/test_human_notes_render.py tests/core/rendering/test_caller_overrides.py`.  [HARD]
- [ ] **T5.4 — Finish facade manifest and stale-resolution cleanup** Finalize `render/executor.yaml`, remove `@lru_cache` from `execution/executor/argv.py::resolve_executor_runtime_module`, and add a repository source-topology allowlist test; acceptance: `pytest -q tests/core/rendering/test_production_callers.py tests/core/test_executor_registry_snapshot.py`.
- [ ] **T5.5 — Replace the empty renderer parity gate** Populate repository-owned semantic timeline/assets/theme fixtures, rewrite `tests/packs/test_renderer_parity.py`, reuse generated black/silence media and existing Hype/audio-reactive goldens, and wire real FFmpeg plus Remotion typecheck into blocking CI; acceptance: `pytest -q -m renderer_parity tests/packs/test_renderer_parity.py`.  [HARD]
- [ ] **T5.6 — Complete the M1 contract and compatibility documentation** Finish `render-backend-v1.md` and update `docs/packs/{creating-packs,aliases-vs-forks-vs-overrides}.md`, rendering `SKILL.md`/`STAGE.md`, `_core/skill/SKILL.md`, `docs/reference/render-adapter.md`, `docs/guides/creating-tools.md`, and the asset-resolution bridge; acceptance: `bash tests/verify_docs_commands.sh`.  [HARD]
- [ ] **T5.7 — Package and run the M1 gate** Update `pyproject.toml`, wheel smoke, CI lanes, and package-data tests for schemas/manifests/fixtures; run and record the full M1 matrix for the checkpoint; acceptance: `pytest -q`, `make check`, `make ci`, `bash scripts/smoke_wheel_install.sh`, and `cd remotion && npm run typecheck`.

## Batch 6 — Python SDK, conformance, and scaffold

**Checkpoint:** The oracle first enforces the M1 handoff, then reviews wire-equivalent SDK serialization, `RenderContext`, shared conformance fixtures, public import behavior, and the exact four-file scaffold from source and an installed wheel. Batch 7 cannot begin until the oracle returns `PASS`.

**Acceptance criteria:**

- The frozen protocol, schemas, raw fixture, trusted discovery, built-ins, service, and conformance suite work from source and an installed wheel before SDK work proceeds.
- Any SDK/wire mismatch stops the batch and returns to M1 through the oracle; no SDK-only fields or semantics are introduced.
- `astrid/sdk/rendering.py` wraps canonical DTOs, preserves `_json_safe`, keeps heavy imports function-local, and maintains exact lazy public-export ordering and collision checks.
- `RenderContext` supplies allocated paths, descriptor path/URL access, permission checks, sanitized subprocesses, redacted logs/progress, interruption state, probing, hashing, audio completion, attachments, and cleanup while documenting that it is not an OS sandbox.
- Raw and SDK fixtures produce semantically identical wire fields for minimal rendering, request-sensitive support, passthrough audio, no audio, attachment, and intentional failure.
- `astrid renderers create acme.example` writes exactly `pack.yaml`, `renderer.yaml`, `render.py`, and `test_renderer.py`; generated glue is within 50 nonblank/non-comment lines and contains no placeholders.
- Scaffold collision, ownership, command-containment, static validation, trusted install, generated test, two-second smoke, and installed-wheel cases pass.

### Tasks

- [ ] **T6.1 — Enforce the M1 handoff** Run the frozen raw fixture, trusted discovery, built-in registration, `RenderService`, and conformance tests from source and an installed wheel; acceptance: `pytest -q tests/core/rendering tests/packs/rendering` plus `bash scripts/smoke_wheel_install.sh`, with any protocol defect returned to the prior oracle gate.
- [ ] **T6.2 — Add the public rendering SDK** Implement `astrid/sdk/rendering.py::{renderer_main,render,support}`, reuse core DTOs and `sdk.results._json_safe`, and update `astrid._SDK_EXPORTS`, `astrid/sdk/__init__.py::__all__`, and `tests/_sdk_contract.py::EXPECTED_PUBLIC_NAMES`; acceptance: `pytest -q tests/test_sdk_rendering.py tests/test_sdk_public_surface.py`.
- [ ] **T6.3 — Implement `RenderContext`** Add `astrid/sdk/rendering.py::RenderContext` conveniences for paths, assets, permissions, subprocesses, logs, interruption, probing, hashing, audio modes, attachments, and cleanup; acceptance: `pytest -q tests/test_sdk_render_context.py`.  [HARD]
- [ ] **T6.4 — Add shared raw/SDK conformance fixtures** Create `tests/fixtures/renderer_packs/sdk/` cases for minimal render, request-sensitive support, passthrough, no-audio, attachment, and failure, using one conformance harness for raw and SDK implementations; acceptance: `pytest -q tests/core/rendering/test_conformance.py`.
- [ ] **T6.5 — Add the exact four-file scaffold** Implement `astrid/core/rendering/scaffold.py::create_renderer_scaffold` and the initial `create` route in `astrid/core/rendering/cli.py::main`/`gateway/dispatch.py::_dispatch_renderers`, referencing packaged fixtures rather than generating a fifth file; acceptance: `pytest -q tests/core/rendering/test_scaffold.py`.
- [ ] **T6.6 — Prove the scaffold golden path** Add fresh-directory and installed-wheel tests for creation, static validation, generated test, trusted installation, and deterministic smoke output; acceptance: `pytest -q tests/core/rendering/test_scaffold_install.py` and `bash scripts/smoke_wheel_install.sh`.

## Batch 7 — CLI, replay, documentation, and epic freeze

**Checkpoint:** The oracle reviews Batch 7’s diff and the integrated epic: CLI contracts, replay ownership/redaction/drift behavior, author documentation, package contents, source-topology audit, ledger and sidecar invariants, and the complete verification matrix. Completion requires a final `PASS`.

**Acceptance criteria:**

- `astrid renderers create|list|inspect|validate|smoke|replay` is routed through `_TOP_LEVEL_HANDLERS`, appears in help, and remains unbound from project sessions.
- `list` and `inspect` perform static metadata parsing and report source kind, precedence, active revision, trust eligibility/reason, permissions, capabilities, aliases, conflicts, and overrides without importing backend code.
- `validate` is static by default and runs conformance only for execution-eligible candidates; `smoke` calls `RenderService` directly with a temporary output and creates no project run.
- Each CLI verb has a frozen raw-dictionary `--json` shape; expected errors exit 2, degraded bugs exit 1, and interruption cleans up before normal exit-130 behavior.
- Every backend failure emits a self-contained bundle under the owning project run or explicit smoke/output root with request, localized inputs, configuration, identity/digest, support, logs, result, hashes, and exact replay command.
- Bundles redact credentials, authorization headers, and signed URL queries; replay pins renderer and request hashes, reports implementation drift, and requires explicit acknowledgement before using a changed digest.
- Successful disposable workdirs are removed unless `--keep-workdir` is requested; no background TTL or cleanup daemon is introduced.
- Renderer-author documentation covers raw JSON, Python SDK, non-Python commands, trust, permissions, selection, configuration, assets, output/audio/attachments, diagnostics, replay, and legacy selectors while explicitly deferring async jobs, remote infrastructure, and layer compositing.
- Generic service/planner/dispatcher code contains no concrete Remotion/FFmpeg branches; every success has one validated video and committed sidecar, attached paths have one ledger, and every backend failure has a replay bundle.
- Full pytest, semantic parity, real FFmpeg, explicit optional-Remotion evidence, `make check`, `make ci`, wheel smoke, and Remotion typecheck pass.

### Tasks

- [ ] **T7.1 — Complete renderer CLI discovery and smoke** Extend `astrid/core/rendering/cli.py::main`, `gateway/dispatch.py::_dispatch_renderers`, `_TOP_LEVEL_HANDLERS`, and `gateway/help.py` with static `list`, `inspect`, `validate`, and direct-service `smoke`; acceptance: `pytest -q tests/core/rendering/test_cli.py`.
- [ ] **T7.2 — Freeze CLI JSON and error behavior** Add verb-specific JSON-key, session independence, conflict, trust denial, unsupported support, recovery, and interruption tests without introducing a universal envelope or independent exit-code layer; acceptance: `pytest -q tests/core/rendering/test_cli_contract.py tests/test_astrid_error_contract.py tests/test_exec_error_contract.py`.
- [ ] **T7.3 — Capture replay bundles on backend failure** Add `astrid/core/rendering/replay.py::{ReplayBundle,write_replay_bundle}` and service hooks for project-run versus explicit-root ownership, localized hashed inputs, logs/partial results, credential and URL redaction, and exact commands; acceptance: `pytest -q tests/core/rendering/test_replay_bundle.py`.  [HARD]
- [ ] **T7.4 — Implement pinned replay and drift acknowledgement** Add the `replay` CLI route, pin qualified renderer/request/manifest digests, refuse silent backend substitution, require explicit drift acknowledgement, and prove replay succeeds after an acknowledged fixture correction; acceptance: `pytest -q tests/core/rendering/test_replay.py`.  [HARD]
- [ ] **T7.5 — Finish renderer-author documentation** Write the create → implement → test → validate → trusted install → smoke → provenance golden path and separate advanced support/finalizer sections across the contract, pack-authoring, SDK, skill, stage, debugging, and compatibility docs; acceptance: `bash tests/verify_docs_commands.sh`.  [HARD]
- [ ] **T7.6 — Run the epic-wide verification and freeze** Add the generic-code backend-name audit and final success/failure/ledger/sidecar assertions, verify package data, run the complete matrix, and record evidence in `.oracle/verification.md`; acceptance: `pytest -q`, renderer parity, real FFmpeg, optional Remotion with explicit skip evidence, `make check`, `make ci`, `bash scripts/smoke_wheel_install.sh`, and `cd remotion && npm run typecheck`.

## Execution notes

- Persist this markdown exactly as `.oracle/tasklist.md` before implementation. It is frozen; any change requires an explicit oracle-reviewed plan revision.
- Record the pre-execution commit as `C0`. After each batch passes its local acceptance tests, commit the batch as `CN` before check-in. Submit the batch’s tasks, criteria, test evidence, known issues, and `git diff C(N-1)..CN` to the oracle.
- If the oracle reports issues, rework only the current batch, recommit, and resubmit the cumulative `C(N-1)..HEAD` range until `PASS`. Do not begin the next batch early.
- `[HARD]` tasks go to GPT-5.6 Sol at max reasoning. All other tasks go to DeepSeek V4 Flash with the named files, symbols, and acceptance command copied mechanically into its brief.
- Do not execute batches in parallel. Within batches, do not parallelize T1.2–T1.4, T2.4–T2.6, any T3 extraction, T4.1/T4.3/T4.4, T5.1–T5.4, T6.2–T6.5, or T7.1/T7.3/T7.4 because they share contracts, facade files, registries, provenance, or CLI routing.
- Preserve all pre-existing dirty work. Never reset, reformat, or absorb unrelated changes into a batch commit.
- Generate tiny media during tests; do not commit generated MP4 binaries. Real Remotion rendering may skip only for a precisely reported missing dependency, while Remotion typechecking remains blocking.
- Batch 1 must freeze all 18 decisions from the canonical epic brief; `.oracle/plan.md` restates only decisions 4–12.
- At M2 handoff, any wire-contract defect returns to M1 through the oracle. Do not patch it with SDK-only behavior.
