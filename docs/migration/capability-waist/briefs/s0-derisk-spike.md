# S0 — De-risk spike  (HARD GATE for the epic)

**Read first:** `docs/RFC-capability-artifact-waist.md` + `docs/migration/capability-waist/MIGRATION-PLAN.md` (esp. §8 cross-cutting requirements + §9 decision record).
**Profile:** partnered / light / depth high. **Why:** this is a *spike* (light robustness, throwaway code OK) but it exercises the two judgment-heavy, irreversible bets — novel scoped-config primitive + import-topology of the registry collapse — so the planner must be premium.

## Why this sprint exists
A high-altitude review found the original plan gated its go/no-go on the *easy* claim (the timeline lookup) while the real, irreversible risk lives in S3 (scoped-config across 32+ ambient-context seams) and S4 (collapsing four registries through `__init__`/re-export topology without a circular-import cascade). This sprint proves the hard things in **days**, before the epic commits weeks to them.

## Scope (IN) — three cheap proofs, throwaway code allowed
1. **Scoped-config on ONE theme seam.** Prototype the kernel-scoped-config primitive and use it to remove **one** real usage of the `_ACTIVE_THEME_DIR` global / `HYPE_ACTIVE_THEME` env read (e.g. the `executor/runner.py:375` resolve path). Goal: prove the primitive can replace ambient threading without breaking subprocess parity on that one path. This is S3's load-bearing risk.
2. **Import-graph map for the collapse.** Map the import graph of the four registries (`element`, `model_catalog`, `executor`, `orchestrator`) + `contracts/schema.py` + `gateway/dispatch.py`. Produce a written **cycle-free ordering** for introducing a generic kernel module (where it sits in the import graph so the per-kind packages import *it*, not vice-versa). Prototype just the kernel module's import skeleton and prove `python -c "import astrid"` + suite *collection* stays clean. This is S4's load-bearing risk (the documented circular-import trap).
3. **Reigh round-trip baseline.** Capture a baseline: a corpus of current timelines loaded via the external `banodoco_timeline_schema` package round-trips byte-identically. This becomes the CI parity gate that guards every later sprint (§8.2).

## Anti-scope (OUT)
No production carrier, no annotations, no real consumer rewiring, no purge. This sprint writes throwaway prototypes + one doc + one baseline test. It does not ship the field (that's S1).

## Done criteria / GATE (this gates the whole epic)
- Scoped-config prototype replaces one global usage with subprocess parity preserved on that path.
- A written, reviewed cycle-free collapse ordering exists; the kernel-skeleton import proves no cycle.
- Reigh round-trip baseline test exists and is green.
- **If the scoped-config seam or the import-graph leg proves intractable → STOP, record why, re-plan S3/S4 before proceeding.** A clean "this is harder than the plan assumed" finding here is a success, not a failure.

## Deliverable
`docs/migration/capability-waist/s0-findings.md` (the import-graph ordering + scoped-config feasibility verdict + any re-plan flags), the Reigh baseline test, throwaway prototype branches/notes.

## Touchpoints (read/prototype, not ship)
`element/catalog.py`, `executor/runner.py`, `subprocess_env.py` (seam 1); the 4 registry modules + `contracts/schema.py` + `gateway/dispatch.py` (seam 2); `timeline/banodoco_schema.py` + `banodoco_timeline_schema` (seam 3).
