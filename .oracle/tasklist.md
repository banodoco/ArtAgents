# SPRINT 1

Frozen execution rule: execute these batches exactly as written. Do not rescope, merge, omit, or introduce compatibility releases. Any revision during execution goes through the oracle.

Source-of-truth note: the checked-in SPRINTS section contains Batch 0 / Task 0.0, making 20 tasks total—not 19. It is retained because omitting it would contradict the plan and drop an `[XHARD]` task.

# Batch 0 — Freeze the two pack layers and rebase on astrid-first · Phase 0 · Sol(XHARD)

Tasks: 0.0 `[XHARD]` Freeze the two pack layers and rebase on astrid-first.

Ownership: GPT-5.6 Sol. Delegate bounded research, mechanical implementation, and validation streams where useful; Sol retains architectural decisions, integration, and final verification.

- Begin only after astrid-first m1–m8 land on `main`, then rebase and rerun the packification audit against the landed tree.
- Freeze the physical roots:
  - capability packs: `astrid/packs/`
  - data kernel: `astrid/data/kernel/`
  - data packs: `astrid/data/packs/{timeline,shots,references}/`
  - explicit data composition: `astrid/data/composition.py`
- Freeze the manifest names:
  - capability packs use `pack.yaml`
  - data packs use `data-pack.yaml`
- Freeze dependency semantics:
  - capability `depends` declares static Python support dependencies between capability packs
  - data `depends_on` orders data-pack registration, migrations, and service availability
  - the fields are never merged, aliased, or accepted interchangeably
- Freeze activation:
  - capability packs use the existing discovery graph across source, local, extra, environment, and installed roots
  - shipped data packs are composed explicitly through `register_pack()` calls in `astrid/data/composition.py`
  - data activation never calls `discover_pack_metadata()` and gains no install/uninstall, environment-root, marketplace, or third-party loader
- Freeze CLI ownership:
  - `projects`, `media`, `tasks`, `runs`, `timelines`, `serve`, `doctor`, and `backup` are the eight product families
  - `astrid serve` is the zero-config product bootstrap
  - capability-pack, executor, orchestrator, element, skill, inspect, and qualified-run surfaces are developer tooling
  - `astrid scratch` is developer-only if retained and is never a ninth product family
- Freeze application composition:
  - the application shell owns explicit data-pack registration, CLI/bridge mounts, public service wiring, and editor startup
  - the reusable data kernel does not import product data packs or Reigh implementations
  - the thin local bridge routes through application composition and `TimelineRepository`, not `astrid/core/integrations/reigh/`
- Freeze package-data rules:
  - capability inventory packages `bundled.yaml`, `pack.yaml`, capability manifests, skills, STAGE files, and declared extension assets
  - data packaging separately includes `data-pack.yaml`, migrations, catalogs/vocabularies, repository registrations, conformance declarations/code, and explicit composition
  - data packs are never counted as bundled or discovered capability packs
- Record coordination requirements for the separately owned astrid-first initiative:
  - use the frozen `astrid/data/...` roots and `data-pack.yaml`
  - retain `depends_on` and explicit `register_pack()` composition
  - do not add capability discovery or third-party loading for data packs
  - keep the bridge outside `astrid/core/integrations/reigh/`
  - preserve `astrid serve`
  - treat capability IDs and digests as opaque data
  - invoke capabilities only through the public capability service
  - consistently qualify “capability pack” versus “data pack” and “application/capability kernel” versus “data kernel”
  - call the existing `astrid/packs/media/` package the **media capability pack** and the kernel-owned tables the **kernel media subsystem**; create no data pack named `media`
- Freeze final canonical capability IDs before astrid-first durable dogfood fixtures store them.
- Record the lifecycle decision gate with exactly two options:
  - Arnold `start/next/ack/status/abort`
  - runs/tasks/events with no plan/session/`next`/`ack`
- Record the `astrid scratch` decision gate:
  - retain as developer-only tooling
  - remove from the shipped surface
- Add no grand unified pack schema, discriminated `pack_type`, shared loader, or cross-layer abstraction.

CHECKPOINT:

- Evidence confirms astrid-first m1–m8 landed, the worktree was rebased, and the audit was rerun.
- The lifecycle and `astrid scratch` decisions are recorded and unresolved decisions block execution.
- All frozen roots and manifests exist.
- Contract evidence distinctly defines capability `depends`, data `depends_on`, capability discovery, explicit data composition, the eight product families, and `astrid serve`.
- Greps find no new unified `pack_type`, cross-layer loader, data-pack marketplace/discovery path, lifecycle selector, fallback, or dual runtime.
- Oracle records `PASS` before Batch 1.

# Batch 1 — Lock the capability kernel and eliminate core-to-pack exceptions · Phase 0 · Sol(XHARD)

Tasks: 0.1 `[XHARD]` Lock the capability kernel, apply the lifecycle decision, and eliminate core-to-pack exceptions.

Ownership: GPT-5.6 Sol, with the delegation mandate.

- Update `docs/packs/contract.md` with an authoritative application/capability-kernel table distinct from the data kernel:
  - CLI gateway and application bootstrap
  - capability pack discovery/validation/install/store
  - capability registries
  - SDK and skills installer
  - structure/doctor
  - foundation/contracts
  - provider-neutral rendering and generation protocols
  - the lifecycle selected by Task 0.0
  - public repository/materialization service contracts
- Explicitly exclude the following from the application/capability-kernel authority:
  - the 14-table reusable data kernel
  - timeline, shots, and references data-pack schemas
  - raw SQLite writers, connections, and UoW construction
  - file-backed timeline/eventlog authority
  - sidecar/event-stream recovery as persistence authority
- State that timeline capability code may produce or edit timeline documents, but persistence, CAS, receipts, events, and materialization route through the registered data repositories.
- Remove capability aliases from the kernel definition.
- Apply the recorded lifecycle decision as a direct cut:
  - If Arnold wins, make Arnold the sole engine for `start`, `next`, `ack`, `status`, and `abort`; remove the legacy engine, selector, fallback, warnings, and product-workflow table.
  - If runs/tasks/events wins, remove the plan/session/`next`/`ack` product surface and delete the Arnold lifecycle host rather than preserving an alternate engine.
