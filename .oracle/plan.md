# SPRINTS

## Execution admission gate — astrid-first first

This plan is prepared now, but packification execution does not begin until all of the following are true:

- Astrid-first milestones m1–m8 have landed on `main`.
- The packification worktree has rebased onto that landed authority.
- The packification audit has been rerun against the rebased tree.
- The lifecycle decision is recorded:
  - **Option A:** Arnold owns `start`, `next`, `ack`, `status`, and `abort`.
  - **Option B:** astrid-first’s runs/tasks/events model wins, with no plan/session/`next`/`ack` surface.
- The losing lifecycle is scheduled for direct deletion. No selector, fallback, compatibility window, or dual runtime survives.

The `astrid scratch` decision is also recorded during Batch 0. Until that decision is made, this plan treats it as developer-only tooling, outside the eight product families.

## Sprint 1 / Sprint A — two-layer contract, canonical graph, and direct-cut foundation

Time box: approximately two delegated execution weeks, beginning only after the execution admission gate passes.

Batches/tasks:

- Batch 0: Task 0.0
- Batch 1: Task 0.1
- Batch 2: Task 0.2
- Batch 3: Task 0.3
- Batch 4: Tasks 1.1, then 1.2
- Batch 5: Task 1.3
- Batch 10a, pulled forward: Task 3.1

Eight tasks across seven batches.

Rationale:

- Batch 0 freezes the separate capability-pack and data-pack contracts against the landed astrid-first implementation before packification changes shared roots, CLI, packaging, or validation.
- Phase 2 cannot begin until Phase 1 proves the real manifest-backed capability graph and separately proves the explicitly composed data assets in source and wheel installations.
- Task 3.1 is independent of extraction and can therefore remove aliases before Phase 2 rewrites manifests and entrypoints.
- This remains the smaller effort slice. Its remaining capacity is reserved for wheel/discovery hardening and the oracle gate; pulling extraction into it would violate the hard dependency.
- One larger combined sprint would hide the most important architectural checkpoint. A third sprint would add a boundary without exposing another dependency-safe release state.

Exit criteria:

- The two layers are frozen and named:
  - capability packs: `astrid/packs/` with `pack.yaml`
  - data kernel: `astrid/data/kernel/`
  - data packs: `astrid/data/packs/{timeline,shots,references}/` with `data-pack.yaml`
  - explicit data composition: `astrid/data/composition.py`
- Capability `depends` and data `depends_on` remain distinct contracts.
- `_core` is a trusted, manifest-backed capability system pack and is unrelated to the data kernel.
- `astrid/packs/bundled.yaml` is capability-only.
- The bundled capability inventory is deterministic, packaged, and excludes `builtin` and checkout-local packs.
- Capability, skill, and element readers use the single discovered capability-pack stream.
- Data packs are explicitly registered and never activated through capability discovery.
- Wheel smoke passes outside the checkout with an empty `ASTRID_HOME`.
- Wheel smoke separately proves capability inventory and data manifests, migrations, catalogs, composition, and conformance assets.
- The lifecycle selected by the admission gate is the sole lifecycle contract; no fallback, selector, warning window, or competing ontology remains.
- `astrid serve` remains the zero-config product bootstrap.
- `runtime/in_process.py` is not an import-layer exception.
- `_IMPORT_LAYERING_EXEMPT_REL` and `_PACK_RUNTIME_BRIDGE_EXEMPT_REL` are gone.
- Pack manifests and schemas contain no capability `aliases:` field.
- `builtin`, `builtin.*`, capability aliases, `astrid author`, `astrid run`, implicit brief routing, and pure-executor shortcuts are absent.
- The eight product families are distinguished from developer capability tooling.
- `validate_import_layering()` and `validate_repo_structure()` pass with zero exemptions.
- Capability validation, data validation, generated-artifact checks, targeted tests, wheel smoke, and `scripts/reshape/run_ci_checks.sh` pass.

Oracle checkpoint:

- Batch 5 / Task 1.3 is the hard Phase 1 → Phase 2 gate.
- It passes only when capability discovery layers and wheel inventory resolve through the canonical capability graph and the separate data assets/composition pass their wheel proof.
- No 2.x task may begin before that recorded `PASS`.
- Task 3.1 runs after Batch 5 within Sprint A because it is independent of Phase 2 extraction.

