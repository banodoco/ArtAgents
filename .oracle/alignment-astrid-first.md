# DOC 2 — `.oracle/alignment-astrid-first.md`

## Packification ↔ astrid-first data model: alignment analysis

### Verdict

The efforts are **philosophically aligned but operationally misaligned**. Both want a narrow reusable kernel, one-way dependencies, explicit contracts, no speculative abstractions, and proof before promotion. But their executable plans currently contradict each other on physical roots, manifest contracts, activation, timeline authority, lifecycle semantics, `astrid serve`, and the public CLI. This needs a plan revision before packification execution; it is not merely a merge-conflict problem.

The smallest coherent design is to keep the concepts separate and name them precisely:

```text
astrid/
  core/                     # application/capability kernel
  packs/                    # discoverable capability/content packs
  data/
    kernel/                 # agent-agnostic 14-table data kernel
    packs/
      timeline/
      shots/
      references/
    composition.py          # explicit shipped register_pack(...) calls
```

Capability packs retain the existing `pack.yaml`, discovery graph, `bundled.yaml`, and `<pack>.<name>` identities. Data packs use a separate validated manifest—preferably `data-pack.yaml`—and remain explicitly composed, not dynamically discovered. This is smaller than teaching every capability reader, installer, indexer, and layout validator about authoritative schema migrations. M1 already allows an equivalent physical layout (`.oracle/inputs/astrid-first/m1.md:63`).

### What aligns

| Principle | Packification | Astrid-first |
|---|---|---|
| Narrow kernel | Concrete adapters, product workflows, and optional domains belong in packs; extensions require a real core consumer with interchangeable implementations (`.oracle/plan.md:125-131`). | Timeline, shots, and references remain outside the 14-table kernel until reuse is demonstrated (`NORTHSTAR.md:19,27-30`). |
| No upward dependency | Core may not import `astrid.packs.*` except through the resolver; final state has zero exemptions (`.oracle/plan.md:119-130`). | Kernel tables/code never depend on pack tables/code; pack FKs point inward only (`unified-data-model-plan-v10-20260813.md:156-164,649-650`). |
| One authority | One lifecycle engine and one canonical route per capability (`.oracle/plan.md:25-46,79-92`). | One database, writer queue, UoW, and `BEGIN IMMEDIATE`; packs never own a writer (`NORTHSTAR.md:28,31,35`). |
| Proof accompanies extension | Pack schemas, wheel smoke, import rails, and layout validation prove conformance (`.oracle/plan.md:191-209,401-420`). | Every data-pack command passes replay, mismatch, crash, and same-project conformance (`NORTHSTAR.md:30`; v10 `:651-656`). |
| Generalize only after evidence | Do not add extension frameworks without a real interchangeable core consumer (`.oracle/plan.md:118,131`). | Promote a table only after two real compositions prove the common need (`NORTHSTAR.md:19,29`). |
| Portability is a seam, not today’s platform | The external review identifies manifests, multi-root discovery, validation, and wheel proofs as portable bones (`openrouter-sensecheck.md:414-420`). | “Boundary now, loader later”: extract or add a loader only when a second agent is real (`unified-data-master-plan-20260814.md:246-259`). |

### Conflicts and collisions

