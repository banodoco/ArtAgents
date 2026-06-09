# S4 — Collapse + element-restructure + purge  (the structural sprint)

**Read first:** RFC (§5 A6) + MIGRATION-PLAN (§3 element disposition). **Profile:** partnered / full / depth high.
**Why — IMPORT-TOPOLOGY TRIGGER:** this rewires `__init__`/re-export surfaces and gateway dispatch and collapses package boundaries. That class fails *non-locally* (circular imports, load-order) in a way an objective gate does NOT backstop, because the bad topology is designed in the *plan*. Premium planner is mandatory here regardless of how behavior-preserving it looks. High depth for the import graph. Depends on S2 + S3.

## Outcome
The kinds are literally one thing: a single generic registry over `CapabilityHandle`, `kind` demoted to a tag, elements restructured to capability form, and the dead per-kind lifecycle machinery deleted.

## Scope (IN)
1. **Registry collapse.** Collapse Element/Model/Executor/Orchestrator registries onto one generic `Registry` over the existing `CapabilityHandle`/`to_capability_handle` (`contracts/schema.py:119-260`). `kind` becomes a tag, not a subsystem. Unify the gateway dispatch table (`gateway/dispatch.py:137-203`). Leverage already-unified SDK discovery.
2. **Element restructure.** Make `component.tsx` non-required: drop it from `REQUIRED_ELEMENT_FILES` (`element/schema.py:25,167`); element declares `runtime: {adapter: remotion}`; the remotion adapter resolves `component.tsx` by convention. Migrate all 12 elements to capability form (I/O already annotated in S1). Dedup `text-card`: local becomes a kernel `OverrideStore` override, not an element-special fork.
3. **PURGE.** Delete element `fork` (`registry.py:148-159`), `install.py`, cli `fork/install/override/dirty/update`, and their tests (`test_elements_cli.py` fork/install/override sections, `test_elements_install.py`, element parts of `test_fork_executor_orchestrator.py`) — **removed, not skipped**. Any genuinely needed lifecycle lives once in the kernel.

## Anti-scope (OUT)
No new artifact types (S1/S2 own those). No theme changes beyond what the collapse requires (S3 owns themes). Don't rename the word "element" unless explicitly requested.

## Open question for the planner
Sequence the collapse to avoid a circular import: design the generic `Registry` + kernel module's import position FIRST (it must not import the per-kind packages that will import it). Map the import graph before moving code.

## Done criteria / GATE (parity oracle)
SDK `discovery` returns the identical capability set pre/post; gateway routes identically; a Remotion render of each migrated element matches pre-migration output; purged-machinery tests are gone (grep proves no skips); no circular import (suite collects clean).

## Sizing note
If planning shows this exceeds ~2 weeks, split: **S4a registry-collapse** (topology, partnered//high) and **S4b element-restructure+purge** (behavior-preserving, directed//low). The two are separable along the same axis.

## Touchpoints
`contracts/schema.py`, new `core/registry/` kernel, the 4 registry modules, `gateway/dispatch.py`, `element/{schema,registry,catalog,cli,__init__}.py`, `element/install.py` (delete), the element tests above.