- Retain no `--engine task|arnold` selector or dual-engine help under either branch.
- Port only operations meaningful to the selected lifecycle. Delete operations belonging solely to the losing lifecycle.
- If Arnold remains, replace `astrid/core/integrations/arnold/host/compat.py` with one exact lazy contract loader and delete the static product-workflow/alias table in `host/shapes.py`.
- If Arnold does not remain, delete the lifecycle integration rather than introducing compatibility naming or optional-version accommodation.
- Resolve qualified orchestrators through the discovered capability registry; add no product-shape extension framework.
- Consolidate capability runtime loading in `astrid/core/pack/resolver.py`.
- Move fresh-module loading needed by in-process execution behind that resolver, then remove:
  - `_IMPORT_LAYERING_EXEMPT_REL`
  - `_PACK_RUNTIME_BRIDGE_EXEMPT_REL`
  - the classification of `runtime/in_process.py` as a static core-to-pack bridge
- Make the structural rail reject literal `astrid.packs.*` imports/importlib targets anywhere in core and reject direct runtime-module resolution outside the resolver.
- State that concrete adapters, discoverable capabilities, product workflows, and optional service domains belong in capability packs.
- Keep `astrid scratch` classified as developer-only pending its recorded decision; if removed, delete it directly with no alias.
- Classify `astrid serve` as a permanent application-shell product contract.
- Classify `remotion/`, `themes/`, and Git-aware scripts as product-owned.
- Accept `astrid.packs.*`, `python3 -m astrid`, and `<pack>.<name>` as Astrid developer/product implementation contracts where appropriate.
- Record the zero-violation import/structure baseline and add negative tests proving no exception or static product-workflow table remains.
- Retain the extension-admission rule: use an extension only for a real core consumer with interchangeable implementations.

CHECKPOINT:

```bash
rg -n '_IMPORT_LAYERING_EXEMPT_REL|_PACK_RUNTIME_BRIDGE_EXEMPT_REL' astrid tests
rg -n 'astrid\.packs\.' astrid/core
python3 - <<'PY'
from astrid.core.structure import validate_import_layering, validate_repo_structure
assert validate_import_layering() == []
assert validate_repo_structure().errors == ()
PY
```

- Both greps return nothing.
- Only the selected lifecycle remains. Help, parsers, exports, and tests contain no engine selector, fallback, warning window, alternate host, or static product-workflow/alias table.
- `astrid/core/pack/resolver.py` is the sole runtime-target resolution boundary.
- Negative structure tests prove literal core-to-pack imports and direct runtime-module resolution fail.
- `astrid serve` remains available.

# Batch 2 — Make `_core` a manifest-backed capability system pack · Phase 0 · Sol(XHARD)

Tasks: 0.2 `[XHARD]` Make `_core` a legal, manifest-backed capability system pack.

Ownership: GPT-5.6 Sol, with the delegation mandate.

- Update `_defs.json` so `pack_id` accepts normal IDs or reserved literal `_core`; provenance remains a capability-loader concern.
- Add one `is_trusted_system_pack_source(pack_id, manifest_path)` seam.
- Accept `_core` only from the canonical shipped capability-pack source root.
- Reject user, local, extra, environment, installed, symlinked, and relative-path `_core` claims.
- Preserve folder/ID equality and reject `_core.<name>` capability IDs.
- Add `astrid/packs/_core/pack.yaml` with system metadata, its skill root, and no capabilities, dependencies, or extensions.
- State and test that `_core` is the capability system pack and is unrelated to `astrid/data/kernel/`.
- Remove manifest-less skill-shell handling from first-party and capability-layout validation.
- Add `astrid/skills/branding.py` as the single `_core` → `astrid` presentation seam.
- Consume it from Claude, Codex, Hermes, registry, CLI, and installer code.
- Preserve literal `python3 -m astrid` commands and Python package paths.
- Extend schema, loader, discovery, validation, skills, and wheel tests for canonical trust, noncanonical rejection, empty capabilities, branding invariants, and separation from the data kernel.

CHECKPOINT:

```bash
test -f astrid/packs/_core/pack.yaml
test -f astrid/skills/branding.py
python3 -m astrid packs validate astrid/packs
python3 -m pytest \
  tests/packs/test_packs_validate.py \
  tests/test_skills.py \
  tests/test_skills_sync_registry.py \
  tests/test_sdk_public_surface.py -q
```

- `_core` declares no capabilities, dependencies, or extensions.
- Canonical source trust succeeds; local, extra, environment, installed, symlinked, and relative `_core` claims fail.
- `_core.<name>` capability IDs fail.
- No manifest-less `_core` handling remains.
- Branding tests prove `astrid/skills/branding.py` is the single presentation seam.
- Wheel tests prove `_core` inclusion and separation from `astrid/data/kernel/`.

# Batch 3 — Establish deterministic capability inventory and delete `builtin` · Phase 0 · Flash

Tasks: 0.3 Establish one deterministic capability inventory and delete `builtin`.

Ownership: DeepSeek V4 Flash.

- Replace hardcoded first-party capability-pack sets with `astrid/packs/bundled.yaml`.
- Define `bundled.yaml` as capability-only.
- Include the complete tracked manifest-backed capability set, including `_core` and Blender.
- Exclude `builtin`, `discord_local`, `seedance_local`, and every data pack.
- Delete `astrid/packs/builtin/`, including `builtin.agent_probe`, build output, fixtures, and golden data.
- Replace `builtin.agent_probe` regression use with a temporary test capability pack covering the same generic orchestration behavior.
- Remove every `builtin.*` reference from manifests, tests, docs, skills, fixtures, and lifecycle state.
- Make generic first-party capability validation consume an adjacent inventory rather than embedded Astrid IDs or Git assumptions.
- Derive displayed capability counts, documentation, tests, and wheel capability parity from the inventory.
- Keep checkout-local capability packs runtime-discoverable but exclude them from committed index generation.
- Make capability-index generation select only tracked bundled capability IDs.
- Require data packs to activate only through `astrid/data/composition.py`; they never appear in `bundled.yaml`.
- Add generated-output check modes for the capability index and `_core/skill/SKILL.md`.
- Regenerate both artifacts from a clean checkout.

CHECKPOINT:

