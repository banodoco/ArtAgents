# Updated plan

The 18 locked decisions remain unchanged.

## Resolved implementation decisions

4. **Registry semantics:** build renderer/planner/finalizer registries over `CapabilityRegistry`, `AliasResolver`, and `OverrideStore`. Winner order comes directly from `DiscoveredPack.priority_index`; do not reinterpret executor `metadata["priority"]`. Only execution-eligible candidates enter the executable registry, so an ineligible higher-precedence candidate cannot shadow trusted code.

5. **Aliases and overrides:** extend pack-schema and normalizer alias-kind allowlists for `renderer`, `planner`, and `finalizer`, while keeping bare legacy names programmatic. Resolution is alias → canonical ID → override target → registry winner. Wire `OverrideStore` during default registry construction rather than CLI-only post-attachment.

6. **Run ownership:** a standalone `rendering.render` invocation owns its executor/project run. When another capability already owns the run, invoke the facade through the existing task-attached path:

   - provide the owning project and `ASTRID_TASK_PROJECT`, `ASTRID_TASK_RUN_ID`, and a unique `ASTRID_TASK_STEP_ID`;
   - use an attached/auto-resolved request when retaining the caller’s output directory;
   - let `prepare_project_run()` reuse the parent run ID and step context;
   - never treat `project=None` or `run_root` as a run-reuse mechanism;
   - never invoke a bare nested `astrid executors run` without attachment context.

   Encapsulate this in one small helper over existing task/executor primitives so callers do not hand-roll environment state. Legacy unbound callers and unbound renderer smoke tests use the public `RenderService` directly. Backend commands remain leaf subprocesses and never create `run.json`.

7. **Wire protocol:** backend commands run with `shell=False`, pack root as `cwd`, sanitized environment, absolute request/result paths, and an authoritative result file:

   ```text
   <command...> render|support|plan|finalize \
     --request <absolute-request.json> \
     --result <absolute-result.json>
   ```

8. **Compatibility selection:**

   - `ffmpeg` → strict `rendering.ffmpeg`.
   - `remotion` → the characterized legacy policy, including eligible FFmpeg/audio-specialized routing.
   - `hybrid` → `rendering.legacy_hybrid`, never a renderer ID.
   - Qualified `rendering.remotion` and `rendering.ffmpeg` are strict.
   - Request-sensitive fallback is permitted only by an explicit planner/fallback policy.

9. **Provenance:** provenance v2 is additive. Preserve every currently emitted v1 top-level field for the whole epic, including Remotion, hybrid, and audio-specialization fields. Add authoritative routing, trust, support, artifact, normalization, and backend-fragment data. Do not remove v1 projections without a separate external-consumer audit.

10. **Publication:** validate in an invocation workdir, take a per-output lock, rename the video, then atomically write the hashed provenance sidecar as the commit marker. A crash may leave a detectable orphaned video, but never a sidecar claiming an incomplete artifact.

11. **Developer surfaces:** follow existing conventions:

   - frozen dataclasses and `_json_safe`, with lazy public SDK imports;
   - a plain renderer sub-CLI routed through `_TOP_LEVEL_HANDLERS`;
   - verb-specific raw JSON dictionaries, not a universal CLI envelope;
   - existing `AstridError`/`ExecError` behavior: expected errors exit 2, degraded bugs exit 1, and interruption is cleaned up then allowed to produce normal `KeyboardInterrupt`/SIGINT exit 130 behavior.

12. **Parity:** replace the empty, self-skipping Sprint 08 input-hash test with repository-owned semantic fixtures. Generate tiny media during tests rather than committing ignored MP4s. Blocking CI must perform a real FFmpeg render and Remotion typecheck; a real Remotion render may remain an explicitly reported optional integration test.

## M1 — Renderer kernel and built-ins

