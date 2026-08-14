# Astrid packification — megado status

**Status: EXECUTION-READY (gated)** — plan STABLE v10, tasklist frozen v4; execution
prepared but deliberately gated on the astrid-first data-model initiative landing.

## Aspiration (accepted)

Every discoverable capability and every optional domain is a pack, behind a
closed, named kernel — with portability seams for a future framework
extraction, no transitional machinery, and the capability-pack layer aligned
with the astrid-first data-pack layer (two distinct "pack" concepts, one
coherent repo).

## Artifacts

- `.oracle/plan.md` — STABLE v10: execution admission gate + SPRINTS (2
  two-week sprints, Batch 0 added) + 20 tasks (phases 0-4, [XHARD]) +
  SHIM-SWEEP (20 CUT / 5 KEEP) + 2 decision gates + INTEGRATED table (36
  alignment recommendations adopted, none rejected).
- `.oracle/tasklist.md` — FROZEN v4: 14 batches, 14 checkpoints
  (Sprint 1: Batch 0-5 + 10a; Sprint 2: Batch 6-9, 10b, 11-12).
- `.oracle/explanation.md` — one-time comprehensive explanation of the effort.
- `.oracle/alignment-astrid-first.md` — alignment analysis with the data model
  (16 conflicts, per-side adjustments, sequencing, 4 questions) — user
  accepted its recommendations; integrated as plan v10.
- `.oracle/inputs/astrid-first/` — staged data-model docs (NORTHSTAR, master
  plan, v10 normative, m1 brief).
- `.oracle/inputs/openrouter-sensecheck.md` — external sense-check (v4).
- `.oracle/findings/01-16*.txt` — Flash exploration findings.
- `.oracle-threejs-archive/` — previous megado run, preserved.

## Execution admission gate (NEW in v10)

Packification execution does not begin until:
1. Astrid-first milestones m1–m8 have landed on `main`.
2. This worktree rebases onto the landed authority.
3. The packification audit is rerun against the rebased tree.
4. **Lifecycle decision recorded** (Gate 1): Option A Arnold
   `start/next/ack/status/abort` vs Option B astrid-first runs/tasks/events
   (no plan/session/`next`/`ack`). No hybrid; the loser is deleted outright.
5. **`astrid scratch` decision recorded** (Gate 2, in Batch 0): developer-only
   tooling (working-plan default) vs removed. Either result preserves exactly
   eight product families.

## The two layers (frozen by Task 0.0 / Batch 0)

- **Capability packs:** `astrid/packs/` + `pack.yaml` (discovery, `<pack>.<name>`,
  `bundled.yaml` capability-only, `_core` = capability system pack).
- **Data model:** `astrid/data/kernel/` (14-table agent kernel) +
  `astrid/data/packs/{timeline,shots,references}/` + `data-pack.yaml` +
  `astrid/data/composition.py` (`register_pack()`; no dynamic loader).
- `depends` (capability) vs `depends_on` (data) stay distinct; `astrid serve`
  stays the zero-config product bootstrap; capability tooling is
  developer-facing; capabilities never get raw SQLite writers/UoW; timeline
  authority = landed SQLite `TimelineRepository` (file-backed authority
  removed from the kernel plan).

## Sprint map (v4)

| Sprint | Batches | Focus |
|---|---|---|
| 1 (~2 wk) | 0-5, 10a | Two-layer freeze (0.0), kernel lock, `_core`, bundled inventory + `builtin` deletion, canonical discovery + pack-only elements, wheel proof of BOTH layers, alias removal |
| 2 (~2 wk) | 6-9, 10b, 11-12 | Generation/RunPod extraction, experiments + dependency laws, Reigh → `TimelineRepository` + worker, API freeze + CI, compat deletion, dual layout validation, hygiene + docs + closure |

Hard gate: Batch 5 / task 1.3 (capability graph AND data assets wheel-proven)
before any 2.x task.

## Key shim cuts (20 of 25)

Arnold sole lifecycle (post Gate 1); `in_process.py` exception + allowlists;
`serve` route → product bootstrap (Reigh route only deleted); worker/runpod/
publish*/reigh-data/author/run/--brief routes; `builtin` + `agent_probe`
(test fixture); pack `aliases:` field + resolver; Arnold compat.py +
shapes.py table; legacy runtime shapes, auto-bind shim, rendering selector +
`legacy_engine.py`; `rendering.legacy_hybrid` → `rendering.hybrid`; Reigh
`assets.json` fallback; no deprecation windows. KEPT: scratch (pending Gate
2), `_core → astrid` branding, deprecated-as-metadata, rendering fallback,
forks/overrides.

## Next action

Execution is GATED — the immediate asks are the two decisions (lifecycle;
scratch), and the astrid-first milestones landing. Say "execute" once the
admission gate passes; Batch 0 (Sol XHARD, delegation mandate) runs first.