| # | Surface | Packification says | Data model says | Impact |
|---:|---|---|---|---|
| 1 | Pack tree | Every real directory under `astrid/packs/` must be a valid capability pack and obey the capability layout contract (`.oracle/plan.md:147-160,357-372`). | Establish `core/` plus `packs/{timeline,shots,references}` or equivalent (`m1.md:23,63`). | Landing data packs directly under `astrid/packs/` makes them invalid capability packs or accidentally discoverable capabilities. Use `astrid/data/packs/`. |
| 2 | Meaning of “core” | `astrid/core/` includes CLI, sessions/projects, run state, discovery, registries, timeline/eventlog, protocols, and Arnold (`.oracle/plan.md:98-131`). | “Core” is the reusable 14-table data substrate (`NORTHSTAR.md:15,19,23`). | Two unrelated roots called `core` would obscure ownership and import laws. Call the new layer `astrid/data/kernel/`. |
| 3 | Manifest shape | Capability `pack.yaml` declares identity, capabilities, content, extensions, permissions, and agent metadata. | Data manifests declare migrations, vocabularies, repositories, conformance, and CLI/bridge mounts (`unified-data-master-plan-20260814.md:82-96`). | These have different trust and validation requirements. A separate data manifest is simpler than a large discriminated union today. |
| 4 | Dependency fields | `depends` is a static Python support dependency between capability packs; execution should use capability dispatch (`.oracle/plan.md:227-242`). | `depends_on` orders data-pack registration, migrations, and service availability (`unified-data-master-plan-20260814.md:84-94,415-419`). | The fields must not be merged or treated as aliases. |
| 5 | Discovery and activation | One `DiscoveredPack` stream covers source, local, extra, environment, and installed capability roots (`.oracle/plan.md:164-177`). | Only the three trusted in-tree data packs are registered by explicit `register_pack()`; no loader ships at GA (`m1.md:23,36`; v10 `:152-154`). | Scope “one graph” to capabilities, skills, elements, and concrete backends. Data registration remains explicit. |
| 6 | Timeline authority | Task 0.1 keeps “timeline/eventlog” in the kernel; Tasks 2.4–2.6 retain generic file-event recovery, sidecars, and local timeline commands (`.oracle/plan.md:100-110,259-291`). | `timelines` belongs to the timeline data pack; document, registry, event, head, and receipt commit atomically in SQLite (`v10:408-417,529-550`). Old file authority is deleted at m6 (`NORTHSTAR.md:50`). | Packification would otherwise formalize machinery scheduled for deletion. Tasks 0.1 and 2.4–2.6 must be rewritten after astrid-first. |
| 7 | Timeline capability | Video-editing executors such as cut, hype, and iteration stay capability packs. | The timeline data pack owns persistence and CAS. | No conflict if named correctly: capability code produces or edits timeline documents; the data pack persists them through repositories. A capability never owns the SQLite writer. |
| 8 | Lifecycle ontology | Arnold becomes the sole engine for `start`, `next`, `ack`, `status`, and `abort` (`.oracle/tasklist.md:24-35`). | V10 removes plans, steps, sessions, leases, `next`, `ack`, and hooks; runs directly group immutable tasks (`v10:12-18,67-88,638-657`). | This is the largest contradiction. Task 0.1 cannot execute unchanged. The user must choose the final lifecycle contract. |
| 9 | `astrid serve` | Task 2.5 deletes the top-level route; only `executors run reigh.serve_local_bridge` remains (`.oracle/tasklist.md:356-368`). | `astrid serve` is the zero-config entry point and one of exactly eight product families (`NORTHSTAR.md:15`; v10 `:591-604`). | Keep `astrid serve` as a thin application-shell bootstrap. It is not a compatibility alias. Provider-specific implementation can still live outside core. |
| 10 | Product CLI | Packification centers qualified capability routes and deletes competing host routes (`.oracle/plan.md:79-92`). | V10 freezes eight product families; capability and pack tooling is developer-facing (`v10:591-606`). | Qualified execution can coexist with the product CLI, but it should be documented as a developer/capability surface rather than product navigation. |
| 11 | Bridge ownership | Packification moves Reigh transport and worker implementations into the Reigh capability pack (`.oracle/plan.md:271-286`). | M1 places a thin bridge at `astrid/core/integrations/reigh/local_bridge_server.py` (`m1.md:61-64`). | Do not knowingly create a core Reigh module that packification immediately moves. Put the frozen adapter at the application/data composition boundary; keep repositories in the data packs. |
| 12 | Package inventory | Task 1.3 proves capability manifests and source/wheel inventory parity (`.oracle/tasklist.md:169-198`). | The installed artifact must also contain data migrations, catalogs, conformance code, and explicit composition (`m1.md:19-29,57-64`). | Add separate wheel assertions for data assets without calling them discovered capability inventory. |
| 13 | Stored capability IDs | Packification deletes aliases and changes callers to final canonical IDs (`.oracle/plan.md:308-324`). | `tasks.capability` and task/run metadata retain capability IDs or digests (`v10:291-305`; `:84,124`). | Data treats these as opaque strings and never imports capability packs. Final destination IDs must be selected before durable dogfood fixtures are frozen. |
| 14 | Capability output authority | Moving implementations into packs is sufficient for packification ownership. | Capabilities may not directly create semantic file authority; outputs are quarantined and materialized through repositories (`v10:651`; risk correction `:688`). | Packification’s supported pack API must include the repository/materialization boundary, without exposing raw SQLite writers. |
| 15 | “Media” naming | The current tree already has a capability pack at `astrid/packs/media/pack.yaml`. | `media`, `media_locations`, and `media_relations` are kernel tables, never a data pack (`v10:147,349-383`). | Documentation must say “media capability pack” versus “kernel media subsystem.” Do not create a data pack named `media`. |
| 16 | Execution tracks | Packification Sprint 1 immediately rewrites kernel, pack schemas, discovery, inventory, and wheel packaging (`.oracle/plan.md:3-44`). | M1 immediately creates the data kernel, three data packs, repositories, registration, and bridge (`m1.md:13-28`). | Parallel implementation would encode contradictory contracts and create high merge churn. |

### Recommended adjustments

#### Packification plan