- [ ] **M1-00 — Freeze the corrected decisions and characterize the baseline**

  - Draft `docs/contracts/render-backend-v1.md` with the decisions above and an explicit statement that all 18 locked decisions remain unchanged.
  - Preserve the dirty snapshot and record baseline failures/skips without resetting or reformatting unrelated work.
  - Characterize:
    - all three legacy engine values;
    - nominal-Remotion auto-FFmpeg behavior;
    - audio-reactive specialization;
    - current Remotion props, merged-theme, registry, staging, environment, and generated-source behavior;
    - every currently emitted provenance field;
    - transition `duration` versus `durationFrames` behavior;
    - standalone facade run ownership;
    - task-attached facade execution with a retained caller output;
    - the fact that `project=None` auto-resolves or errors and `run_root` does not suppress run creation.
  - Freeze the production callsite inventory:
    - `iteration_video/run.py`;
    - `iteration_video/plan_template.py`;
    - `hype/steps.py`;
    - `human_notes/run.py`;
    - the broken `cut/run.py` and `cut/resume.py` imports;
    - already-canonical `hype/plan_template.py` and `tools/render_and_check.py`.
  - Record that `tests/fixtures/sprint08` is empty and `test_renderer_parity.py` currently neither renders nor runs in CI.
  - Gate: existing rendering, pack, executor, iteration, Hype, and audio-reactive suites remain at their recorded baseline.

- [ ] **M1-01 — Freeze the language-neutral contracts**

  - Add backend-neutral modules under `astrid/core/rendering/` for:
    - renderer, planner, and finalizer descriptors;
    - `RenderRequest`, `SupportReport`, `RenderPlan`, and half-open frame windows;
    - asset descriptors;
    - video and audio profiles;
    - audio ownership;
    - primary `VideoArtifact`, named attachments, and `RenderResult`;
    - structured protocol/backend/artifact/finalizer failures;
    - provenance v2.
  - Add versioned JSON Schemas for request, result, support, plan, finalization, and the three manifest types.
  - Define `[start_frame, end_frame)`, rational FPS/time base, dimensions, container, codecs, pixel format, duration tolerance, resolved audio sample rate/layout, and audio ownership `rendered|passthrough|none`.
  - Require one primary video. Preserve uniquely named, contained attachments without requiring the default finalizer to understand them.
  - Keep backend configuration only in:

    ```json
    {
      "backend_config": {
        "pack.renderer": {}
      }
    }
    ```

    Only the selected backend receives its namespace.
  - Use existing atomic JSON and SHA-256 helpers.
  - Gate: Python DTOs and raw JSON fixtures round-trip identically; unknown versions, invalid frame bounds, duplicate attachments, traversal, and backend attempts to overwrite core fields fail structurally.

- [ ] **M1-02 — Add strict pack-extension loading, registries, and trust eligibility**

  - Extend `astrid/core/pack/schemas/v1/pack.json` and `_optional_pack_extensions()` in `pack/permissions.py` with the exact `extensions.rendering` shape.
  - Add schema/normalizer parity tests for extension keys and alias-kind enums.
  - Add `pack_rendering_manifest_paths()` and descriptor helpers beside existing extension descriptor helpers in `pack/registry.py`.
  - Resolve referenced files relative to the pack root, require containment, and load them statically with `load_manifest_mapping()`.
  - Do not add a renderer component root, manifest walker, `runpy` fallback, or generic component-manifest kind.
  - Extend `PACK_ALIAS_KINDS`, `PackAliasKind`, `pack.json`, and alias extraction for `renderer`, `planner`, and `finalizer`.
  - Build registries directly from `discover_pack_metadata()` so every entry retains `source_kind` and `priority_index`.
  - Add a derived trust/eligibility record without changing `PackDefinition` or inventing `DiscoveredPack.trusted`/`active` fields.
  - For installed candidates, verify the active symlink’s revision and installation trust audit; deny execution for missing, corrupt, or mismatched records. Keep such candidates inspectable for diagnosis. Do not expose staging or inactive revisions through normal discovery.
  - Refactor executor/orchestrator default registry construction to accept and wire `OverrideStore(project_root)` consistently. Use the same mechanism for renderer kinds.
  - Validate renderer-required permissions against the existing disclosure vocabulary:
    `project_files`, `network`, `subprocess`, `environment`, `accelerator`, `external_services`.
  - Register `remotion`/`ffmpeg` legacy selectors programmatically and translate `hybrid` only to a planner policy.
  - Gate: schema/runtime parity, precedence, conflicts, aliases, overrides, cycles, invalid targets, active/inactive installs, corrupt trust records, env denial, explicit-extra eligibility, traversal, and no-import listing tests pass.

