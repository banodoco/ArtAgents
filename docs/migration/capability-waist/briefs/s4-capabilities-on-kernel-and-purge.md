# S4 — Capabilities on the kernel + element restructure + purge (SLIMMED)

**Context:** RFC §5 + MIGRATION-PLAN §3. **Profile:** partnered / full / depth high.
**REQUIRES RESTRUCTURE W7** (it builds `core/registry/` base + the `execution/{executor,orchestrator}` umbrella). Depends on S2 + S3.

## Why slimmed
The original S4 *built* the kernel and collapsed registries — that's now RESTRUCTURE's job (W7 `core/registry/` + `execution/`). This milestone **puts capabilities on the substrate RESTRUCTURE built** and does the element-specific restructure + purge that RESTRUCTURE doesn't cover.

## Outcome
Models/elements/executors/orchestrators are one capability over RESTRUCTURE's `core/registry/` kernel; `kind` is a tag; elements are real capabilities; dead per-kind lifecycle machinery is gone.

## Scope (IN)
1. **Capabilities on the kernel.** Register all four kinds through RESTRUCTURE's `core/registry/` base + `CapabilityHandle`; `kind` becomes a tag, not a subsystem. (Do NOT re-build the registry base — consume it.)
2. **Element restructure.** `component.tsx` non-required: drop it from `REQUIRED_ELEMENT_FILES`; element declares `runtime: {adapter: remotion}`; the remotion adapter resolves `component.tsx` by convention. Migrate the 12 elements to capability form (I/O annotated in S1). Dedup `text-card`: local → kernel `OverrideStore` override.
3. **PURGE.** Delete element `fork`, `install.py`, cli `fork/install/override/dirty/update`, and their tests — **removed, not skipped**. Any real lifecycle lives once in the kernel.

## Anti-scope (OUT)
Don't build/redesign the registry base or `execution/` umbrella (RESTRUCTURE owns them). No new artifact types (S1/S2). No theme changes beyond what the collapse needs (S3). Don't rename the word "element" unless explicitly requested.

## Done / GATE (parity oracle)
SDK `discovery` returns the identical capability set pre/post; gateway routes identically; a Remotion render of each migrated element matches pre-migration output; purged-machinery tests are gone (grep proves no skips); no circular import (suite collects clean — RESTRUCTURE's tier invariants hold).