```bash
test -f astrid/packs/bundled.yaml
test ! -e astrid/packs/builtin
python3 -m astrid packs validate astrid/packs
python3 -m pytest \
  tests/packs/test_pack_layout_contract.py \
  tests/packs/test_pack_discovery_metadata.py \
  tests/packs/test_packs_validate.py \
  tests/test_skills_sync_registry.py -q
```

- `bundled.yaml` contains `_core`, Blender, and every tracked bundled capability pack.
- It contains neither `builtin`, `discord_local`, `seedance_local`, nor any data pack.
- `builtin.agent_probe` behavior is covered by a temporary test capability pack.
- Production greps for `builtin` and `builtin.*` return nothing outside explicit negative fixtures.
- Inventory counts, generated capability index, documentation, tests, and wheel parity derive from `bundled.yaml`.
- Generated-artifact check modes pass from a clean checkout.

# Batch 4 — Canonical discovery and capability-pack-only elements · Phase 1 · Sol(XHARD)

Tasks: 1.1 `[XHARD]` Route every capability, skill, and element reader through the canonical discovered-pack stream; then 1.2 `[XHARD]` Remove theme and workspace element discovery.

Ownership: GPT-5.6 Sol, with the delegation mandate. Task 1.1 must pass before Task 1.2 begins.

## Task 1.1

- Refactor capability, skills, and agent-index readers to consume ordered `DiscoveredPack` records.
- Cover source, local, extra, environment, and installed capability roots.
- Delete direct `PACKS_DIR.iterdir()` walks, manifest-less fallback, swallowed manifest errors, duplicate scanners, and the agent-index dual path.
- Fix `ASTRID_PACKS_PATH` skill discovery.
- Exclude hidden capability packs consistently from every capability layer.
- Treat `deprecated` only as capability lifecycle metadata: the pack remains discoverable under its canonical ID, with no redirect, warning window, or retained old implementation.
- Obtain skill roots only from `DiscoveredPack.skill_roots()`.
- Apply capability pack-ID deduplication once at canonical source priority.
- Preserve explicit-root testability by parameterizing shared capability discovery.
- Make invalid capability manifests fail at the capability-pack boundary and expose no capabilities, skills, or elements.
- Preserve top-level SDK laziness.
- Prove data-pack activation does not call `discover_pack_metadata()`, consume `DiscoveredPack`, or search capability roots.
- Add ordering, `_core`, duplicate, hidden-installed, deprecated-status, invalid-manifest, checkout-local, and data-nondiscovery tests.

## Task 1.2

- Remove `ElementSource`, `default_sources()`, `load_source_elements()`, active-theme element loading, `WORKSPACE_ROOT`, `legacy_workspace`, and conflict warnings.
- Build the element registry exclusively from discovered capability-pack metadata and declared roots.
- Add no pseudo-packs for theme, workspace, or data-pack directories.
- Remove discovery-only `active_theme`, `include_missing_roots`, and `elements --theme` inputs.
- Update timeline document validators, training, rendering, SDK capability discovery, and effect-registry generation to consume capability-pack metadata where appropriate.
- Keep theme selection, state, pointers, and provenance as rendering data.
- Replace positive theme/workspace discovery tests with negative no-scan rails.
- Preserve local capability-pack precedence and rendering behavior.
- Require every loaded element to report `source == "pack:<id>"`.

CHECKPOINT:

```bash
rg -n 'ElementSource|default_sources|load_source_elements|legacy_workspace|WORKSPACE_ROOT|include_missing_roots|elements --theme' astrid
python3 -m pytest \
  tests/packs/test_pack_discovery_metadata.py \
  tests/packs/test_composition_elements.py \
  tests/timeline/test_effects_catalog.py \
  tests/test_skills.py \
  tests/test_sdk_public_surface.py -q
```

- The grep returns nothing.
- Capability, skill, agent-index, and element readers consume one ordered `DiscoveredPack` stream across source, local, extra, environment, and installed roots.
- Direct pack-directory walks, duplicate scanners, manifest-less fallbacks, swallowed errors, and agent-index dual paths are absent.
- `ASTRID_PACKS_PATH`, source-priority deduplication, hidden/deprecated status, invalid-manifest atomic failure, and checkout-local behavior pass.
- Data activation never calls capability discovery.
- Every loaded element reports `source == "pack:<id>"`.
- SDK top-level laziness remains green.

# Batch 5 — Package and prove both layers in wheels · Phase 1 · Flash

Tasks: 1.3 Package and prove the capability graph and data composition in wheels.

Ownership: DeepSeek V4 Flash.

- Replace rendering-only package data with explicit capability coverage for:
  - model-catalog YAML
  - rendering schemas and parity fixtures
  - `packs/bundled.yaml`
  - capability `pack.yaml` manifests
  - executor/orchestrator manifests
  - element manifests
  - rendering extension YAML
  - pack and nested-executor skills
  - executor/orchestrator `STAGE.md`
- Add separate explicit package-data coverage for:
  - data `data-pack.yaml` manifests
  - core and data-pack migrations
  - catalogs and registered vocabularies
  - repository registrations
  - conformance declarations and required conformance code
  - `astrid/data/composition.py`
- Use no blanket recursive capability- or data-pack-root include.
- Extend wheel smoke to run outside the checkout with empty `ASTRID_HOME`.
- Prove every bundled capability ID has its canonical `pack.yaml` in the wheel.
- Prove source and wheel capability inventories agree.
- Prove data manifests, migrations, catalogs, conformance assets, and explicit composition are present without counting them as discovered capability inventory.
- Exercise representative capabilities, skills, STAGE files, extensions, model catalogs, the explicit data composition, and an empty installed capability store.
- Prove the shipped data packs register explicitly and never enter capability discovery.
- Preserve `import astrid` laziness.
- Prove capability registry loading does not eagerly import concrete generation, Reigh, RunPod, or data-pack implementations.

CHECKPOINT — hard Phase 1 → Phase 2 gate:

```bash
python3 -m astrid packs validate astrid/packs
bash scripts/smoke_wheel_install.sh
bash scripts/reshape/run_ci_checks.sh
```