- [ ] **M1-03 — Implement command transport and the raw fixture pack**

  - Implement synchronous backend transport with:
    - a unique invocation workdir;
    - pack-root `cwd`;
    - `shell=False`;
    - sanitized child environment;
    - absolute request/result paths;
    - stdout/stderr capture;
    - manifest binary preflight via `shutil.which`;
    - configurable timeout;
    - a new process session and process-group termination;
    - authoritative result-file parsing.
  - Map missing binary, nonzero exit, timeout/interruption, missing result, malformed result, and invalid protocol versions into renderer-qualified symbolic failures.
  - On interruption, terminate and reap the backend process group, clean owned resources, then re-raise interruption.
  - Commit `tests/fixtures/renderer_packs/raw_command/`, implementing the protocol without importing the Astrid SDK and producing a deterministic two-second artifact.
  - Add versioned text-only and generated-media requests; do not commit MP4 binaries.
  - Exercise both an explicitly supplied extra pack root and the real local-install trust/active-revision path.
  - Prove a backend invocation creates no `run.json`.
  - Gate: render/support success, unsupported response, malformed JSON, missing result/output, nonzero exit, timeout, SIGINT cleanup, untrusted env discovery, trusted install, and static no-import inspection all pass.

- [ ] **M1-04 — Extract the minimal host-owned plumbing**

  - Move only the reusable asset-cache library behind a core API; retain `astrid/packs/training/executors/asset_cache/run.py` as a compatibility wrapper.
  - Preserve cache layout, URL keying, resume/drift behavior, metadata, locking, and `EphemeralSession` cleanup semantics.
  - Extract asset classification/materialization and local serving into an invocation-scoped service.
  - Serve only invocation-staged assets from `127.0.0.1`; bind the server directly to port `0`, retain Range support, start inside the managed context, and always shut down, close, and join it.
  - Eliminate the broad `commonpath` server root by hardlinking or copying only required local assets into the invocation stage. Leave existing remote URLs remote.
  - Add one canonical resolved render profile using the same merged theme/timeline canvas consumed by Remotion. Planner, backend requests, and finalizer all receive that profile.
  - Extend `astrid/core/media.py` with fields already available in cut probing: codec, average/rational FPS, pixel format, time base, audio codec/rate/layout, duration, and dimensions.
  - Add renderer-local artifact enforcement for existence, non-empty output, workspace containment, symlinks, hashes, duration, video profile, and audio ownership.
  - Do not change missing-output semantics for all executors globally; `rendering.render` must fail before returning success.
  - Add a locked publication helper in which the sidecar is the final commit marker.
  - Gate: local/cached/remote assets, Range requests, expired URLs, restricted serving, server-start failure, cleanup, invalid artifacts, visual-only modes, attachments, and crash-orphan recovery pass.

- [ ] **M1-05 — Extract and register `rendering.remotion`**

  - Move theme resolution, timeline serialization, project checks, element-registry generation, effect staging, props creation, Remotion subprocess handling, and backend provenance into `astrid/packs/rendering/backends/remotion/`.
  - Register it through `extensions.rendering` and a static renderer manifest using the raw command protocol.
  - Preserve `TimelineComposition`, merged-theme behavior, registry hashes/state, source-pack/effect lineage, resolved effects, and sanitized environment.
  - Put props and asset staging under the unique invocation workdir.
  - Introduce one outer cross-process lock for generated Remotion sources:
    - acquire it before reading registry state or checking generated outputs;
    - cover the three package registries, shim families, active-theme symlink/text pointer, and registry state;
    - hold it through active-theme selection and the complete Remotion render;
    - write registry state atomically;
    - make the developer `gen-types` path acquire the same outer lock across `types.generated.ts` and effect-registry generation;
    - ensure generator primitives do not recursively acquire the lock.
  - Use the invocation-scoped asset server and reject exit-zero/no-output or empty-output cases before provenance.
  - Move private-helper tests to extracted boundaries while keeping a small facade compatibility suite.
  - Gate: registry invalidation, atomic state, theme/profile parity, effect assets, environment redaction, concurrent differing-theme renders, render-versus-`gen-types` contention, success/failure cleanup, output validation, Remotion typecheck, and an available fixture render pass.