Shippable means a releasable Astrid whose product domains remain in their existing locations, but whose two pack layers, loading, packaging, identity, public product families, developer capability names, and selected lifecycle already match the end state. It is not a compatibility release.

## Sprint 2 / Sprint B — extraction, repository-bound authority, and closure

Time box: approximately two delegated execution weeks.

Batches/tasks:

- Batch 6: Tasks 2.1 and 2.3
- Batch 7: Task 2.2
- Batch 8: Tasks 2.4, then 2.5
- Batch 9: Task 2.6
- Batch 10b: Task 3.2
- Batch 11: Tasks 4.1, then 4.2
- Batch 12: Tasks 4.3, then 4.4, then 4.5

Twelve tasks across seven batches.

Rationale:

- This is the heavier slice because extraction, import-policy closure, repository/materialization boundaries, private-entrypoint cleanup, dual layout enforcement, documentation, and final verification must converge.
- Tasks 2.1 and 2.3 can be delegated as independent streams.
- The Reigh inversion remains sequential: 2.4 must pass before 2.5.
- Phase 4 begins only after the Phase 3 deletion work is complete.
- Splitting closure into a third sprint would either strand transitional state or produce a boundary that is not independently shippable.

Inter-sprint dependency gate:

- Batch 5 / Task 1.3 must have a recorded `PASS`.
- Source, local, extra, environment, installed, and wheel-source capability layers must all use the canonical capability graph.
- The wheel must contain the complete bundled capability inventory.
- Data manifests, migrations, catalogs, conformance assets, and explicit composition must be packaged and smoke-tested separately.
- Sprint A’s full checkpoint, including Task 3.1, must be green before Sprint B begins.

Exit criteria:

- Generation, RunPod, Reigh remote integration, worker, and experiment implementations live only in their capability packs.
- Every static cross-capability-pack support dependency is declared, necessary, and acyclic.
- Capability `depends` is never confused with data `depends_on`.
- No capability pack imports another pack’s executor/orchestrator `run.py`.
- Every capability-to-kernel import belongs to the machine-readable supported API.
- Capabilities use the public repository/materialization boundary and never receive raw SQLite connections, writers, or UoW construction.
- `runpod` and `worker` have no top-level gateway routes.
- The old Reigh-specific serving route is absent.
- `astrid serve` remains the sole zero-config application bootstrap for database initialization, explicit data-pack composition, the local repository bridge, and editor startup.
- Legacy runtime shapes, parser fallbacks, file-backed timeline/eventlog authority, sidecar recovery authority, bridge `assets.json` migration fallback, auto-bind shims, rendering compatibility selectors, and the old hybrid-planner ID are gone.
- Pack-private commands are guarded.
- Capability-pack layout is enforced under `astrid/packs/`.
- Data-pack manifests, migrations, vocabularies, repositories, conformance declarations, and writer rules pass an independent validator.
- Documentation, generated artifacts, CI selection, wheel contents, and repository hygiene describe the actual two-layer tree.
- Full tests, wheel smoke, Remotion checks, capability validation, data validation, import rails, catalog/migration-order tests, single-writer tests, bridge tests, and clean-checkout hygiene pass.

Shippable means the complete end state: one discovered capability graph, one explicit data composition, one selected lifecycle, one canonical ID per capability, eight coherent product families, one public route per operation, one semantic writer, and no retained migration scaffolding.

# TASKLIST

## Phase 0 — freeze the layers and legalize the capability kernel

### 0.0 `[XHARD]` Freeze the two pack layers and rebase on astrid-first — Phase 0 · M · Depends: none

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

### 0.1 `[XHARD]` Lock the capability kernel, apply the lifecycle decision, and eliminate core-to-pack exceptions — Phase 0 · L · Depends: 0.0

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

### 0.2 `[XHARD]` Make `_core` a legal, manifest-backed capability system pack — Phase 0 · M · Depends: 0.1

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

### 0.3 Establish one deterministic capability inventory and delete `builtin` — Phase 0 · M · Depends: 0.2

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

## Phase 1 — one capability load graph and one explicit data composition

### 1.1 `[XHARD]` Route every capability, skill, and element reader through the canonical discovered-pack stream — Phase 1 · M · Depends: 0.2–0.3

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

### 1.2 `[XHARD]` Remove theme and workspace element discovery — Phase 1 · L · Depends: 1.1