- Wheel smoke builds and runs outside the checkout with a fresh, empty `ASTRID_HOME`.
- Every bundled capability ID has its canonical `pack.yaml`; source and wheel inventories are identical.
- The wheel separately contains data manifests, core/data-pack migrations, catalogs, vocabularies, repository registrations, conformance assets/code, and `astrid/data/composition.py`.
- Data packs register explicitly and never appear in capability discovery or bundled counts.
- No blanket recursive package-data include exists.
- `import astrid` remains lazy, and registry loading does not eagerly import concrete generation, Reigh, RunPod, or data-pack implementations.
- The oracle records `PASS`. No 2.x task may start without it.

# Batch 10a — Remove aliases and separate product navigation from developer tooling · Phase 3 · Flash

Tasks: 3.1 Remove all alias surfaces and separate product navigation from developer tooling.

Ownership: DeepSeek V4 Flash. This task is pulled forward and runs after Batch 5 within Sprint A.

- Freeze the eight product families:
  - `projects`
  - `media`
  - `tasks`
  - `runs`
  - `timelines`
  - `serve`
  - `doctor`
  - `backup`
- Document qualified capability execution, pack management, executors, orchestrators, elements, skills, and inspection as developer tooling rather than competing product navigation.
- Keep `astrid scratch` outside the product families if its decision gate retains it.
- Delete the capability-pack-level `aliases:` schema field, definition field, parser, normalizer, resolver, validation, and registry wiring.
- Remove `AliasRecord`, `AliasResolver`, alias-cycle logic, deprecation messages, and alias tests.
- Delete every alias declaration from shipped capability manifests, including `builtin.*`, `external.*`, `upload.youtube`, and similar alternate IDs.
- Require code, manifests, tests, skills, docs, fixtures, stored examples, and durable dogfood metadata to use final canonical qualified capability IDs directly.
- Delete the `builtin` namespace rather than redirecting it.
- Remove top-level `publish`, `publish-youtube`, `upload-youtube`, and `reigh-data`.
- Remove `astrid author` and `astrid run`.
- Remove implicit flag-first `astrid --brief/--video` routing.
- Remove Arnold CLI aliases if Arnold is retained; if it is not, remove the Arnold lifecycle surface entirely.
- Remove element-kind aliases such as `crossfade`.
- Replace `tests/test_canonical_aliases.py` with canonical-ID rejection and uniqueness tests.
- Replace the aliases/forks/overrides guide with a forks-and-overrides guide.
- Keep forks and explicit user overrides as customization contracts.
- Add negative root-help, unknown-command, schema, and manifest tests for every removed name.
- Prove all eight product families remain available and are not implemented as aliases to developer capability commands.

CHECKPOINT:

```bash
rg -n '^\s*aliases\s*:' astrid/packs -g '*.yaml' -g '*.yml'
rg -n 'AliasRecord|AliasResolver' astrid
python3 -m astrid --help
python3 -m pytest tests/test_cli_gate.py tests/test_structure_contracts.py -q
```

- Both greps return nothing.
- Root help exposes exactly the eight product families as product navigation.
- `builtin`, `publish`, `publish-youtube`, `upload-youtube`, `reigh-data`, `author`, `run`, implicit `--brief/--video`, Arnold aliases, and element-kind aliases are rejected rather than redirected.
- Canonical-ID rejection and uniqueness tests replace alias-positive tests.
- Forks and explicit user overrides remain.
- No deprecation window or compatibility release exists.

## INTER-SPRINT DEPENDENCY GATE

Sprint B is blocked until all of the following are recorded green:

- Batch 5 / Task 1.3 has an oracle-recorded `PASS`.
- Source, local, extra, environment, installed, and wheel-source capability layers use the canonical capability graph.
- The wheel contains the complete bundled capability inventory.
- Data manifests, migrations, catalogs, conformance assets, repositories, and explicit composition are separately packaged and smoke-tested.
- Batch 10a / Task 3.1 is complete.
- Every Sprint A checkpoint passes.
- Neither the lifecycle decision nor the `astrid scratch` decision is unresolved.
- No 2.x task begins before this gate.

# SPRINT 2

Sprint B begins only after the inter-sprint gate above passes. Extraction uses direct cuts: no deprecation windows, forwarding modules, transitional gateway routes, compatibility releases, fallback engines, or dual runtime paths.

# Batch 6 — Extract generation backends and RunPod maintenance · Phase 2 · Sol(XHARD)

Tasks: 2.1 `[XHARD]` Move concrete generation backends into the generation capability pack; and 2.3 `[XHARD]` Move RunPod maintenance into its capability pack and delete the host route.

Ownership: GPT-5.6 Sol, with the delegation mandate. Tasks 2.1 and 2.3 may run as independent delegated streams; Sol integrates and verifies both.

## Task 2.1

- Move Fal, Codex, and VibeComfy backends into `astrid/packs/generation/backends/`.
- Declare all three through the existing generation-backend extension.
- Delete builtin descriptor seeding and hardcoded module strings from core.
- Keep provider-neutral protocols, registry, taxonomy, verbs, and feature contracts in the capability kernel.
- Require a bare capability registry to be empty and default loading to come only from capability manifests.
- Remove concrete core exports and lazy concrete imports.
- Update generation executors, unavailable-reason handling, tests, SDK capability discovery, gateway resolution, and model validation.
- Delete all tracked `fal-voice-upscale/` files.
- Move adapter tests under `tests/packs/generation/`.
- Add negative tests for old core paths and literal module strings.
- Prove wheel capability discovery gains and loses all three backends with the generation manifest.
- Require generated outputs to cross the public repository/materialization boundary before becoming semantic project authority.

## Task 2.3

- Move RunPod storage and sweeper implementations into the RunPod capability pack.
- Add `runpod.sweep`, `runpod.list_volumes`, and `runpod.ensure_storage`.
- Add no core RunPod protocol, extension, or doctor hook.
- Preserve dry-run diagnostics and storage-recovery behavior.
- Delete top-level `astrid runpod`, `astrid/core/gateway/runpod.py`, dispatch functions, help, exports, and allowlist entries in this task.
- Do not temporarily rewire the old route.
- Remove RunPod checks from core doctor and cover the executor instead.
- Keep `require_existing_storage` pack-local.
- Give training a local diagnostic pointing directly to `runpod.ensure_storage`.
- Remove `astrid/core/integrations/runpod/` after imports move.
- Relocate and retarget tests.
- Add no structure exemption.