- [ ] **M1-06 — Extract and register `rendering.ffmpeg`**

  - Move media-only rendering and audio-reactive colour rendering into `astrid/packs/rendering/backends/ffmpeg/`.
  - Extract pure command/filter builders following the existing audio-reactive builder pattern.
  - Replace validator side effects with an explicit `SupportReport`.
  - Fail closed for:
    - unsupported or unknown track/clip kinds;
    - non-positive clip intervals or source bounds outside probed duration;
    - visual gaps and overlaps;
    - speed changes;
    - unsupported positioning, crop, effect, transition, or non-default opacity semantics;
    - requested visual audio that would be discarded;
    - overlapping audio;
    - `params.fadeIn`/`fadeOut`;
    - missing sources or required audio/video streams.
  - Implement the documented audio controls that are cheap and exact:
    - effective gain is track volume × clip volume;
    - `track.muted` forces zero gain;
    - clip mute remains `volume: 0`; do not invent a clip-level `muted` field;
    - validate gains rather than silently clamping malformed values.
  - Let an explicit planner route unsupported windows elsewhere; strict `rendering.ffmpeg` must not silently alter them.
  - Express media optimization and audio-reactive specialization as request-sensitive support evidence, not facade branches.
  - Preserve compatible stream-copy behavior and supported sequential audio mixing.
  - Return explicit audio ownership; host compatibility policy, not third-party renderers, owns synthesized silence.
  - Use manifest-required binaries and shared subprocess/output validation.
  - Gate: support diagnostics, command graphs, stream-copy, gaps/overlaps, track mute/volume, clip volume zero, fades, source bounds, missing streams/binaries, audio-reactive marker frames/hashes, cleanup, output validation, and provenance pass with a real FFmpeg render.

- [ ] **M1-07 — Extract `rendering.ffmpeg-finalizer`**

  - Move `_concat_segments()` behind the finalizer contract.
  - Probe all input artifacts before assembly.
  - Use the canonical dimensions, rational FPS/time base, and resolved audio target; remove hard-coded 30 FPS and assumed 44.1 kHz stereo.
  - Stream-copy only when the complete profile is compatible. Otherwise normalize dimensions, FPS/time base, codecs, pixel format, sample rate, channel layout, and audio presence.
  - Handle rendered, passthrough, and absent audio without assuming every segment has an audio stream.
  - Record every normalization and preserve named attachments unchanged.
  - Gate: one-segment pass-through, compatible and incompatible multi-segment plans, 24/25/30 and rational FPS, missing audio/video, codec/time-base mismatch, duration mismatch, normalization provenance, and cleanup pass.

- [ ] **M1-08 — Add generic routing, flexible facade output, and provenance v2**

  - Implement `RenderService`:
    1. translate the legacy selector;
    2. resolve its alias;
    3. apply the override;
    4. select the registry winner;
    5. verify execution eligibility;
    6. obtain static/request-sensitive support;
    7. invoke and validate;
    8. complete audio/finalize when required;
    9. publish video and sidecar.
  - Add backend-neutral planner, fallback, finalizer, and configuration inputs.
  - Allow qualified IDs through `engine`; replace fixed argparse choices with validation against legacy names or qualified IDs.
  - Add `output_name` as an ordinary executor input with default `hype.mp4`:
    - reject separators, traversal, and invalid extensions;
    - use existing input-placeholder expansion for `{out}/{output_name}` and `{out}/{output_name}.provenance.json`;
    - keep declared output names `video` and `provenance` stable;
    - rely on the existing inclusion of inputs in cache/CAS identity;
    - add no new dynamic-output or dynamic-sentinel subsystem.
  - Keep Hype’s real pipeline sentinel as `hype.mp4`, since Hype uses the default. Test non-default names through declared output resolution, pipeline propagation, and Arnold collection.
  - Make `render/run.py` a thin facade adapter.
  - Characterize the current argument-order shim, make facade parsing order-independent, then delete `_normalize_render_command_compat` if the compatibility test proves it unnecessary.
  - Emit provenance v2 with:
    - requested legacy selector/policy;
    - resolved renderer/planner/finalizer;
    - source pack/kind/revision and derived trust method;
    - alias and override evidence;
    - manifest and request digests;
    - support decision and alternatives;
    - input and artifact hashes/profiles;
    - audio ownership/completion;
    - normalization and attachments;
    - backend-owned fragments.
  - Preserve all currently emitted optional v1 keys where applicable:
    `engine`, `output`, `timeline`, `assets_registry`, `project_dir`,
    `composition_id`, `active_pack_order`, `active_theme`, `registry_hash`,
    `registry_state`, `resolved_effect_ids`, `resolved_effects`,
    `source_pack_ids`, `element_roots`, `staged_asset_ids`,
    `staged_asset_root`, `segments`, `segment_provenance`,
    `ffmpeg_specialization`, and `audio_reactive_colour`.
  - Ensure plain FFmpeg, FFmpeg fast paths, audio-reactive, Remotion, and single-segment hybrid produce exactly one sidecar.
  - Make previous-output cleanup lock-aware and conservative around corrupt/orphaned pairs; never delete unrelated output solely because a sidecar is unreadable.
  - Gate: strict qualified IDs, legacy selectors, unknown/unsupported alternatives, trust denial, aliases/overrides, output-name handling, every built-in path, sidecar compatibility, and crash recovery pass.

