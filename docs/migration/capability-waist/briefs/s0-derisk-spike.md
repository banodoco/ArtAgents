# S0 — De-risk spike (SLIMMED; gates the epic)

**Context:** `docs/RFC-capability-artifact-waist.md` + `docs/migration/capability-waist/MIGRATION-PLAN.md`. This epic LAYERS ON `RESTRUCTURE-PLAN.md` (live as `beauty-v2`).
**Profile:** partnered / light / depth high (spike; throwaway OK; scoped-config is the novel-primitive judgment).

## Why slimmed
The original S0 had three legs; the **import-graph leg is dropped** — RESTRUCTURE already produced the cycle analysis (`/tmp/cycle-results/CY1–CY5`) and is landing the cycle-free tier structure. Only the genuinely-still-unproven bets remain.

## Scope (IN) — two cheap proofs
1. **Scoped-config on ONE theme seam.** Prototype the kernel-scoped-config primitive (RFC §3) and use it to remove **one** real `_ACTIVE_THEME_DIR` / `HYPE_ACTIVE_THEME` usage (e.g. `executor/runner.py` resolve path), proving it replaces ambient threading **without breaking subprocess parity** on that path. This is S3's load-bearing risk.
2. **Reigh round-trip baseline.** Capture a corpus baseline: current timelines load + round-trip byte-identically via the external `banodoco_timeline_schema` package. This becomes the CI parity gate guarding every later sprint (MIGRATION-PLAN §8.2).

## Anti-scope (OUT)
No production carrier (S1), no annotations, no import-graph work (RESTRUCTURE owns it), no consumer rewiring, no purge.

## Done / GATE (objective; no human halt)
- scoped-config prototype replaces one global usage with subprocess parity preserved;
- Reigh round-trip baseline test exists and is green.
A milestone that cannot meet this objective gate **fails the chain** (surfaced by megaplan + `/babysit`) — there is no human re-plan step. The de-risk value is "fail fast on the riskiest part," not "ask a human."

## Deliverable
`docs/migration/capability-waist/s0-findings.md` (scoped-config feasibility verdict + any re-plan flags) + the Reigh baseline test + throwaway prototype notes.