CHECKPOINT:

```bash
test ! -e fal-voice-upscale
test ! -e astrid/core/gateway/runpod.py
test ! -e astrid/core/integrations/runpod
python3 -m pytest \
  tests/packs/generation \
  tests/packs/runpod \
  tests/core/test_generation_backend_registry.py -q
python3 -m astrid packs validate astrid/packs
bash scripts/smoke_wheel_install.sh
```

- Fal, Codex, and VibeComfy backends exist only under the generation capability pack and appear or disappear with its manifest.
- A bare registry is empty; core contains no concrete descriptor seeding, exports, lazy imports, or hardcoded backend module strings.
- `runpod.sweep`, `runpod.list_volumes`, and `runpod.ensure_storage` exist.
- Top-level `astrid runpod`, its gateway/dispatch/export/allowlist, core doctor hook, and core integration are absent.
- No forwarding route or structure exemption exists.
- Generated outputs cannot become semantic authority before repository materialization.

# Batch 7 — Extract experiments and enforce dependency/import laws · Phase 2 · Sol(XHARD)

Tasks: 2.2 `[XHARD]` Move experiments, declare capability dependencies, and enforce cross-layer import laws.

Ownership: GPT-5.6 Sol, with the delegation mandate.

- Add optional sorted, unique capability `depends` pack IDs for static Python support dependencies.
- Keep capability `depends` distinct from external dependencies, capability composition, and data `depends_on`.
- Reject malformed, duplicate, self, cyclic, undeclared, missing, and stale capability dependencies.
- Keep data `depends_on` limited to explicit registration, migration, and service ordering.
- Add `astrid/core/pack/import_policy.py` and its test suite.
- Inventory all static and literal-dynamic cross-capability-pack imports.
- Classify each edge as capability invocation, genuine support dependency, or accidental/private coupling.
- Replace execution dependencies with qualified capability dispatch.
- Forbid importing another capability pack’s executor/orchestrator `run.py`, even with `depends`.
- Move genuinely shared symbols into narrow owning-pack support modules.
- Declare surviving edges such as editorial → training, video_editing → editorial, and editorial → iteration.
- Move `astrid/core/experiments/` directly to `astrid/packs/iteration/experiments/`.
- Delete the old path and update all consumers atomically.
- Move experiment tests under `tests/packs/iteration/experiments/`.
- Add independent cross-layer rails:
  - `astrid/data/kernel/` may not import `astrid/data/packs/`
  - capability code may not construct raw SQLite connections, writers, transactions, or UoWs
  - capability code may not bypass repository/materialization services
  - data packs may refer across packs only through kernel-owned IDs and declared `depends_on`
- Finish with no known violation deferred.

CHECKPOINT:

```bash
test -f astrid/core/pack/import_policy.py
test ! -e astrid/core/experiments
test -d astrid/packs/iteration/experiments
test -d tests/packs/iteration/experiments
python3 -m astrid packs validate astrid/packs
```

- Capability `depends` rejects malformed, duplicate, self, cyclic, undeclared, missing, and stale edges.
- The capability graph is sorted, complete, necessary, and acyclic.
- No capability pack imports another pack’s executor/orchestrator `run.py`.
- All cross-pack static and literal-dynamic edges are classified and declared.
- Independent negative tests reject data-kernel upward imports/FKs, raw SQLite connections/writers/transactions/UoWs in capabilities, repository bypasses, and undeclared cross-data-pack references.
- No known violation is deferred.

# Batch 8 — Bind Reigh to `TimelineRepository` and extract remote/worker implementations · Phase 2 · Sol(XHARD)

Tasks: 2.4 `[XHARD]` Bind Reigh bridge state to the landed SQLite `TimelineRepository`; then 2.5 `[XHARD]` Move Reigh remote integrations and workers into the Reigh capability pack while retaining product `serve`.

Ownership: GPT-5.6 Sol, with the delegation mandate. Task 2.4 must pass before Task 2.5 begins.

## Task 2.4

- Use the `TimelineRepository` landed by astrid-first as the sole timeline persistence boundary.
- Do not create `astrid/core/timeline/asset_registry_state.py`.
- Do not add file-event recovery, sidecar repair, record/source merge authority, or any other authority scheduled for deletion by astrid-first m6.
- Route bridge timeline list/load/save and CAS through application composition and `TimelineRepository`.
- Preserve the existing editor wire contract while repository operations atomically commit the timeline document, registry, event, stream/project head, receipt, and change cursor.
- Treat stale CAS as no mutation and preserve the frozen conflict/error envelopes.
- Route reconciliation and materialization through the repository/service layer, never through legacy `assets.json`, JSONL, or sidecar authority.
- Keep raw SQLite connections, writer queues, transaction creation, and UoW construction internal to the data kernel.
- Prove bridge handlers and capability callers receive only public repository/service interfaces.
- Replace file-authority recovery tests with repository CAS, receipt replay, mismatch rejection, crash-boundary, restart, reconciliation, and single-writer tests.
- Add no Reigh registry or data extension.

## Task 2.5

- Move Reigh environment, provider, remote transport, task client, remote timeline client, JWT/JWKS, append service, errors, and worker implementations into the Reigh capability pack.
- Delete `astrid/core/integrations/reigh/` and `astrid/core/integrations/worker/`.
- Delete `event_construction.py`, integration-local `supabase_client.py`, and every compatibility export or copy.
- Add canonical `reigh.worker`.
- Keep Reigh-specific remote provider and worker integrations in the Reigh capability pack.
- Retain top-level `astrid serve` as the application-shell bootstrap.
- Make `astrid serve`:
  - lazily initialize/migrate the application database and data directories
  - explicitly register the shipped data packs through `astrid/data/composition.py`
  - start the repository-backed local bridge
  - open the packaged/current editor