- [ ] **M1-09 — Port hybrid to a generic planner/dispatcher**

  - Extract legacy complexity/window planning as `rendering.legacy_hybrid`.
  - Resolve canvas/FPS once from the canonical merged theme/timeline profile.
  - Represent every segment as integer half-open frames.
  - Preserve characterized transition `duration`/`durationFrames` and handle behavior.
  - Retain effects, transitions, overlays, opacity, and fades while closing fatal gaps:
    - speed changes;
    - overlapping audio;
    - unsupported non-media clips;
    - strict-FFmpeg-invalid visual gaps/overlaps;
    - controls rejected by the selected renderer’s support report.
  - Permit FFmpeg track mute/volume after M1-06 proves exact support; fades continue to route away from FFmpeg.
  - Use renderer support reports to validate assignments rather than relying only on duplicated feature predicates.
  - Emit qualified renderer IDs, support evidence, selection reasons, input hashes, and the finalizer/profile.
  - Remove recursive calls to `render()`. The dispatcher invokes plan entries only through `RenderService`.
  - Add a deterministic mixed plan using the raw fixture renderer for one window and a built-in renderer for another.
  - Preserve legacy `segments` and nested `segment_provenance` projections while adding normalized v2 segment records, including FFmpeg segments.
  - Gate: empty/single/multiple windows, handle merging, frame rounding, transition units, 24 FPS theme canvas, speed/audio overlap, track audio controls, non-media clips, all-FFmpeg hybrid, mixed fixture hybrid, segment failure cleanup, attachments, and final provenance alignment pass.

- [ ] **M1-10 — Migrate every production caller and remove stale resolution**

  - Add one small attached-child invocation helper over existing executor/task primitives. It must:
    - require a validated parent project/run ID and unique step ID;
    - preserve the caller-selected output when requested;
    - scope and restore all environment changes;
    - invoke the overridden `rendering.render` capability through `run_executor`;
    - fall back to the public `RenderService` only when no project ledger exists;
    - never infer ownership from `run_root` alone or add a general executor “no-project mode.”

  | Caller | Required change |
  |---|---|
  | `video_editing/orchestrators/iteration_video/run.py` | Remove the concrete module import. Use its existing request project/run context to invoke the attached facade with `output_name=iteration.mp4`; eliminate the video-only rename. Declare and return `iteration.mp4.provenance.json`. |
  | `video_editing/orchestrators/iteration_video/plan_template.py` | Replace the direct module command with a task-attached canonical `rendering.render` invocation, passing `output_name=iteration.mp4`. |
  | `video_editing/executors/cut/run.py` | Remove the nonexistent sibling import. Use attached facade invocation when a parent context exists, otherwise the public `RenderService`. Preserve `--renderer` as a deprecated compatibility spelling translated to the facade selector. |
  | `video_editing/executors/cut/resume.py` | Apply the same repair and preserve the selector through resume metadata. |
  | `video_editing/orchestrators/hype/steps.py` | Replace `executor_argv("render.py")` with attached qualified facade invocation while preserving the default `hype.mp4` sentinel. |
  | `editorial/executors/human_notes/run.py` | Replace its direct-module render command with attached facade invocation when possible, otherwise the public service. |
  | `video_editing/orchestrators/hype/plan_template.py` | Preserve the qualified facade call, ensure task context accompanies execution, and add override/single-ledger regression coverage. |
  | `tools/render_and_check.py` | Preserve the standalone canonical facade call and include it in the source-search allowlist. |
  | `render/executor.yaml` | Keep the stable executor ID and default `hype.mp4`; add only neutral selector/config/output-name inputs and `{output_name}`-based declared outputs. |
  | `executor/argv.py` | Remove the global `@lru_cache` so pack and executor overrides cannot become stale within a process. |

  - Keep direct imports only where tests exercise extracted implementation units.
  - Prove facade executor overrides affect attached facade paths. Prove renderer/planner/finalizer overrides affect both facade and public-service paths.
  - Assert each migrated orchestrator produces only its intended existing project ledger.
  - Gate: repository-wide searches find no production concrete-renderer import or `-m ...render.run` spawn outside the facade manifest, backend implementations, and explicitly marked test/debug code.