- Remove `ElementSource`, `default_sources()`, `load_source_elements()`, active-theme element loading, `WORKSPACE_ROOT`, `legacy_workspace`, and conflict warnings.
- Build the element registry exclusively from discovered capability-pack metadata and declared roots.
- Add no pseudo-packs for theme, workspace, or data-pack directories.
- Remove discovery-only `active_theme`, `include_missing_roots`, and `elements --theme` inputs.
- Update timeline document validators, training, rendering, SDK capability discovery, and effect-registry generation to consume capability-pack metadata where appropriate.
- Keep theme selection, state, pointers, and provenance as rendering data.
- Replace positive theme/workspace discovery tests with negative no-scan rails.
- Preserve local capability-pack precedence and rendering behavior.
- Require every loaded element to report `source == "pack:<id>"`.

### 1.3 Package and prove the capability graph and data composition in wheels — Phase 1 · L · Depends: 1.1–1.2

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

## Phase 2 — extract concrete domains and bind capabilities to repositories

### 2.1 `[XHARD]` Move concrete generation backends into the generation capability pack — Phase 2 · M · Depends: 1.1, 1.3

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

### 2.2 `[XHARD]` Move experiments, declare capability dependencies, and enforce cross-layer import laws — Phase 2 · L · Depends: 0.1, 1.1

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

### 2.3 `[XHARD]` Move RunPod maintenance into its capability pack and delete the host route — Phase 2 · M · Depends: 0.1, 1.1

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

### 2.4 `[XHARD]` Bind Reigh bridge state to the landed SQLite `TimelineRepository` — Phase 2 · M · Depends: 0.1

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

### 2.5 `[XHARD]` Move Reigh remote integrations and workers into the Reigh capability pack while retaining product `serve` — Phase 2 · L · Depends: 2.4

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

### 2.6 `[XHARD]` Close extraction imports, define the pack-facing repository API, and remove CI path coupling — Phase 2 · L · Depends: 2.1–2.5

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

## Phase 3 — eliminate public aliases and residual migration machinery

### 3.1 Remove all alias surfaces and separate product navigation from developer tooling — Phase 3 · M · Depends: 1.3

Scheduled in Sprint A after Batch 5.

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

### 3.2 Delete remaining compatibility parsers and dual-path runtime support — Phase 3 · L · Depends: 2.1–2.5, 3.1

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

## Phase 4 — enforce both layouts and make the repository truthful

### 4.1 `[XHARD]` Canonicalize capability-pack-private entrypoints — Phase 4 · L · Depends: Phase 3

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

### 4.2 `[XHARD]` Enforce capability-pack layout and independently validate data packs — Phase 4 · L · Depends: 4.1

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

### 4.3 Close root-hygiene gaps and root-writing tests — Phase 4 · M · Depends: 2.1, 4.2

- Verify `fal-voice-upscale/` is absent and remove its root allowlist entry.
- Add `*.mp3` to Git ignore and tracked-runtime-media rules.
- Inspect actual root filesystem entries as well as tracked Git paths.
- Keep the hygiene checker product-repository-owned.
- Replace root-directed test output with `tmp_path`, `TemporaryDirectory()`, or system temp paths.
- Add no speculative deletion rules for absent unrelated directories.
- Do not touch `.oracle-threejs-archive/`.
- Run final hygiene from a clean checkout.

### 4.4 Complete the documentation and CI truth pass — Phase 4 · M · Depends: 4.1–4.3

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

### 4.5 Run the dual full-closure gate — Phase 4 · M · Depends: 4.1–4.4

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

# SHIM-SWEEP

The v9 sweep’s declared **20 CUT / 5 KEEP** accounting is retained. The `serve` clarification does not preserve the old Reigh-specific route: that shim remains CUT, while the product-level `astrid serve` bootstrap is a separate adopted contract.

