# PLAN REVISION — settled-plan wave 1 findings (grok-4.6, oracle)

You are the planner revising the frozen plan (`.oracle/plan.md`, sha256 d35a66f5a9f42fd11182d7fc3eef13fc28e1f101261c9034d5587736fc42fc6b) after the first settled-plan sense-check wave. All six accepted findings are listed — apply them to the plan and restate the affected sections. BIAS TOWARD ELEGANCE AND SIMPLICITY. KISS, YAGNI, cut scope that isn't pulling its weight. Do not widen scope, do not re-open settled design decisions unless a finding demands it.

Dispositions (already decided by the oracle — do not relitigate):
- ACCEPT: B1 ∥ B2 ∥ B3 (all three batches parallel, within-batch order only), B4 last (needs ffmpeg render + expand + --shots parent). Clean up the parallelism statement in the plan.
- ACCEPT: T10/T12 acceptance adds idempotency assert — "compile twice → same 25 shots, same 25 timeline rows, no extra rows on the second run".
- ACCEPT: T12 golden-expansion test asserts byte-equivalence modulo clip ids explicitly.
- ACCEPT: canonical render output path `.oracle/evidence/shot-pipeline.mp4` (T14 writes there; T16 documents it as authoritative).
- ACCEPT (structural): `expand_shot_clips(config, registry, *, load_timeline)` is a pure function; one hook in `_prepare_managed_render_inputs`; expansion is memory-only — the stored sqlite document is NEVER written back (T6 asserts this).
- ACCEPT: T3 stills = per-unique-image `-loop 1 -t <hold>` in the existing unique-asset `-i` list; `concat=v=1` unchanged.
- REJECT (do not apply): hardcoding a single captions-only text schema; `--shots` as default.

Deliver the REVISED plan as structured markdown (same shape as the current plan: settled design, additional explore, open questions decided, tasklist, North Star, effort). If nothing material changed, reply EXACTLY `STABLE`. If the only changes are the accepted clarifications above, still emit the revised plan (the accepted items are material to task acceptance text, not to design).