- [ ] **M1-11 — Replace the empty parity story with real semantic gates**

  - Populate repository-owned minimal timeline/assets/theme fixtures and semantic goldens.
  - Reuse `reshape/hype_regression`, generated black/silence media, `tests/golden/hype/merged_render_props.json`, and the existing real audio-reactive test.
  - Replace input-JSON hashing with assertions over:
    - support decisions;
    - commands/filter graphs or Remotion props;
    - resolved canvas/profile;
    - track mute/volume and fade routing;
    - artifact probe results;
    - provenance;
    - bounded duration/frame behavior.
  - Cover Remotion, FFmpeg, nominal-Remotion→FFmpeg, all-FFmpeg hybrid, mixed hybrid, raw renderer, invalid artifacts, and failures.
  - Add standalone-versus-attached run-ledger cases and default/non-default output names.
  - Remove the environment self-skip from the fast semantic parity suite. Keep heavyweight real Remotion rendering separately marked with a precise dependency skip.
  - Ensure blocking CI runs a real FFmpeg render and Remotion typecheck. Do not add a green parity lane that can exercise zero fixtures.
  - Gate: the normal CI test command fails on empty fixtures and passes only after real semantic cases execute.

- [ ] **M1-12 — Freeze M1 documentation and package data**

  - Complete `docs/contracts/render-backend-v1.md`: extension shape, trust eligibility, permission limitations, manifests, protocol, support, assets, media/audio, planning, finalization, run ownership, errors, attachments, provenance, cleanup, and versioning.
  - Update:
    - `docs/packs/creating-packs.md`;
    - `docs/packs/aliases-vs-forks-vs-overrides.md`;
    - rendering `SKILL.md`;
    - render `STAGE.md`;
    - `_core/skill/SKILL.md`;
    - `render-adapter.md`;
    - `creating-tools.md`;
    - the asset-resolution bridge contract.
  - Document that clip mute is `volume: 0`, track and clip volume multiply, track mute wins, and fades are seconds in `params`.
  - Remove or label stale direct-module commands and correct `HypeComposition` to `TimelineComposition`.
  - Package all schemas, manifests, fixtures, and future scaffold templates; extend wheel smoke verification.
  - Final M1 gate: targeted suites, full non-opt-in pytest, semantic parity, real FFmpeg test, `make check`, `make ci`, wheel smoke, and Remotion typecheck pass.

## M2 — Renderer developer kit

- [ ] **M2-00 — Enforce the M1 handoff**

  - Verify the frozen protocol reference, schemas, raw fixture, trusted discovery, built-in registrations, generic service, and conformance suite.
  - Run the raw fixture from source and an installed wheel.
  - If the SDK cannot represent the wire protocol exactly, amend and re-review M1 rather than adding SDK-only behavior.