- Do not add or retain `reigh.serve_local_bridge` as a competing public invocation.
- Delete only the old Reigh-specific remote-serving gateway/dispatch path.
- Delete top-level `astrid worker`; retain no sessionless worker host adapter.
- Route local timeline edits through the `timelines` product service and `TimelineRepository`, not a new Reigh capability.
- Preserve PAT defaults, optional service-role authentication, optimistic versioning, three retries, `force=False`, and event descriptors for surviving remote integrations.
- Remove remote `projects list` and `projects edit`.
- Delete `scripts/node/ops_helper.mjs`.
- Keep local project services and data-pack-mounted timeline commands behind the repository service layer.
- Ensure the capability/application kernel contains no Reigh implementation import or hardcoded Reigh module string.

CHECKPOINT:

- Before Task 2.5, repository CAS, receipt replay, mismatch rejection, crash-boundary, restart, reconciliation, single-writer, stale-save conflict, and draft-safety tests pass through `TimelineRepository`.
- Bridge handlers and capabilities receive only public repository/service interfaces.
- No `asset_registry_state.py`, file-event recovery, sidecar repair, JSONL authority, or legacy `assets.json` authority exists.

```bash
test ! -e astrid/core/integrations/reigh
test ! -e astrid/core/integrations/worker
test ! -e scripts/node/ops_helper.mjs
rg -n 'reigh\.serve_local_bridge|astrid worker' astrid tests docs
python3 -m pytest tests/packs/reigh tests/integrations/reigh -q
python3 -m astrid --help
```

- The grep returns nothing outside explicit negative tests.
- Reigh remote/provider/worker implementations exist only in the Reigh capability pack.
- Canonical `reigh.worker` exists.
- `astrid serve` initializes/migrates data, invokes explicit data composition, starts the repository-backed bridge, and opens the editor.
- No competing Reigh serving route, top-level worker route, compatibility copy, or core Reigh module string survives.

# Batch 9 — Close extraction imports and remove CI path coupling · Phase 2 · Sol(XHARD)

Tasks: 2.6 `[XHARD]` Close extraction imports, define the pack-facing repository API, and remove CI path coupling.

Ownership: GPT-5.6 Sol, with the delegation mandate.

- Move all Reigh implementation tests under `tests/packs/reigh/`.
- Keep provider-neutral repository and data-kernel tests under the data/timeline test suites.
- Document `tests/packs/<id>/` as the capability extraction rail.
- Replace positive implementation inventories with negative absence rails.
- Require no live `astrid.core.integrations.{reigh,runpod,worker}` imports.
- Inventory every remaining capability-pack-to-kernel import.
- Enforce exact machine-readable supported capability-kernel module prefixes.
- Support only provider-neutral contracts and explicitly public foundation, execution, capability discovery, runtime, generation, rendering, repository/materialization, and lineage APIs consistent with the selected lifecycle.
- Include the public repository/materialization service in the supported pack API:
  - capability outputs remain quarantined until repository materialization
  - capability IDs and digests are opaque metadata to the data layer
  - capabilities receive service methods and typed results, not SQLite handles
- Reject `_shared`, private symbols, CLI handlers, concrete implementations, raw SQLite writers/connections/UoWs, and blanket utility families.
- Promote genuinely shared helpers into existing public modules or make them pack-local.
- Define the supported surface as a current contract; update every first-party caller atomically when it changes, with no alias or deprecation window.
- Wire the capability import checker and cross-layer writer checker into CI with zero exemptions.
- Make changed-file selection arbitrary-depth under `astrid/**`.
- Update the bridge workflow for the actual application bridge and surviving `astrid/packs/reigh/**` remote integrations.
- Keep all moved tests discoverable under `tests/`.

CHECKPOINT:

```bash
rg -n 'astrid\.core\.integrations\.(reigh|runpod|worker)' astrid tests
python3 -m pytest tests/packs/reigh tests/test_structure_contracts.py tests/reshape -q
bash scripts/reshape/run_ci_checks.sh
```

- The grep returns no production or positive-test matches.
- Reigh implementation tests live under `tests/packs/reigh/`; provider-neutral tests remain in data/timeline suites.
- Every capability-to-kernel import is inventoried and belongs to exact machine-readable public prefixes.
- `_shared`, private symbols, CLI handlers, concrete implementations, raw SQLite access, and blanket utility namespaces are rejected.
- Capability import and cross-layer writer checks run in CI with zero exemptions.
- Changed-file selection recognizes arbitrary depth under `astrid/**`.
- All moved tests remain discoverable.

# Batch 10b — Delete remaining compatibility parsers and dual runtime paths · Phase 3 · Flash

Tasks: 3.2 Delete remaining compatibility parsers and dual-path runtime support.

Ownership: DeepSeek V4 Flash.

- Delete `runtime_command_legacy` and require one canonical runtime-manifest shape.
- Delete fallback parsing of legacy agent entrypoints; require `agent.normal_entrypoints`.
- Delete the legacy flat manifest parser; use the canonical YAML/JSON loader only.
- Delete disabled project auto-bind compatibility functions.
- Remove rendering’s `engine` selector, neutral alias-to-engine translation, `legacy_engine.py`, and legacy argument adaptation.
- Require qualified renderer/planner/finalizer IDs and namespaced backend configuration.
- Rename the load-bearing hybrid planner directly from `rendering.legacy_hybrid` to `rendering.hybrid`; update callers, fixtures, schemas, and provenance atomically, with no alias.
- Delete obsolete sibling-output compatibility parameters and re-export shells.
- Verify RunPod and worker host routes have not survived through help, exports, tests, or docs.
- Verify the old Reigh-specific serving route has not survived.
- Preserve `astrid serve` and prove it routes only through application composition and repository services.
- Remove warning-window and sunset-version machinery.
- Remove all compatibility machinery belonging to the lifecycle rejected by Task 0.0.
- Add a scoped repository rail rejecting compatibility shims, alias bridges, legacy runtime shapes, file-backed bridge authority, and duplicate public routes.

CHECKPOINT:

```bash
rg -n 'runtime_command_legacy|legacy_engine|rendering\.legacy_hybrid|reigh\.serve_local_bridge' astrid tests docs
python3 -m pytest tests/test_schema_contract.py tests/test_structure_contracts.py tests/core/rendering tests/packs/rendering -q
python3 -m astrid --help
```