| # | Candidate | Verdict | Reason / end state |
|---|---|---|---|
| 1 | `core/runtime/in_process.py` exception | CUT | Keep in-process execution, but resolve manifest-owned targets through the existing capability resolver and delete the static bridge exception. |
| 2 | Five-file runtime/resolver allowlist | CUT | One capability resolver owns manifest-target validation; no file-by-file permission list remains. |
| 3 | Lifecycle fallback/duality | CUT | The decision gate selects one lifecycle; the losing engine, selector, fallback, and compatibility surface are deleted. |
| 4 | Reigh-specific serving route / qualified bridge replacement | CUT | Delete the old Reigh-specific route and do not replace product bootstrap with `reigh.serve_local_bridge`; retain application-level `astrid serve`. |
| 5 | `astrid scratch` | KEEP, decision-gated | Planned as developer-only tooling, never a product family; remove directly if its gate chooses removal. |
| 6 | `builtin` and `builtin.agent_probe` | CUT | They are a compatibility namespace and regression fixture; generic behavior moves to a temporary test capability pack. |
| 7 | Capability-pack `aliases:` and alias machinery | CUT | Alternate IDs exist to smooth migration; every caller moves directly to its canonical ID. |
| 8 | `_core` → `astrid` branding seam | KEEP | Harness installation is intentionally product-branded; one centralized seam is the final capability-system-pack contract. |
| 9a | `in_process.py` extraction blocker | CUT | Solved in Task 0.1 by centralizing runtime resolution. |
| 9b | Arnold `host/shapes.py` blocker | CUT | If Arnold remains, delete the product table and compile discovered qualified orchestrators through existing lowering; otherwise delete the lifecycle host. |
| 10 | Reigh compatibility exports | CUT | Delete `event_construction.py`, integration-local `supabase_client.py`, and every residual re-export shell. |
| 11a | Deprecation windows and one-release warnings | CUT | No warning period or scheduled-removal machinery remains. |
| 11b | Capability-pack `status: deprecated` | KEEP | It is lifecycle metadata on one canonical capability ID, not a redirect or second implementation. |
| 11c | `legacy_workspace` discovery | CUT | Elements originate only from capability manifests. |
| 11d | Transitional RunPod dispatch | CUT | Delete the host route when executor parity lands; never rewire it temporarily. |
| 11e | Recorded extraction debts | CUT | Both named blockers are solved and removed from closure language. |
| 11f | Rendering support-based fallback policy | KEEP | Selecting a renderer that supports current input is capability negotiation, not legacy migration. |
| 12 | `editorial/hype/`, `golden/`, and `fixtures/` classifications | KEEP | These are truthful capability content/layout classes with no alternate route. |
| 13 | `astrid author` and `astrid run` | CUT | They duplicate canonical developer orchestration/run surfaces and are not among the eight product families. |
| 14 | Implicit `astrid --brief/--video` dispatch | CUT | It silently aliases the Hype orchestrator; require qualified developer invocation. |
| 15 | `astrid publish*` and `reigh-data` shortcuts | CUT | Canonical capability IDs already provide each operation. |
| 16 | `astrid worker` and `astrid runpod` | CUT | Remove them with the tasks that land complete capability parity. |
| 17 | Arnold `compat.py` optional surface | CUT | If Arnold wins, use one exact lazy contract loader; if it loses, delete the integration. |
| 18 | Arnold shape CLI aliases | CUT | If Arnold wins, qualified orchestrator IDs are the only accepted workflow names; otherwise the surface is absent. |
| 19 | Legacy runtime-manifest shapes and entrypoint fallback | CUT | Schemas and readers accept one canonical representation. |
| 20 | Disabled project auto-bind functions | CUT | Dead compatibility functions have no end-state role. |
| 21 | Rendering `engine` selector and `legacy_engine.py` | CUT | Require qualified backend IDs and namespaced configuration. |
| 22 | `rendering.legacy_hybrid` name | CUT | Rename directly to `rendering.hybrid`, updating all callers without an alias. |
| 23 | Forks and explicit user overrides | KEEP | They are intentional customization mechanisms, not migration redirects. |
| 24 | Video transitions and transition layout/schema terms | KEEP | “Transition” describes a media capability, not migration machinery. |
| 25 | File-backed Reigh bridge recovery, including legacy `assets.json` | CUT | `TimelineRepository` is the sole authority; no legacy representation, sidecar, or JSONL recovery path survives. |

# OPEN QUESTIONS

## Gate 1 — lifecycle contract

Must be decided before Batch 1 and, under the execution admission gate, before packification execution begins.

- **Option A — Arnold lifecycle:** retain `start`, `next`, `ack`, `status`, and `abort`; make Arnold the sole implementation and delete all fallback/legacy lifecycle machinery.
- **Option B — runs/tasks/events lifecycle:** adopt astrid-first’s direct runs/tasks/events ontology; remove plan/session/lease/`next`/`ack` surfaces and delete the Arnold lifecycle host.

No hybrid option is permitted.

## Gate 2 — `astrid scratch`

