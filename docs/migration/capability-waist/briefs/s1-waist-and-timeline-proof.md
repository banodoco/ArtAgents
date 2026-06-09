# S1 — Waist + timeline proof  (vertical slice; the go/no-go)

**Read first:** `docs/RFC-capability-artifact-waist.md` + `docs/migration/capability-waist/MIGRATION-PLAN.md`.
**Profile:** directed / full / depth medium. **Why:** the carrier is additive (cheap) but the type-resolution design is a real planner decision; a parity oracle backstops execution.

## Outcome
The rendering path composes by **artifact type**, not by name. One vertical slice proves M×N→M+N end to end. If the parity oracle is green, the whole theory is validated and S2–S4 are justified.

## Scope (IN)
1. **Carrier.** Add `artifact_type: str | None = None` to `Port` and `Output` (`contracts/schema.py:26-43`). Parse it in the two parsers (`executor/schema.py:312-338`, `orchestrator/schema.py:211-237`). Optional → every existing manifest loads unchanged.
2. **Registry.** `ArtifactTypeRegistry`, pack-extensible (mirror `ElementKindRegistry` at `pack/registry.py:49-103`; extend via `pack.extensions["artifact_types"]`). Seed from the inventory's 13 types (canonicalize `video/clip`↔`clip/visual`). Declared-but-unregistered type = validation error; unknown *runtime* values stay opaque.
3. **Annotate the timeline path only.** Add `consumes`/`produces` artifact types to the 12 element manifests (per plan §3 dispositions) and give `ElementDefinition` `inputs`/`outputs` (its `to_capability_handle` stops emptying them). Annotate the `render` executor I/O (`timeline`,`asset_registry`,`theme`→`video/clip`).
4. **Rewire the timeline validator.** Replace the enumerate-and-membership-test at `validators/timeline.py:247-257` (+ `validators/registry.py:10-22`, anim/transition validators) with: resolve `clipType`/ref id → capability → kernel type-check `clip/visual` → validate params. **Preserve open-string opaque fallback** (unknown clipType stays valid — Reigh compat, `timeline.py:194,251`).

## Anti-scope (OUT)
No registry collapse, no theme/scoped-config work, no element restructure (component.tsx stays required this sprint), no purge, no annotation of non-timeline executors. Those are S2–S4.

## Locked decisions
Composition = type-match (validate) + id-reference (select); id-reference is irreducible. `artifact_type` is additive/optional. No closed enums over `clipType`/`kind`.

## Done criteria / GATE (parity oracle)
Across the timeline test corpus, the **new type-resolution path accepts/rejects the identical set of timelines** as the old `_effect_ids` path. All existing tests green. New tests: registry resolution + pack extension; element I/O annotation present; open-string fallback preserved.

## Touchpoints
`contracts/schema.py`, `executor/schema.py`, `orchestrator/schema.py`, `pack/registry.py`, `timeline/validators/{timeline,registry}.py`, 12 `element.yaml`, `element/schema.py` (ElementDefinition I/O), `rendering/executors/render/executor.yaml`.