- The grep returns nothing outside explicit negative fixtures.
- Only `agent.normal_entrypoints`, the canonical YAML/JSON manifest loader, qualified rendering IDs, and namespaced backend configuration remain.
- `rendering.hybrid` replaces `rendering.legacy_hybrid` atomically, without an alias.
- RunPod, worker, and old Reigh serving routes are absent from help, exports, tests, and docs.
- `astrid serve` routes only through application composition and repository services.
- The repository rail rejects compatibility shims, alias bridges, old runtime shapes, file-backed authority, and duplicate public routes.

# Batch 11 — Canonicalize private entrypoints and validate both layouts · Phase 4 · Sol(XHARD)

Tasks: 4.1 `[XHARD]` Canonicalize capability-pack-private entrypoints; then 4.2 `[XHARD]` Enforce capability-pack layout and independently validate data packs.

Ownership: GPT-5.6 Sol, with the delegation mandate. Task 4.1 must pass before Task 4.2 begins.

## Task 4.1

- Convert `blender/deploy.py` into canonical `blender.deploy`.
- Keep mesh fetching as private `blender.render` support; remove its independent CLI.
- Move Blender render/server support beneath owning executor trees.
- Remove alternate `__main__` surfaces.
- Update Blender manifests, skills, STAGE files, docs, presets, imports, and tests.
- Keep rendering backend/planner/finalizer runners as manifest-private transport commands, including `rendering.hybrid`.
- Have core rendering transport set the internal-invocation marker.
- Reject direct subprocess invocation while allowing manifest transport.
- Remove the unsupported `python -m astrid.sdk.rendering` claim.
- Remove executable behavior from unledgered generation golden demos.
- Add canonical-success/direct-module-failure subprocess rails.
- Search for stale `python -m astrid.packs.*` instructions, permitting only exact manifest-private commands.

## Task 4.2

- Scope capability-pack layout validation strictly to `astrid/packs/`.
- Make capability layout validation walk actual capability-pack-root entries.
- Permit only:
  - `pack.yaml`
  - declared capability roots
  - `skill/`, `docs/`, `examples/`, `schemas/`, `fixtures/`, `golden/`
  - capability-local golden fixtures
  - Python package markers
  - declared extension roots
  - narrowly documented declared support-library roots
- Keep `editorial/hype/` as declared library-only support and prove it has no discovery or CLI surface.
- Keep rendering’s declared backend/planner/finalizer extension roots.
- Reject undeclared loose files and directories with actionable paths.
- Move Fal tests under `tests/packs/fal/`.
- Add positive editorial/rendering/fixture/golden tests and negative junk-layout cases.
- Add a small independent validator for `astrid/data/` that validates:
  - `data-pack.yaml`
  - unique data-pack identity/version
  - `depends_on` validity and migration order
  - declared migrations and checksums
  - registered stream/event/command vocabularies
  - repository registration
  - conformance declarations
  - CLI/bridge mounts
  - kernel-to-pack import/FK prohibition
  - cross-data-pack reference rules
  - raw-writer and pack-owned-transaction prohibition
- Do not teach capability layout validation about data migrations or teach data validation about executors, orchestrators, elements, capability skills, or `bundled.yaml`.
- Add no common discriminated pack schema.

CHECKPOINT:

```bash
rg -n 'python(3)? -m astrid\.packs\.' . \
  -g '!*.pyc' -g '!*.lock'
rg -n 'python(3)? -m astrid\.sdk\.rendering' astrid docs tests
python3 -m astrid packs validate astrid/packs
python3 -m pytest \
  tests/packs/test_pack_layout_contract.py \
  tests/packs/test_packs_validate.py \
  tests/test_structure_contracts.py \
  tests/packs/rendering -q
```

- Task 4.1 passes first: `blender.deploy` is canonical, mesh fetching is private support, alternate `__main__` surfaces are gone, and manifest-private transports accept only marked internal invocation.
- The first grep contains only exact ledgered manifest-private commands; the second returns nothing.
- Canonical-success/direct-module-failure subprocess rails pass.
- Capability validation walks only actual entries under `astrid/packs/`, accepts only declared content classes, and rejects undeclared junk with actionable paths.
- Editorial support and rendering extension roots obey their restricted contracts.
- Fal tests live under `tests/packs/fal/`.
- The independent data validator passes identity/version, `depends_on`, migration/checksum, vocabulary, repository, conformance, mount, import/FK, cross-reference, and writer/transaction checks.
- Neither validator understands the other layer’s concepts, and no shared discriminated pack schema exists.

# Batch 12 — Close hygiene, documentation, CI truth, and full verification · Phase 4 · Flash

Tasks: 4.3 Close root-hygiene gaps and root-writing tests; then 4.4 Complete the documentation and CI truth pass; then 4.5 Run the dual full-closure gate.

Ownership: DeepSeek V4 Flash. Execute strictly in the order 4.3 → 4.4 → 4.5.

## Task 4.3

- Verify `fal-voice-upscale/` is absent and remove its root allowlist entry.
- Add `*.mp3` to Git ignore and tracked-runtime-media rules.
- Inspect actual root filesystem entries as well as tracked Git paths.
- Keep the hygiene checker product-repository-owned.
- Replace root-directed test output with `tmp_path`, `TemporaryDirectory()`, or system temp paths.
- Add no speculative deletion rules for absent unrelated directories.
- Do not touch `.oracle-threejs-archive/`.
- Run final hygiene from a clean checkout.

## Task 4.4

- Document the exact application/capability kernel and the separate data kernel.
- Document the selected sole lifecycle; remove claims belonging to the rejected lifecycle.
- Document the eight product families and distinguish developer capability tooling.
- Document `astrid serve` as the product bootstrap.
- Document the supported capability-pack API, including the repository/materialization boundary.
- Document capability `depends` and data `depends_on` as separate fields with separate semantics.
- Document capability discovery versus explicit data registration.
- Document application composition and the three explicit `register_pack()` calls.
- Document no capability-kernel-to-capability-pack exceptions and no data-kernel-to-data-pack upward imports.
- Document no static lifecycle product-shape table.
- Document `_core` as the capability system pack, unrelated to the data kernel, and the absence of `builtin`.
- Document data packs as explicitly registered rather than installed/discovered.
- Document data manifests, migrations, vocabularies, repositories, conformance, and single-writer rules.
- Document capability IDs/digests as opaque data-layer metadata.
- Consistently distinguish:
  - capability pack versus data pack
  - application/capability kernel versus data kernel
  - media capability pack versus kernel media subsystem