Add **Batch 0 / Task 0.0 — Freeze the two pack layers and rebase on astrid-first** before Task 0.1. It should lock physical roots, manifest names, dependency semantics, activation rules, CLI ownership, application composition, and package-data rules.

Then revise these existing tasks:

- **0.1 / Batch 1:** distinguish the application/capability kernel from the data kernel. Remove file-backed timeline/eventlog authority and defer the Arnold lifecycle clause until the lifecycle decision is settled.
- **0.2 / Batch 2:** define `_core` strictly as the capability system pack; tests should prove it is unrelated to the data kernel.
- **0.3 / Batch 3:** make `astrid/packs/bundled.yaml` capability-only. Registered data packs use the explicit application composition.
- **1.1 / Batch 4:** change “every reader” to “every capability, skill, and element reader.” Data-pack activation does not call `discover_pack_metadata()`.
- **1.3 / Batch 5:** package and smoke-test data manifests, migrations, catalogs, and conformance assets separately from capability inventory parity.
- **2.2 / Batch 7:** preserve the semantic difference between capability `depends` and data `depends_on`. Add import rails for `data/kernel → data/packs` and direct capability access to data writers.
- **2.4 / Batch 8:** replace `core/timeline/asset_registry_state.py` and file-side recovery work with the landed SQLite `TimelineRepository`. Do not create new authority scheduled for m6 deletion.
- **2.5 / Batch 8:** retain top-level `astrid serve` as application bootstrap. Keep Reigh-specific remote integrations in the Reigh capability pack.
- **2.6 / Batch 9:** define the public repository/materialization service capabilities may call; keep raw UoW/connection creation internal.
- **3.1 / Batch 10a:** distinguish the eight product families from developer capability tooling while still eliminating aliases.
- **4.2 / Batch 11:** scope capability layout validation to `astrid/packs/`; add a small independent validator for data migrations, vocabularies, repositories, conformance, and writer rules.
- **4.4–4.5 / Batch 12:** make closure explicitly dual: discovered manifest-backed capability packs plus explicitly registered data packs. Add catalog, migration-order, deletion-factoring, single-writer, and bridge tests.

#### Astrid-first initiative

- Replace ambiguous `core/` and `packs/` touchpoints with `astrid/data/kernel/` and `astrid/data/packs/{timeline,shots,references}/`.
- Use an unmistakable data manifest such as `data-pack.yaml`; retain `depends_on`.
- Place the three `register_pack()` calls in `astrid/data/composition.py` or the application bootstrap, never in the reusable data kernel.
- Do not adopt capability discovery, install/uninstall, environment roots, or third-party loading.
- Move the thin bridge adapter out of `astrid/core/integrations/reigh/`; route it through the application composition and timeline repository.
- Preserve `astrid serve` as the product bootstrap.
- Treat capability IDs and digests as opaque metadata and invoke capabilities only through the public capability service.
- In shared documentation, always qualify “capability pack” versus “data/schema pack” and “application kernel” versus “data kernel.”

The absent OpenRouter plugin-data chat does not block this analysis. `NORTHSTAR.md` identifies v10 as normative and the master plan as the vision anchor (`NORTHSTAR.md:11`); the master plan says v10 controls current behavior (`unified-data-master-plan-20260814.md:235-244`). The chat might add rationale, but it should not change the alignment unless it contains a still-unrecorded physical-root or manifest decision.

### Recommended sequencing

Do not execute frozen packification v3 in parallel with astrid-first. The frozen tasklist itself says scope or ordering changes require the oracle (`.oracle/tasklist.md:3,245`).

Recommended order:

1. Resolve the lifecycle, physical-root, and `serve` decisions now and issue packification STABLE v10/tasklist v4.
2. Let astrid-first m1–m8 land on `main`, using the aligned roots, opaque final capability IDs, and application-shell decisions.
3. Rebase and rerun the packification audit against the landed authority.
4. Execute the revised two-sprint packification plan.

Waiting only through m1 or m2 is insufficient: file-backed timeline authority remains until m6, and later milestones settle the product CLI, package, and installed-artifact shape. If schedule pressure forces overlap, limit it to capability-local audits and tests. Hold implementation touching `astrid/core`, `astrid/packs`, gateway/CLI, timeline/eventlog, bridge, schemas, validators, package data, and root documentation.

### Open questions for the user

1. Which lifecycle wins: Arnold/session `start-next-ack-status-abort`, or astrid-first’s runs/tasks/events model with no plan/session/`next`/`ack` surface?
2. Approve separate data roots and manifests, or require one shared `astrid/packs/` tree with a discriminated `pack_type`?
3. Confirm that `astrid serve` remains the zero-config product entry point rather than being replaced by a qualified executor command.
4. Is `astrid scratch` retained as developer-only tooling, or removed entirely from the shipped product as v10 currently specifies?