- [ ] **M2-01 — Add the public Python SDK**

  - Add `astrid/sdk/rendering.py` as a thin layer over canonical core DTOs; do not duplicate serialization models.
  - Provide `renderer_main()` plus functional `render(request, context)` and optional `support(request, context)` author hooks.
  - Reuse frozen dataclasses and `sdk.results._json_safe`.
  - Keep heavy registry/runner imports function-local.
  - Add only explicitly selected public names to:
    - `astrid._SDK_EXPORTS`;
    - `astrid/sdk/__init__.py::__all__`;
    - `tests/_sdk_contract.py::EXPECTED_PUBLIC_NAMES`.
  - Preserve exact ordering, lazy `astrid.sdk` loading, and top-level-module collision checks.
  - Gate: raw and SDK fixtures emit semantically identical JSON, `import astrid` remains lightweight, and public-surface tests pass.

- [ ] **M2-02 — Add `RenderContext` conveniences and SDK conformance**

  - Provide allocated output/work paths, descriptor-based local path/URL access, declared-permission checks, sanitized subprocess execution, redacted logging/progress, read-only interruption state, probing, hashing, completion, attachments, and cleanup.
  - Add helpers for rendered audio, passthrough/mux, and no-audio results.
  - State explicitly that these checks do not create an OS sandbox.
  - Add SDK fixtures for:
    - minimal render;
    - request-sensitive support;
    - visual-only passthrough;
    - visual-only no-audio;
    - named attachment;
    - intentional protocol/backend failure.
  - Gate: raw and SDK implementations pass the same conformance suite and emit the same wire fields.

- [ ] **M2-03 — Add the exact four-file scaffold**

  - `astrid renderers create acme.example` writes only:
    - `pack.yaml`;
    - `renderer.yaml`;
    - `render.py`;
    - `test_renderer.py`.
  - Point `extensions.rendering.renderers` directly at the root manifest.
  - Reference packaged versioned fixtures from the generated test; do not generate a fifth fixture file.
  - Keep generated adapter glue within 50 nonblank, non-comment lines before backend-specific logic.
  - Validate ID ownership, collision handling, command containment, and absence of placeholders.
  - Include the normal installation/trust step in the documented golden path.
  - Gate: create, static validate, generated test, trusted install, and two-second smoke render pass in a fresh directory and installed wheel.

- [ ] **M2-04 — Add renderer CLI discovery, validation, and smoke**

  - Add `astrid/core/rendering/cli.py::main`.
  - Add `_dispatch_renderers` to `gateway/dispatch.py::_TOP_LEVEL_HANDLERS` and update `gateway/help.py`.
  - Keep renderer commands unbound from project sessions.
  - Implement:
    - `create`;
    - `list`;
    - `inspect`;
    - `validate`;
    - `smoke`;
    - `replay` routing, completed in M2-05.
  - `list` and `inspect` parse static metadata only and show source kind, precedence, active revision where applicable, trust eligibility/reason, permissions, capabilities, aliases, conflicts, and override evidence.
  - `validate` is static by default. Explicit conformance execution requires an execution-eligible candidate.
  - `smoke` calls `RenderService` directly with a temporary output. Do not call `run_executor(project=None)`, auto-attach to the current project, or introduce a general no-project executor mode.
  - Follow existing raw-dictionary `--json` conventions and freeze exact keys per verb. Use structured renderer-qualified error dictionaries where machine-readable failure is required.
  - Reuse `AstridError` conventions. Clean up and re-raise interruption rather than adding an independent exit-code layer.
  - The unrelated lifecycle `--engine task|arnold` parser needs no change.
  - Gate: help, dispatch, session independence, JSON keys, error/recovery behavior, conflicts, trust denial, installed selection, unsupported support, interruption, and smoke output pass.

- [ ] **M2-05 — Add replay bundles and `replay`**

  - On backend failure, retain a bundle under the owning project run when one exists, otherwise under the explicit smoke/output root.
  - Bundle the resolved request, localized inputs, backend configuration, renderer/manifest identity and digest, support report, logs, result/partial result, hashes, and exact replay command.
  - Redact environment credentials, authorization headers, and signed URL query strings. Use localized hashed inputs whenever possible.
  - Pin the qualified renderer and request hash. Record implementation drift and require explicit acknowledgement before replaying with a changed digest; never silently resolve another backend.
  - Delete successful disposable workdirs unless `--keep-workdir` is requested. Add no TTL daemon or background cleanup system.
  - Gate: intentional failure emits a self-contained redacted bundle; replay after an acknowledged fixture correction succeeds without rerunning the editorial pipeline.