- Remove alias-carrier, compatibility-window, fallback-engine, Reigh-specific serving-route, and extraction-debt language.
- Document hidden and deprecated capability status without implying redirects or retained old implementations.
- Correct repository shape, execution paths, gateway modules, application composition, and SDK export count.
- Document capability-only discovery and qualified developer capability routes.
- Document `rendering.hybrid` and remove the old planner ID.
- Update Generation, Iteration, Reigh, RunPod, YouTube, Blender, rendering, data, and `_core` skills/manifests/STAGE files.
- Update integration contracts to use `astrid serve` for the local application/editor bootstrap.
- Update CI-lane documentation and command verification for both validators.
- Regenerate `_core/skill/SKILL.md`.
- Search for stale domain paths, aliases, `builtin`, removed host verbs, old lifecycle surfaces, legacy runtime/bridge authority, old planner IDs, direct pack commands, and old exception language.

## Task 4.5

- Run capability-pack validation.
- Run the independent data-pack/kernel validator.
- Run schema, dependency/import-policy, capability discovery, skills, elements, structure, gateway, doctor, generation, iteration, Reigh, RunPod, rendering, layout, CI-selection, and hygiene tests.
- Run data catalog, migration-order, vocabulary-registration, repository, conformance, deletion-factoring, single-writer, raw-writer-denial, and bridge tests.
- Run wheel smoke outside the checkout with empty `ASTRID_HOME`.
- Run `scripts/reshape/run_ci_checks.sh` and the broad suite.
- Run Remotion typechecking and renderer-parity tests.
- Require zero import-layer exemptions.
- Require no runtime-resolver file allowlist.
- Require a complete, non-stale, acyclic capability `depends` graph.
- Require a valid explicitly composed data `depends_on` graph and deterministic migration order.
- Require no cross-capability-pack executor/orchestrator entrypoint imports.
- Require every capability-pack-to-kernel import to belong to the supported API.
- Require `astrid/data/kernel/` to have no imports or FKs into data packs.
- Require capabilities to have no raw SQLite writer, connection, transaction, or UoW access.
- Require capability outputs to reach semantic authority only through repository materialization.
- Run generated-artifact check modes.
- Prove no shipped capability manifest contains `aliases:`.
- Prove `builtin`, `builtin.*`, removed gateway verbs, dual lifecycle selection, old runtime shapes, `rendering.legacy_hybrid`, old core-domain paths, file-backed timeline/eventlog authority, and legacy bridge `assets.json` recovery are absent outside explicit negative fixtures.
- Prove the lifecycle rejected by Task 0.0 is absent.
- Prove `runtime/in_process.py` and any retained lifecycle host contain no product-specific exception or workflow table.
- Prove every capability, skill, element, and concrete generation backend originates from a manifest-backed discovered capability pack.
- Prove every shipped data pack originates from the explicit `astrid/data/composition.py` registration and never enters capability discovery.
- Prove the composed catalog equals the data kernel catalog plus the tables declared by the explicitly registered data packs.
- Prove core and data-pack migrations apply independently and in declared order.
- Prove deleting a data pack from the source composition leaves the data-kernel suite green.
- Prove every data-pack command passes replay, mismatched-key, crash-boundary, same-project, and single-writer conformance.
- Prove the existing editor bridge list/load/save/reload, stale-save conflict, restart, and draft-safety tests pass through `TimelineRepository`.
- Prove `astrid serve` remains available and no competing Reigh-specific public serving route exists.
- Prove `astrid/core/integrations/` contains no Reigh, RunPod, or worker implementation.
- Verify moved capability tests follow `tests/packs/<id>/`.
- Verify clean-checkout indexing and hygiene without touching `.oracle-threejs-archive/`.
- Refuse final `PASS` while either lifecycle or `astrid scratch` decision remains unresolved.

CHECKPOINT — final closure:

```bash
test ! -e fal-voice-upscale
rg -n '^\s*aliases\s*:' astrid/packs -g '*.yaml' -g '*.yml'
rg -n '_IMPORT_LAYERING_EXEMPT_REL|_PACK_RUNTIME_BRIDGE_EXEMPT_REL' astrid tests
rg -n 'astrid\.core\.integrations\.(reigh|runpod|worker)' astrid tests
rg -n 'rendering\.legacy_hybrid|runtime_command_legacy|legacy_engine' astrid tests docs

python3 -m astrid packs validate astrid/packs
bash scripts/smoke_wheel_install.sh
bash scripts/reshape/run_ci_checks.sh
python3 -m pytest --tb=no -q --no-header -m 'not integration and not opt_in'

python3 - <<'PY'
from astrid.core.structure import validate_import_layering, validate_repo_structure
assert validate_import_layering() == []
assert validate_repo_structure().errors == ()
PY

cd remotion
npm run typecheck
```

- Every absence grep returns nothing outside explicit negative fixtures.
- The independent data-pack/kernel validator passes.
- Capability and data dependency graphs are valid, deterministic, non-stale, and acyclic.
- There are zero import-layer exemptions and no runtime-resolver file allowlist.
- No cross-capability entrypoint imports, unsupported kernel imports, data-kernel upward imports/FKs, or raw capability SQLite/UoW access remain.
- Generated-artifact check modes and renderer-parity tests pass.
- Every capability, skill, element, and concrete generation backend comes from a manifest-backed discovered capability pack.
- Every shipped data pack comes only from `astrid/data/composition.py` and never enters capability discovery.
- Catalog composition, migration independence/order, deletion factoring, data command conformance, single-writer behavior, and all `TimelineRepository` bridge scenarios pass.
- `astrid serve` remains the sole zero-config application bootstrap; no competing Reigh-specific public serving route exists.
- `astrid/core/integrations/` contains no Reigh, RunPod, or worker implementation.
- Moved tests follow `tests/packs/<id>/`.
- Clean-checkout indexing and hygiene pass without touching `.oracle-threejs-archive/`.
- Final `PASS` is forbidden while either the lifecycle decision or the `astrid scratch` decision remains unresolved.
- This is the complete direct-cut end state: no deprecation windows, compatibility releases, aliases, fallback engines, dual runtimes, or retained migration scaffolding.
