## USER — 2026-08-14T14:01:21.731Z

Can you look through the following thing and basically try to make it so that this system has a generalized, as much as possible is part of the plugin system and we keep the actual surface of the kernel to be as narrow as possible while everything else that we need plugs in on top of it. can you just sense check this and that and if there's any kind of questions you think we should ask of the code base in order to validate that this kind of plan gets us towards that end state what are they how do you think about this
```plaintext
# TASKLIST

## Phase 0 — name and legalize the kernel

### 0.1 Lock the kernel and green import baseline — Phase 0 · S · Depends: none

- Update `docs/packs/contract.md` with the authoritative kernel table: CLI gateway; session/project management; task-run machinery; pack discovery/validation/install/store/aliases; capability registries; SDK and skills installer; structure/doctor; foundation/contracts; timeline/eventlog; rendering and generation protocols; Arnold lifecycle/orchestration.
- State the exclusion rule: concrete generation adapters, discoverable capabilities, and optional service domains belong in manifest-backed packs.
- Retain `astrid/core/integrations/arnold/`, `astrid/core/orchestrate/`, `astrid/core/timeline/`, `astrid/core/timeline/eventlog/`, `astrid scratch`, `astrid serve`, `remotion/`, and `themes/` in their host/substrate/data roles.
- Record the verified baseline: `validate_import_layering()` and `validate_repo_structure()` both report zero violations.
- Keep `astrid/core/runtime/in_process.py` as the sole static core-to-pack import exception and preserve the existing manifest-driven dynamic resolver allowlist in `astrid/core/structure.py`; add no exemptions.
- Explicitly test hardcoded/importlib module strings such as those currently in `astrid/core/generation/backends/registry.py:185-205`, because the AST checker cannot see them.

### 0.2 `[XHARD]` Make `_core` a legal, manifest-backed system pack — Phase 0 · M · Depends: 0.1

- Change validation before or atomically with adding `astrid/packs/_core/pack.yaml`; a naïve manifest is runtime-fatal because:
  - `astrid/core/pack/_common.py:144-146` rejects `_core`.
  - `astrid/core/pack/loader.py:94-107` does not skip underscore directories.
  - `loader.py:117-118` requires manifest ID to match the folder.
  - The resulting `PackValidationError` escapes discovery and crashes every registry.
- Update `astrid/core/pack/schemas/v1/_defs.json` so the lexical `pack_id` definition accepts either a normal pack ID or the reserved literal `_core`; do not pretend raw JSON Schema can validate filesystem provenance.
- Add an explicit reserved-ID path in `astrid/core/pack/_common.py` and enforce provenance context in `astrid/core/pack/loader.py`: `_core` is accepted only at the canonical shipped source root.
- Continue rejecting user, local, extra, environment, and installed packs claiming `_core`; preserve folder/ID equality and reject `_core.<name>` capability IDs.
- Add `astrid/packs/_core/pack.yaml` with system metadata, the existing skill root, and no executors, orchestrators, elements, aliases, or extension capabilities.
- Remove the manifest-less skill-shell rules from `astrid/core/pack/validate_first_party.py:136-155` and `astrid/core/pack/validate_layout.py:122-129`.
- Preserve literal `_core → astrid` harness branding in:
  - `astrid/skills/harnesses/base.py`
  - `astrid/skills/harnesses/claude.py`
  - `astrid/skills/harnesses/codex.py`
  - `astrid/skills/harnesses/hermes.py`
  - `astrid/skills/{__init__,registry,cli}.py`
- Extend `tests/packs/test_pack_yaml_schema.py`, `test_pack_discovery.py`, `test_pack_layout_contract.py`, `test_packs_validate.py`, `test_packs_cli.py`, `tests/test_skills.py`, and wheel smoke coverage with lexical schema acceptance, canonical loader acceptance, noncanonical-source rejection, capability emptiness, discovery, and branding invariants.

### 0.3 Establish one deterministic first-party inventory — Phase 0 · M · Depends: 0.2

- Make `_FIRST_PARTY_PACK_IDS` in `astrid/core/pack/validate_first_party.py` describe the tracked, manifest-backed bundled set; add `blender` and `_core`, and remove `_FIRST_PARTY_INTERNAL_DIRS`.
- Derive tests and documentation from that inventory instead of maintaining duplicate shipped-ID lists such as `tests/packs/test_pack_layout_contract.py:49-69`.
- Treat `discord_local` and `seedance_local` correctly: they are checkout-local personal packs excluded through `.git/info/exclude`, not stale or bundled content.
- Do not add those packs to the first-party inventory, delete them, restore them, or suppress their runtime discovery.
- Change `scripts/gen_capability_index.py` to generate the committed capability index from tracked first-party source packs only, excluding untracked/ignored personal packs even when they exist in the live checkout.
- Add a regression fixture containing an untracked personal pack and prove it remains runtime-discoverable but cannot enter the committed index.
- Regenerate `astrid/packs/_core/skill/SKILL.md` from a clean checkout.
- Keep `astrid/packs/builtin/pack.yaml` visible and make its description truthful about the live `builtin.agent_probe` orchestrator; add a manifest/documentation consistency test.

## Phase 1 — one manifest-backed load graph

### 1.1 `[XHARD]` Route skills through the canonical discovered-pack stream — Phase 1 · M · Depends: 0.2–0.3

- Refactor `astrid/skills/discovery.py` to consume ordered `DiscoveredPack` records from `astrid/core/pack/discovery.py` across source, local, extra, environment, and installed roots.
- Delete the direct `PACKS_DIR.iterdir()` walk, manifest-less fallback, swallowed manifest errors, and duplicate `_scan_discovered_packs()` traversal.
- Fix the current `ASTRID_PACKS_PATH` omission caused by `astrid/skills/discovery.py:143-145`; environment-root skills must list.
- Make hidden-pack treatment consistent: hidden packs must not enter source or installed discovery. Preserve the explicitly documented deprecated-pack policy instead of conflating it with hidden visibility.
- Obtain skill roots only from `DiscoveredPack.skill_roots()` and apply pack-ID deduplication once at canonical source priority.
- Preserve explicit-root testability by parameterizing shared discovery rather than adding another filesystem scanner.
- Make invalid manifests fail at the pack boundary and never leak skills.
- Preserve top-level SDK laziness asserted by `tests/test_sdk_public_surface.py:3339-3386`.
- Add source/local/extra/environment/installed ordering, `_core`, duplicate, hidden-installed, deprecated, invalid-manifest, and checkout-local pack cases in `tests/packs/test_pack_discovery_metadata.py` and `tests/test_skills.py`.

### 1.2 `[XHARD]` Remove theme and workspace element discovery — Phase 1 · L · Depends: 1.1

- In `astrid/core/element/registry.py`, `catalog.py`, and `__init__.py`, remove `ElementSource`, `default_sources()`, `load_source_elements()`, active-theme element loading, `WORKSPACE_ROOT`, `legacy_workspace`, and source-conflict warnings.
- Build the element registry exclusively from `discover_pack_metadata()` and pack-declared element roots; do not create pseudo-packs for absent theme/workspace sources.
- Remove discovery-only `active_theme`, `include_missing_roots`, and `elements --theme` inputs from `astrid/core/element/cli.py` and `astrid/sdk/discovery.py`.
- Update `astrid/core/timeline/validators/`, `astrid/packs/training/executors/pool_merge/run.py`, `astrid/packs/rendering/backends/remotion/run.py`, and `scripts/gen_effect_registry.py` to use pack metadata.
- Keep theme selection, pointers, state, and provenance as rendering data.
- Replace positive theme/workspace discovery expectations with negative no-scan rails in `tests/core/test_elements_registry.py`, `tests/timeline/test_effects_catalog.py`, `tests/timeline/test_timeline_elements_catalog.py`, and `tests/test_sdk_public_surface.py`.
- Preserve local-pack precedence and rendering behavior through `tests/packs/test_pack_local_priority.py`, `tests/packs/test_text_card_override.py`, and Remotion registry/code-generation tests.
- Assert every loaded element has `source == "pack:<id>"` and matching pack metadata.

### 1.3 Package and prove the canonical graph in wheels — Phase 1 · L · Depends: 1.1–1.2

- Replace the rendering-only package-data declaration in `pyproject.toml` with explicit coverage for:
  - `core/model_catalog/*.yaml`
  - existing rendering schemas and parity fixtures
  - `packs/*/pack.yaml`
  - `packs/*/executors/*/executor.yaml`
  - `packs/*/orchestrators/*/orchestrator.yaml`
  - element manifests
  - rendering extension YAML
  - `packs/*/skill/SKILL.md`
  - nested executor skills
  - executor and orchestrator `STAGE.md` files
- Do not use a blanket recursive pack-root include.
- Extend `scripts/smoke_wheel_install.sh` to run outside the checkout with an empty `ASTRID_HOME` and prove:
  - Every canonical bundled manifest is present.
  - Representative executor, orchestrator, element, nested skill, STAGE, and extension files ship.
  - `ModelRegistry.load_default()` and `LoraRegistry.load_default()` succeed.
  - Skills discover from the wheel’s source layer.
  - `include_installed=True` with an empty installed store is a no-op, not a loss of source packs.
- Prefer canonical-inventory assertions over brittle fixed capability counts.
- Preserve `import astrid` laziness and add a rail that loading registries does not eagerly import concrete generation, Reigh, or RunPod implementations.

## Phase 2 — extract concrete domain implementations

### 2.1 `[XHARD]` Move concrete generation backends into the generation pack — Phase 2 · M · Depends: 1.1, 1.3

- Move:
  - `astrid/core/generation/backends/fal.py`
  - `astrid/core/generation/backends/codex.py`
  - `astrid/core/generation/backends/vibecomfy.py`
  into `astrid/packs/generation/backends/`.
- Declare `cloud → FalBackend`, `codex → CodexBackend`, and `local → VibeComfyBackend` under `extensions.generation.backends` in `astrid/packs/generation/pack.yaml`.
- Use the existing, tested hook; do not add another extension framework. It is already defined in `astrid/core/pack/schemas/v1/pack.json:114-128` and consumed by generation registry/features/verbs and `astrid/core/pack/permissions.py:141`.
- Delete builtin seeding and hardcoded module strings from `astrid/core/generation/backends/registry.py:78-79,185-205`.
- Keep provider-neutral protocols, registry, taxonomy IDs, verbs, and feature contracts in core. A bare registry must be empty; default loading must populate it only from discovered manifests.
- Remove concrete exports and lazy concrete imports from `astrid/core/generation/backends/__init__.py`.
- Update generation executor imports, `codex_unavailable_reason`, golden patch targets, gateway generation resolution, SDK discovery, and model-catalog validation.
- Delete the six tracked files under `fal-voice-upscale/` in this change instead of repairing their private FAL-helper imports; they are uncalled scratch experiments already designated for removal and recoverable from Git history.
- Move concrete adapter tests from `tests/core/generation/` to `tests/packs/generation/`; update:
  - `tests/test_generation_backend_registry.py`
  - `tests/packs/builtin/generate_image/test_codex_backend.py`
  - `tests/test_sdk_public_surface.py`
  - generation parameter-map tests
  - wheel smoke
- Preserve the third-party descriptor rail in `tests/test_third_party_integration.py`.
- Add explicit negative tests for old core backend paths and hardcoded importlib strings.
- Extend wheel smoke to prove the generation manifest supplies all three descriptors and that removing that manifest removes them.

### 2.2 Move experiments into the iteration pack — Phase 2 · M · Depends: 0.1

- Move `astrid/core/experiments/` to `astrid/packs/iteration/experiments/` without a compatibility shim.
- Update iteration experiment import, prepare, review, and review-session entrypoints.
- Update `astrid/packs/editorial/executors/human_review/run.py`, the second current consumer.
- Document pack-to-pack support-module imports as legal while retaining the prohibition on core-to-pack imports.
- Move `tests/core/experiments/` under `tests/packs/iteration/experiments/` and update iteration/editorial tests and `STAGE.md` references.

### 2.3 `[XHARD]` Move RunPod maintenance into the RunPod pack without a new abstraction — Phase 2 · M · Depends: 0.1, 1.1

- Move `astrid/core/integrations/runpod/storage.py` and `sweeper.py` into support code under `astrid/packs/runpod/`.
- Add canonical executors and manifests for:
  - `runpod.sweep`
  - `runpod.list_volumes`
  - `runpod.ensure_storage`
- Do not add a core `RunPodMaintenance` Protocol or another extension hook: after the callers below are rewired, core has no remaining consumer that justifies one.
- Preserve sweep dry-run diagnostics and storage recovery messages.
- Rewire the transitional top-level `runpod` handler through canonical executor dispatch rather than statically importing pack code.
- Remove `_check_runpod_stale_handles()` from `astrid/core/doctor.py`; replace it with executor coverage and do not add a doctor extension hook.
- Keep `require_existing_storage` pack-local. Replace training’s imported `ENSURE_STORAGE_HINT` with a local message pointing to `runpod.ensure_storage`; do not create a core interface solely to share a diagnostic string.
- Update `astrid/packs/runpod/pack.yaml`, `skill/SKILL.md`, executor `_common.py`, and `astrid/packs/training/orchestrators/training_run/{compute_backends,config}.py`.
- Remove `astrid/core/integrations/runpod/` only after all imports have moved.
- Relocate or retarget `tests/packs/runpod/test_sweeper.py`, `test_ensure_storage.py`, `tests/test_sweeper_async.py`, `tests/test_sweeper_edges.py`, `tests/test_doctor_setup.py`, and task-mutation inventories.
- Add no `astrid/core/structure.py` exemption.

### 2.4 `[XHARD]` Invert the generic Reigh bridge state before extraction — Phase 2 · M · Depends: 0.1

- Create `astrid/core/timeline/asset_registry_state.py` for provider-neutral:
  - latest registry-event recovery
  - sidecar repair
  - record/source resolution
  - no-pruning merge semantics
- Move the generic logic currently buried in `astrid/core/integrations/reigh/local_bridge.py:485-549` into that host module.
- Make `astrid/core/timeline/asset_registry_edits.py` and the eventual pack bridge consume the new host helper.
- Extend the existing Protocol precedent in `astrid/core/contracts/remote_timeline.py` with only the remote load/save/list shapes needed by migration, editing, and worker callers.
- Preserve `astrid/core/timeline/{local_fs,supabase,selector,reigh_events,transfer}.py`.
- Keep event recovery, CAS, crash reconciliation, sidecar repair, no-op, and no-pruning behavior in `tests/timeline/test_asset_registry_sync.py`; move generic recovery tests out of `tests/integrations/reigh/test_local_bridge_helpers.py`.

### 2.5 `[XHARD]` Move the Reigh service domain and worker into the Reigh pack — Phase 2 · L · Depends: 2.4

- Move Reigh environment, provider, bridge transport, task client, remote timeline I/O, JWT/JWKS, append service, error, and worker implementations from:
  - `astrid/core/integrations/reigh/`
  - `astrid/core/integrations/worker/`
  into `astrid/packs/reigh/integration/` and pack executor support.
- Keep the host timeline/eventlog primitives in core and delete compatibility copies such as `event_construction.py` and the integration-local `supabase_client.py`.
- Add `reigh.worker`, preserving the long-running claim loop, signal handling, authentication, and qualified provenance.
- Add `reigh.serve_local_bridge` for the pack-owned HTTP/CORS/media transport, including `--projects-root`.
- Preserve top-level `astrid serve` as the documented, unbound host facade. Resolve its pack implementation through the canonical registry without weakening normal executor project/session requirements or adding a general service framework.
- Add a deliberately narrow `reigh.timeline_edit` executor replacing only the existing remote operations:
  - `add-clip`
  - `move-clip`
  - `set-theme`
- Preserve PAT-by-default authentication, optional service-role auth, optimistic `expected_version`, three retries, `force=False`, and event descriptors. Do not expand it to the full local timeline CLI.
- Remove remote `projects list` because `reigh.reigh_data` already returns timelines.
- Remove remote `projects edit` from `astrid/core/cli/project.py` and `project_handlers.py` after `reigh.timeline_edit` is covered.
- Delete `scripts/node/ops_helper.mjs` only after proving its sole mutation caller is gone.
- Keep generic local project-store and local `timelines` commands in core.
- Update Reigh pack manifests, skill, permissions, STAGE files, `scripts/reigh_seed_timeline_events.py`, `tests/core/test_project_cli.py`, `tests/test_cli_gate.py`, provider tests, and `docs/architecture/timeline-event-sourcing/m6a-astrid-supabase-contract.md`.
- Ensure core gateway, project handlers, and timeline code never statically import pack implementations.

### 2.6 Close extraction imports and CI path coupling — Phase 2 · M · Depends: 2.1–2.5

- Move Reigh-domain, worker, claim-loop, task-client, JWT, provider, and baseline tests under `tests/packs/reigh/`; retain host timeline/eventlog Protocol tests under `tests/timeline/`.
- Replace positive inventories in `tests/test_structure_contracts.py` and `tests/test_m2_public_surface.py` with negative rails for:
  - `core/experiments`
  - concrete generation backends
  - Reigh implementations
  - RunPod implementations
  - worker implementations
- Require repository searches for `astrid.core.integrations.{reigh,runpod,worker}` to return no live imports.
- Wire the existing import-layer checker into `scripts/reshape/run_ci_checks.sh`; add no exemptions.
- Replace depth-limited changed-file matching in `scripts/reshape/run_ci_checks.sh:139-163` with arbitrary-depth `astrid/**` selection and cover moved Reigh/RunPod paths in `tests/reshape/test_ci_changed_selection.py`.
- Keep the `astrid.core.session.identity` seed import because session identity remains kernel-owned.
- Update `.github/workflows/bridge-latency.yml` to trigger on `astrid/packs/reigh/**` while retaining `astrid/core/timeline/**`, and make checkout test the actual PR ref rather than a hardcoded external repository state.
- Keep all moved tests under `tests/` so broad discovery cannot silently lose them.

## Phase 3 — retire capability-shaped host aliases

### 3.1 Remove pure executor aliases — Phase 3 · S · Depends: 2.5

- Remove top-level:
  - `publish`
  - `publish-youtube`
  - `upload-youtube`
  - `reigh-data`
- Point users to:
  - `executors run reigh.publish`
  - `executors run youtube.upload`
  - `executors run reigh.reigh_data`
- Update `astrid/core/gateway/dispatch.py`, `help.py`, related gateway exports, `tests/test_pipeline_dispatch_aliases.py`, and social-publish tests.
- Add negative root-help and unknown-command assertions.
- Preserve session gating semantics while the aliases exist; none of these routes currently bypasses the bound-session gate.

### 3.2 Remove RunPod and worker host routes after executor parity — Phase 3 · M · Depends: 2.3, 2.5, 3.1

- Remove top-level `worker` only after `reigh.worker` covers the claim loop.
- Remove top-level `runpod` only after `runpod.sweep`, `runpod.list_volumes`, and `runpod.ensure_storage` cover its entire maintenance surface.
- Delete `astrid/core/gateway/runpod.py`, obsolete dispatch functions, help entries, and unused exports.
- Retain `_dispatch_executor_main` if still used by the permanent `serve` facade or other canonical host bridges.
- Keep `scratch`, `astrid/core/gateway/scratch.py`, `serve`, and the current unbound `serve` allowlist entry.
- Update the frozen allowlist assertions in `tests/test_cli_gate.py` in the same change.
- Add gateway-level negative coverage for all six retired tokens, including the previously untested `worker` route, plus positive `scratch` and `serve` coverage.
- Replace shortcut commands in RunPod, Reigh, and YouTube skills, STAGE files, recovery messages, and manifests with qualified executor invocations.

## Phase 4 — enforce pack layout and make the repository truthful

### 4.1 `[XHARD]` Canonicalize pack-private entrypoints — Phase 4 · L · Depends: Phase 3

- Convert:
  - `astrid/packs/blender/deploy.py` into `blender.deploy`
  - `astrid/packs/blender/mesh_fetch.py` into `blender.mesh_fetch`
- Move `render_core.py`, `renders/`, and `server/blender_render_server.py` beneath the appropriate executor support trees; retain library imports but remove alternate user-facing `__main__` surfaces.
- Update Blender imports, presets, README, pack manifest, skill, STAGE files, and tests.
- Classify rendering backend/planner/finalizer runners as manifest-private transport commands, not new executors:
  - `astrid/packs/rendering/run.py`
  - `backends/{ffmpeg,remotion,threejs}/run.py`
  - `planners/{legacy_hybrid,threejs_hybrid}/run.py`
  - `finalizers/ffmpeg/run.py`
- Have `astrid/core/rendering/transport.py` set the internal-invocation marker and guard those commands so direct subprocess invocation fails while manifest transport succeeds.
- Remove the unsupported `python -m astrid.sdk.rendering` claim from `astrid/sdk/rendering.py` and `docs/reference/sdk.md`; do not create another public CLI.
- Remove executable `__main__` behavior from the three unledgered generation golden demos; retain them only as non-runnable fixtures if tests still consume them, otherwise delete them.
- Add subprocess rails proving canonical capability/transport invocation works and direct pack-module invocation fails.
- Add a scoped search rail for stale `python -m astrid.packs.*` instructions while permitting exact manifest-private commands.

### 4.2 `[XHARD]` Enforce actual pack-root layout — Phase 4 · L · Depends: 4.1

- Extend `astrid/core/pack/validate_layout.py` to walk real pack-root entries rather than validating exception declarations alone.
- Permit:
  - `pack.yaml`
  - declared capability/content roots
  - `skill/`, `docs/`, `examples/`, `schemas/`, `fixtures/`, `golden/`
  - capability-local golden fixtures
  - Python package markers
  - manifest-declared extension roots
  - narrowly documented support-library roots declared by the owning manifest
- Declare `astrid/packs/editorial/hype/` as library-only support in `astrid/packs/editorial/pack.yaml`; prove it exposes no independent discovery or CLI surface.
- Preserve rendering’s declared `backends/`, `planners/`, and `finalizers/` extension layout.
- Reject undeclared loose files and directories with actionable paths.
- Move `astrid/packs/fal/tests/test_h3_video.py` to `tests/packs/fal/`.
- Add positive rendering/editorial/golden/fixture tests and negative Blender-style junk cases in `tests/packs/test_pack_layout_contract.py` and `tests/packs/test_packs_validate.py`.

### 4.3 Close root-hygiene gaps and root-writing tests — Phase 4 · M · Depends: 2.1, 4.2

- Verify `fal-voice-upscale/` is absent after Task 2.1 and remove it from `ROOT_DIR_ALLOWLIST` in `scripts/reshape/check_repo_hygiene.py`.
- Add `*.mp3` to `.gitignore` media rules and the hygiene checker’s tracked-runtime-media rules.
- Extend `find_unknown_root_entries()` and `tests/reshape/test_repo_hygiene.py` to inspect actual root filesystem entries as well as tracked Git paths.
- Replace root-directed temporary directories with `tmp_path`, `TemporaryDirectory()`, or the system temp directory in:
  - `tests/test_pipeline_caching.py`
  - `tests/core/test_project_cli.py`
  - `tests/test_managed_write_paths.py`
  - worker/claim-loop tests
  - `tests/core/test_executor_cli.py`
  - `tests/packs/reigh/test_open_in_reigh.py`
  - `tests/timeline/test_edit_helpers.py`
- Do not add speculative deletion rules for absent `external/`, competition, `mgt-*`, or pipeline-test directories.
- Do not touch `.oracle-threejs-archive/`; it is user-owned staged work outside HEAD. Run final hygiene validation from a clean checkout.

### 4.4 Complete the documentation and CI truth pass — Phase 4 · M · Depends: 4.1–4.3

- `docs/packs/contract.md`: locked kernel, one manifest-backed graph, no concrete capability exceptions.
- `docs/packs/pack-taxonomy.md`: `_core` as a manifest-backed system pack; visible `builtin`; Blender included; all current shipped manifests accurately described as `install_tier: core`; correct alias-carrier claims.
- `docs/architecture/repo-shape.md`: actual `astrid/core/execution/{executor,orchestrator}` paths, current gateway modules, complete kernel directories, and no legacy workspace source.
- `docs/architecture/import-tiers.md`: packs may consume stable kernel APIs and pack support modules; core may use only the fixed runtime bridges and provider-neutral Protocols.
- `docs/contracts/platform-contract.md` and `docs/architecture/repo-shape.md`: derive the SDK public surface accurately—currently 32 exports, not 28.
- `docs/packs/adapter-packs.md`: include `fal.h3_video`.
- `docs/reference/{architecture,sdk}.md`: qualified capability routes, pack-only discovery, and no silent module CLI.
- Generation, iteration, Reigh, RunPod, YouTube, Blender, rendering, builtin, and `_core` skills/manifests/STAGE files: current paths and commands.
- `docs/contracts/integration_contracts.md` and `docs/contracts/asset-resolution-generation-bridge-contract.md`: pack ownership while retaining documented `astrid serve`.
- `docs/guides/ci-lanes.md` and documentation-command verification: arbitrary-depth changed-file selection and current workflow paths.
- Regenerate `astrid/packs/_core/skill/SKILL.md` from the deterministic tracked inventory.
- Search for stale core-domain paths, removed aliases, obsolete pack counts, direct pack module commands, and old `_core` exception language.

### 4.5 Run the full closure gate — Phase 4 · M · Depends: 4.1–4.4

- Run `python3 -m astrid packs validate astrid/packs`.
- Run schema, pack discovery, skill, element, structure, gateway, doctor, generation, iteration, Reigh, RunPod, rendering, layout, CI-selection, and hygiene test groups.
- Run `scripts/smoke_wheel_install.sh` outside the source checkout with an empty `ASTRID_HOME`.
- Run `scripts/reshape/run_ci_checks.sh` and the full broad test suite; do not rely on the changed-file fast lane alone.
- Run Remotion typechecking and renderer-parity tests.
- Verify the import-layer checker remains green with zero new exemptions.
- Search for retired gateway tokens, deleted core-domain imports, hardcoded old backend module strings, obsolete paths, and unsupported direct module commands.
- Verify all executors, orchestrators, elements, skills, and concrete generation backends originate from manifest-backed packs.
- Verify `astrid/core/integrations/` contains only the retained Arnold implementation domain.
- Verify the deterministic capability index and repository hygiene from a clean checkout.

# EXPLORE

- **Sessionless `serve` delegation:** before Task 2.5, trace the gateway, executor runner, project/session gate, output-root handling, and shutdown path. Confirm `astrid serve --projects-root ...` can resolve and launch the pack-owned bridge without granting all executors a sessionless mode. If the standard executor runner cannot preserve this contract, use the smallest dedicated host adapter rather than introducing a general service framework.
- **Manifest-private command boundary:** before Task 4.1, inventory the exact rendering transport and deployed Blender-service subprocess callers so the shared internal-invocation guard covers every legitimate caller without creating another public CLI surface.

# OPEN QUESTIONS

- None.

```

## anthropic/claude-fable-5 (anthropic/claude-fable-5) — 2026-08-14T14:01:21.732Z

# Sense check: does this plan get you to a narrow kernel?

**Overall: yes, structurally.** The sequencing is right (legalize `_core` → unify discovery → extract implementations → retire aliases → enforce layout → truth pass), the plan is disciplined about *not* inventing new abstractions (no RunPod Protocol, no doctor hook, no service framework), and it leans on negative rails and wheel-smoke proofs rather than trust. Those are the correct instincts for kernel-narrowing work.

But there are four places where the plan is either silent on an architectural decision, or quietly makes one that undermines the stated goal. Those are where I'd push before executing.

---

## The four things I'd challenge

### 1. Task 2.2 legalizes pack-to-pack imports as a one-line side effect

> "Document pack-to-pack support-module imports as legal"

This is the single biggest architectural decision in the document and it's buried inside the experiments move. If `editorial` statically imports `iteration/experiments/`, packs are no longer independently removable — which is the whole point of a plugin system. Before accepting this, decide:

- Do pack manifests get a `depends:` field, with an import checker validating cross-pack imports against declared dependencies?
- Or is the rule "cross-pack imports allowed only between packs sharing an `install_tier`," making them de facto one unit?

Either answer is defensible; leaving it as informal documentation is not, because it will silently grow.

### 2. Arnold's kernel residency is asserted, never justified

The plan keeps `astrid/core/integrations/arnold/` and the closure gate *verifies* it's the only thing left in `core/integrations/` — but Reigh and RunPod, which look structurally identical (external service domains), get extracted. If Arnold is genuinely substrate, `docs/packs/contract.md` should say *why* (e.g., the task-run machinery can't function without it). If it's just harder to extract, say that too and record the future path. Otherwise the "exclusion rule" in 0.1 has an unexplained exception baked into it on day one, and the next person will use it as precedent.

### 3. "Packs may consume stable kernel APIs" — with no definition of stable

Task 4.4's import-tiers update permits packs to import kernel APIs, but nothing in the plan defines the stable set. Without that, every existing `from astrid.core.X import Y` in every pack gets grandfathered, and the kernel's *effective* surface is "everything any pack currently touches" — which can be far wider than the kernel table in `contract.md`. This deserves its own task: enumerate what packs actually import from core, classify each as contract or accident, and add a rail restricting pack imports to an explicit allowlist (even a generous one).

### 4. How does the pack register `remote_timeline` / `serve` / generation implementations back into core?

The plan says core resolves pack implementations "through the canonical registry" and keeps `in_process.py` as the sole static exception. Fine — but verify the *mechanism* for each inversion (2.1, 2.4, 2.5) really flows through manifest-declared extensions and never grows the runtime-bridge exception. The `extensions.generation.backends` hook exists and is tested; the equivalent for the Reigh remote-timeline Protocol implementation is not spelled out. That's the place a second static core→pack import will sneak in.

---

## Questions to ask the codebase before/while executing

These are the validation queries I'd run to confirm the plan's assumptions hold:

**Dependency graph reality checks**
1. `grep -rn "astrid\.packs" astrid/core/` — beyond `in_process.py` and the hardcoded strings in `backends/registry.py:185-205`, are there *any* other references (importlib strings, subprocess `python -m` commands, entrypoint strings inside YAML)? The plan tests known ones; this proves there are no unknown ones.
2. `grep -rn "astrid\.core" astrid/packs/` — inventory every kernel API packs consume today. This is the input to concern #3 above.
3. `grep -rn "astrid\.packs\.<other>" astrid/packs/` — what is the *existing* cross-pack import graph? Is editorial→iteration really the only edge, or are there more that Task 2.2's rule will silently bless?
4. Does anything in `astrid/core/` statically import from `remotion/` or `themes/`? They're retained as "substrate/data" — confirm they're data, not code coupling.

**`_core` legalization blast radius (0.2)**
5. Does anything *persist* pack IDs — task ledgers, timeline event logs, session state, the capability index, installed-store metadata? If so, does `_core` becoming a real manifest-backed ID change any serialized record or round-trip path where the provenance check doesn't run?
6. Can the installed-pack store or alias system ever be fed a path that resolves to a `_core`-claiming manifest via symlink or relative-path tricks? The provenance check is "canonical shipped source root" — how is *canonical* computed?

**Discovery unification (1.1)**
7. What's the cold-start cost of full manifest discovery + validation on every CLI invocation once skills route through it? Is there caching, and does the plan's "invalid manifests fail at the pack boundary" turn one broken user-local pack into a bricked CLI? (Fail-fast is right for source packs; for user/local roots you may want quarantine-with-error rather than crash.)
8. What actually consumes hidden packs today, and do any *aliases or capability references* point into a hidden pack? 1.1 tightens hidden-pack exclusion — confirm nothing depends on the current leak.

**Extraction parity (2.3, 2.5, 3.x)**
9. Search skills, STAGE files, docs, scripts, cron/CI in *other* repos, and recorded task ledgers for the six retired tokens (`publish`, `publish-youtube`, `upload-youtube`, `reigh-data`, `runpod`, `worker`). Is anything outside this repo calling them? Hard removal vs. deprecation window depends on the answer.
10. For `reigh.timeline_edit`: enumerate every current caller of remote `projects edit` and confirm add-clip/move-clip/set-theme is genuinely the complete used surface, not just the documented one (check ledgers/logs, not docs).
11. For `astrid serve`: the EXPLORE item is right — but also ask whether the executor runner's *output-root and provenance* handling assumes a session even when gating is bypassed. Sessionless dispatch can pass the gate and still write to session-shaped paths.

**Packaging truth (1.3)**
12. Is the wheel-smoke inventory *derived from the tracked source tree* (e.g., "every `pack.yaml` under `astrid/packs/` in git must exist in the wheel") rather than a maintained list? Explicit pyproject globs without a tree-derived parity test means every new file type is a silent wheel gap.

<details>
<summary>Smaller notes (worth a look, not blockers)</summary>

- **Drift checks for generated artifacts:** `_core/skill/SKILL.md` and the capability index are "regenerated from a clean checkout" twice — add a CI check that committed output matches regeneration, or it will drift the week after 4.5.
- **0.1's importlib-string tests:** good, but make it a general rail (grep for `importlib.import_module` with string literals under `astrid/core/`), not just a test of the known registry lines — otherwise 2.1 fixes the instance and the class of bug survives.
- **Hidden vs. deprecated policy (1.1):** the plan says "don't conflate" — write the two policies down side by side in `contract.md`, since the current conflation is presumably why they're conflated in code.
- **`tests/` centralization:** keeping all tests under `tests/` is right for now, but note it as a known cost if any pack is ever meant to be externally installable/developed.
- **Extension-hook admission rule:** the plan repeatedly refuses new hooks (correct) but never states the criterion for when a hook *is* justified. One paragraph in `contract.md` ("a hook requires ≥2 independent implementations and a core consumer" or similar) prevents relitigating this every quarter.
- **`ENSURE_STORAGE_HINT` duplication (2.3):** duplicating the diagnostic string is the right call vs. a shared interface, but add a comment cross-reference in both locations so they don't diverge into contradictory advice.

</details>

---

## How I'd think about it overall

The plan is unusually honest — it names the exact files and line numbers that make each move dangerous, which suggests it was written against the real tree, not from memory. Execute Phases 0–1 as written; they're low-regret. Before Phase 2, resolve challenges #1–#4 above explicitly (they're each a one-paragraph decision, not new work). And treat the "OPEN QUESTIONS: None" section with suspicion — a plan this large with zero open questions usually means the open questions were resolved silently. The pack-to-pack import rule and the "stable kernel API" definition are exactly those silently-resolved questions; surface them as real decisions before they become de facto architecture.

## USER — 2026-08-14T14:03:17.860Z

And if I wanted to move some of the kernel into another repo that feeds, that this uses but also other agent packs use. Yeah, what would I need to do to do that? Basically I want to have a structure for building these agent tools like this. You know, is there any kind of cases where we're like buying into an architecture? This will actually be part of Arnold but it's going to be renamed. But are there any cases here where we're buying into an architecture that's allowing us into being something part of this repo or are we basically setting it up so it'll be more portable?

## anthropic/claude-fable-5 (anthropic/claude-fable-5) — 2026-08-14T14:03:17.861Z

# Short answer

You're mostly building portable bones — manifests, extension hooks, no static core→pack imports, wheel proofs outside the checkout. That's exactly the skeleton a shared "Arnold framework" repo needs. But the plan does have a handful of places where **identity and trust are derived from *this repo's filesystem and git state*** rather than from packaging/distribution identity, and one giant implicit decision — **the Python namespace** — that will cost you a second full migration if you don't confront it now.

Here's the breakdown.

---

## Where the plan is genuinely portable (keep as-is)

- **Manifest-backed everything.** `pack.yaml` + schema v1 + extension hooks (`extensions.generation.backends`, rendering's declared backends/planners/finalizers) is a real plugin contract. Another repo can implement it.
- **Multi-root discovery.** Source / local / extra / environment / installed roots (1.1) is already the right shape — in a multi-repo world, "source" just becomes "roots registered by the product distribution." Nothing structural changes.
- **`packs validate <path>` taking a path argument.** That's a shippable conformance tool, not a monorepo script. Lean into this.
- **Wheel smoke outside the checkout with empty `ASTRID_HOME`** (1.3). This is literally a rehearsal for the kernel living elsewhere.
- **Negative rails.** Import-layering checks and no-scan rails are enforcement you export to the framework, unchanged.

---

## Where you're buying into the monorepo

| Lock-in | Where in plan | Why it breaks multi-repo | Cheap fix now |
|---|---|---|---|
| **Packs are subpackages of the kernel's namespace** (`astrid.packs.*`) | everywhere, esp. 2.1–2.5 | Every import path, manifest entrypoint string, and doc bakes "same distribution as kernel" in. Extraction = second full migration. | Decide the namespace **before Phase 2** (see below) |
| **`_core` trust via filesystem provenance** ("canonical shipped source root") | 0.2 | "Canonical source root" is meaningless once the kernel is a wheel other repos depend on. Trust should attach to *distribution* identity, not path. | Keep the mechanism, but isolate the provenance check behind one function so it can be swapped for package-origin trust |
| **First-party inventory hardcoded in kernel code** (`_FIRST_PARTY_PACK_IDS`) | 0.3 | The framework kernel shouldn't know which packs exist — that's *product* knowledge. Other Arnold-based tools will have different inventories. | Move the list to product-layer config/data the kernel reads, not a constant in `validate_first_party.py` |
| **Git-aware tooling** (`gen_capability_index.py` filtering by tracked-ness, hygiene checker reading git paths) | 0.3, 4.3 | Ties "what ships" to "what this repo tracks." Fine for astrid-the-product; must never migrate into the framework. | Mark these scripts as product-repo tooling in the contract doc so they don't get dragged along |
| **Pack-to-pack Python imports** | 2.2 | Only works when all packs share one package tree. Cross-repo packs can't import each other's support modules without declared, versioned dependencies. | Require a `depends:` manifest field *now*, even if the checker is trivial in the monorepo |
| **All tests centralized under `tests/`** | 2.6 explicitly mandates this | A pack extracted to another repo leaves its tests behind. | Acceptable for now, but keep pack tests in per-pack subtrees (`tests/packs/<id>/`) — the plan already does this, so extraction is a `git mv` |
| **Branding literals** (`_core → astrid` in five harness files) | 0.2 preserves them | You're renaming to Arnold; branding baked into harness code multiplies the rename. Other products on the framework need their own branding. | One `BRANDING`/distribution-metadata constant instead of five literals — same test invariants, one seam |
| **`in_process.py` static core→pack exception** | 0.1 preserves it | Any static core→pack import is by definition same-repo. It's the one edge that cannot survive extraction. | Fine to keep, but note it as *the* known blocker; plan its replacement (entry-point or manifest-declared runtime bridge) as a pre-extraction task |
| **`remotion/` and `themes/` as repo-root substrate** | 0.1 | Kernel-adjacent data trees at repo root have no story once the kernel is a dependency. Are they product assets or framework assets? | Just answer the classification question in `contract.md` — no code change needed yet |

---

## The one decision to make before Phase 2: the namespace

Phases 2 and 4 are about to touch **every import path, entrypoint string, STAGE file, and test path** for the extracted domains. That's exactly the set of strings a kernel-extraction would touch again. So the real question isn't "is this plan portable" — it's **"do I want to pay the string-churn once or twice?"**

Options, roughly:

1. **Do the plan as written, extract later.** Two migrations, but each is simpler. Reasonable if extraction is >6 months out or speculative.
2. **Rename during the plan.** Move kernel code to the future name (`arnold.*` or whatever) as part of Phases 0–2, since you're touching everything anyway. Highest value if extraction is definitely happening; highest risk of scope explosion.
3. **The hedge (my recommendation): a stable facade.** Don't rename anything, but require that *all pack code* imports kernel APIs through one module (e.g., `astrid.kernel` or an SDK facade) rather than reaching into `astrid.core.pack.discovery`, `astrid.core.timeline.*`, etc. directly. Then:
   - The "stable kernel API" question from my last review gets answered mechanically — the facade *is* the API.
   - The eventual rename/extraction becomes one alias module plus a find-replace on a single prefix.
   - The import-layering checker you're already wiring into CI can enforce it for free.

This slots cleanly into the plan: it's an addition to Task 4.4's import-tiers rule ("packs import only the facade") plus a rail in 2.6.

---

## What kernel extraction would actually require (checklist)

When you do split the repo, the work is:

1. **Two distributions:** `arnold` (kernel: gateway, session, task-run, pack machinery, registries, timeline/eventlog, rendering/generation protocols, structure/doctor) and `astrid` (product: packs, inventory, branding, aliases, capability index, product docs). The plan's kernel table in `docs/packs/contract.md` (0.1) is literally the split manifest — keep it precise.
2. **Versioned contract:** semver the kernel; add a kernel-version compatibility range to `pack.yaml` (schema already versioned — good); publish a deprecation policy.
3. **Replace path/git identity with distribution identity:** `_core` provenance, first-party inventory, index generation.
4. **Ship the conformance kit:** `packs validate`, layout contract, import-layering checker, and a pytest fixture set so third-party pack repos can prove compliance without your CI.
5. **Kill or generalize `in_process.py`** into a manifest/entry-point registration mechanism.
6. **Pack dependency resolution:** `depends:` becomes real packaging metadata, not a documented courtesy.

<details>
<summary>Lesser extraction items</summary>

- **Doctor**: currently kernel-owned and the plan (correctly) refuses a doctor extension hook — but in a framework world, product-specific health checks need *somewhere* to live. That's the one place your "no new hooks" discipline will eventually bend; fine, just expect it.
- **Skills harnesses** (claude/codex/hermes): these feel framework-shaped (any Arnold product wants them) but contain product branding — the facade + branding constant handles this.
- **CI lanes / changed-file selection** (2.6): pure product-repo machinery; the framework needs its own, simpler CI. Don't try to share it.
- **`ASTRID_HOME` / env var naming**: another rename-multiplier; route env access through one config module if you haven't.

</details>

---

## Bottom line

You are **not** architecturally trapped by this plan — its contracts (manifests, hooks, discovery roots, validation) are the portable part, and it deliberately avoids the traps (new frameworks, new static imports, exemptions). What you *are* buying into is **repo-relative identity**: path-based `_core` trust, git-based inventories, one shared Python namespace, and branding literals. Every one of those has a cheap seam you can cut now — a facade module, a `depends:` field, one provenance function, one branding constant, and a "product vs. framework" column in the kernel table. Add those five seams during Phases 0–2 (while you're touching these files anyway) and the later Arnold extraction becomes a packaging exercise instead of a rewrite.