- [ ] **M2-06 — Finish renderer-author documentation**

  - Write the golden path: create → implement → test → static validate → trusted install/expose → smoke → inspect provenance.
  - Keep support probing and custom finalizers in separate advanced sections.
  - Include raw command/JSON, Python SDK, and non-Python examples.
  - Document trust, disclosure-only permissions, selection, aliases/overrides, backend configuration, assets, output/audio/attachments, cleanup, diagnostics, replay/redaction, and legacy selectors.
  - Clearly defer async jobs, production remote rendering/upload infrastructure, and layer compositing.
  - Extend documentation-command verification and remove stale direct-module paths.

- [ ] **M2-07 — Epic-wide verification and freeze**

  - Run the complete matrix for raw-wire and SDK fixtures, trusted/untrusted discovery, built-ins, strict IDs, legacy selectors, aliases, overrides, hybrid planning, audio modes, attachments, failures, and replay.
  - Assert generic planner/dispatcher/service code contains no concrete Remotion/FFmpeg branches. Built-in names may occur only in registrations, implementations, compatibility translation, and intentional tests/docs.
  - Verify every successful facade/service path produces one validated video and one committed sidecar.
  - Verify attached facade paths create no second `run.json` and every backend failure produces a replay bundle.
  - Re-run full pytest, semantic parity, real FFmpeg, optional real Remotion with explicit skip evidence, `make check`, `make ci`, wheel smoke, and Remotion typecheck.
  - Review independently at the contract/discovery, built-in extraction, generic routing/hybrid, caller migration, SDK/scaffold, and CLI/replay/docs seams.

# Changes from v1

- Kept the strict `extensions.rendering` approach, derived trust eligibility, additive provenance, semantic parity, and existing SDK/CLI conventions.
- Replaced the nonexistent `project=None`/`run_root` reuse assumption with Astrid’s task-attached child-run mechanism; no general executor no-project mode is added.
- Made unbound smoke and legacy unbound nesting use the existing public `RenderService`.
- Kept neutral `output_name`, but implemented it entirely through existing input placeholders and cache identity—no dynamic-output or sentinel subsystem.
- Made FFmpeg audio semantics exact: track and clip gains multiply, track mute wins, clip mute is volume zero, and fades remain unsupported.
- Expanded strict FFmpeg rejection to cover silently discarded visual transforms, invalid source bounds, and missing media streams.
- Extended the Remotion lock from generation through rendering and brought the developer `gen-types` writer path under the same outer lock.
- Corrected caller migration to distinguish attached facade paths from public-service paths while preserving one ledger and one matching sidecar.
- Retained the earlier scope cuts: no generic component system, OS sandbox, global missing-output enforcement, universal CLI envelope, committed MP4s, or replay-cleanup daemon.

# Potential issues

- Trusted renderer commands retain the user process’s OS permissions; trust and declarations do not contain malicious code.
- A valid active symlink with a corrupt install record must remain inspectable while being excluded from execution.
- Task attachment requires a matching project, run ID, and step ID. The helper must scope environment changes and avoid process-global mutation during concurrent in-process work.
- Preserving a caller-selected output during task attachment relies on the existing attached/auto-resolved request semantics; tests must prevent this from regressing into `--project`/`--out` rejection or a new run.
- Hype’s sentinel remains intentionally tied to its default `hype.mp4`; future non-default Hype output names would require an explicit Hype cache redesign.
- The Remotion outer lock serializes renders and `gen-types`. Nested acquisition must be impossible, and developers must not bypass the locked writer entrypoint.
- Correctly applying track mute/volume changes output for timelines that previously relied on FFmpeg silently ignoring those fields.
- Video plus sidecar cannot be atomically renamed as one filesystem object; the sidecar remains the commit marker and orphan recovery is required.
- External Reigh/upload/CAS provenance consumers remain unknown, so no v1 field removal belongs in this epic.
- General pack schema/runtime-loader drift remains; test the new rendering fields in both paths without broadening into a loader rewrite.
- Real Remotion rendering may remain unavailable in blocking CI, so props/provenance coverage and typechecking must remain strong and optional skips explicit.
