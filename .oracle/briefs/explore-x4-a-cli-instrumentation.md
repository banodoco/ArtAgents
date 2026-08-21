# NORTH STAR — judge your work against this (mandatory)

## Desirable end state
A user editing a timeline in the reigh video editor can trust that every edit is durably saved, that conflicts are surfaced honestly (never silently resolved against them), and that recovery after a crash or offline period offers their latest work back. The editor (E = reigh-timeline-main), the Astrid bridge (A), and the shared schema (S = ArtAgents/packages/timeline-schema) behave as one trustworthy system with a small, explicit contract surface.

## Enduring principles
- **Verify, don't assume.** Every behavioral claim comes from a real test run or live observation with quoted output.
- **Minimal interim forms.** Fix today's real problems with the smallest durable mechanism; do not pre-build the SQLite/Turso future.
- **The user's work is sacred.** Unrelated WIP is never swept into commits; incident fixes are staged surgically.
- **Honest failure UX.** A failed save must surface a persistent, actionable error — never a silent badge, never an automatic retry that defeats CAS.
- **One contract.** The hand-written schema is the sole source of truth; wire envelopes are explicit and conformed on both sides.

## Anti-patterns (reject on sight)
- Silent data loss or silent no-op saves.
- Automatic reload-and-repost loops that defeat optimistic concurrency.
- Scope creep into gated futures: SQLite/Turso migration, monorepo consolidation, full B6/B7/B8 machinery, outboxes.
- Committing the user's unrelated WIP or the untracked `dev/scene-phase-markers/` extension.
- "Green harness" claims without live observation; liveness treated as correctness.
- Framework ceremony that isn't pulling its weight (KISS, YAGNI).

## What aligned progress feels like
Each batch lands as a small, verified, committed increment with quoted acceptance evidence; the three repos stay coordinated; the next batch starts only when the previous one demonstrably passed.

Judge your work against these principles; flag anything that violates an anti-pattern.

---
# EXPLORE X4 — A CLI families for B1b instrumentation (read-only)
Repo: A = /workspace/goalmd-20260822/repos/Astrid. READ-ONLY.

GOAL.md B1b names 11 event-dependent CLI families: history, diff, audit, who-edited, preview, undo, mass-undo, erase, recover, branch, push/pull, migrate-events. astrid/core/cli/ has only domain_*.py modules — find where these commands are actually defined/registered:
1. Map each family → defining module/function file:line (grep command names across astrid/, including registration.py and any click/argparse wiring).
2. Common entry point(s) where ONE instrumentation hook could count all invocations (e.g., a dispatcher, main(), decorator) — prefer a single choke point; quote it.
3. Existing logging/counter patterns in A we should reuse (logging config, metrics file, anything similar).
4. Event-log shape: inspect tests/fixtures/timeline_visualize/desert_slice/assembly.jsonl (first 2 lines + actor field name) and park24_slice — what field identifies the actor and its type? Are timestamps present for windowing (format)?
5. Where timelines live on disk by default (paths.py root) so a synthetic project could be created for measurement runs.

Output: ranked findings <300 words + mapping table family→file:line. Unknowns/risks separate.