Must be decided in Batch 0 and cannot remain unresolved at Task 4.5.

- **Option A — retain developer-only:** keep `astrid scratch` as an explicitly non-product, project-scoped developer escape hatch.
- **Option B — remove:** delete it from the shipped surface with no alias or compatibility window.

The working plan carries Option A’s classification until the gate is resolved; either result preserves exactly eight product families.

# INTEGRATED

| Adopted alignment recommendation | Plan carrier |
|---|---|
| Separate capability and data-pack layers | Task 0.0; Sprint 1 exit |
| `astrid/packs/` + `pack.yaml` for capabilities | 0.0, 0.2–0.3, 1.1–1.3, 4.2 |
| `astrid/data/kernel/` and `astrid/data/packs/{timeline,shots,references}/` | 0.0, 0.1, 4.2, 4.4–4.5 |
| Separate `data-pack.yaml` | 0.0, 1.3, 4.2, 4.4–4.5 |
| Capability `depends` versus data `depends_on` | 0.0, 2.2, 4.2, 4.4–4.5 |
| Capability discovery versus explicit data registration | 0.0, 0.3, 1.1, 1.3, 4.4–4.5 |
| `astrid/data/composition.py` owns shipped `register_pack()` calls | 0.0, 1.3, 2.4–2.5, 4.4–4.5 |
| No dynamic data-pack loader, install/uninstall, environment roots, or third-party ABI | 0.0, 1.1, 4.5 |
| `astrid serve` remains the zero-config product bootstrap | Sprint exits; 0.0–0.1, 2.5, 3.1–3.2, 4.4–4.5 |
| Qualified capability tooling is developer-facing | 0.0, 3.1, 4.4 |
| Application composition owns bridge/CLI mounts | 0.0, 2.4–2.5, 4.4 |
| Bridge moves out of `astrid/core/integrations/reigh/` | 0.0, 2.4–2.5, 4.5 |
| Separate capability inventory and data package assets | 0.0, 0.3, 1.3, Sprint gates |
| astrid-first m1–m8 land before packification | Execution admission gate; 0.0 |
| Rebase and rerun the packification audit | Execution admission gate; 0.0 |
| Defer Arnold-sole-engine clause to the lifecycle gate | Admission gate; 0.1, 3.1–3.2, 4.4–4.5 |
| Keep `scratch` as developer-only in the working plan while preserving its decision | Admission gate; 0.0–0.1, 3.1, 4.5 |
| Remove file-backed timeline/eventlog authority from the capability kernel | 0.1, 2.4, 3.2, 4.5 |
| `_core` is a capability system pack, not the data kernel | 0.2, 4.4 |
| `bundled.yaml` is capability-only | 0.3, 1.3, 4.5 |
| “Every reader” is capability/skill/element-scoped | 1.1 |
| Data activation never calls `discover_pack_metadata()` | 1.1, 1.3, 4.5 |
| Wheel proves data manifests, migrations, catalogs, and conformance separately | 1.3, Sprint gates, 4.5 |
| Cross-layer import and writer rails | 2.2, 2.6, 4.2, 4.5 |
| Use landed SQLite `TimelineRepository`; create no new m6-deleted authority | 2.4 |
| Keep Reigh remote integrations in the Reigh capability pack | 2.5 |
| Public pack API includes repository/materialization services | 2.6, 4.4–4.5 |
| Capabilities never get raw SQLite writers/UoW | 2.2, 2.4, 2.6, 4.2, 4.5 |
| Preserve eight product families while eliminating aliases | 3.1, 4.4–4.5 |
| Scope capability layout validation to `astrid/packs/` | 4.2 |
| Add a small independent data validator | 4.2, 4.5 |
| Dual closure for discovered capability packs and explicitly registered data packs | 4.4–4.5 |
| Catalog, migration-order, deletion-factoring, single-writer, and bridge tests | 4.5 |
| Capability IDs/digests are opaque data metadata | 0.0, 2.6, 3.1, 4.4 |
| Freeze final capability IDs before durable dogfood fixtures | 0.0, 3.1 |
| “Media capability pack” versus “kernel media subsystem”; no media data pack | 0.0, 4.4 |
| Consistently qualify both pack and kernel meanings | 0.0, 4.4 |
| KISS/YAGNI: no grand unified pack framework | 0.0, 4.2 |

# REJECTED

None. All alignment recommendations were adopted.
