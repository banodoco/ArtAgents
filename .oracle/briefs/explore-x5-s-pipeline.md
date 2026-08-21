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
# EXPLORE X5 — S schema pipeline state (read-only)
Repo: S = /workspace/goalmd-20260822/repos/ArtAgents/packages/timeline-schema (exec-goal @ 34e939b WIP snapshot). READ-ONLY.

GOAL B2/B3 vs what already exists here — report precisely:
1. python/banodoco_timeline_schema/timeline.schema.json: byte size (>1000? the degenerate artifact was 265 bytes), does it require tracks, enforce clip_order>0, define keyframes + derived_output, closed core keys, app as opaque object? Quote relevant fragments.
2. typescript/src/schemas.ts — still present (zod source)? typescript/src/generated.ts — generated from schema via emit-ts-types.mjs? Is json-schema-to-typescript pinned (package.json devDeps — quote versions; is zod / zod-to-json-schema / datamodel-code-generator still referenced anywhere)?
3. scripts/check-codegen.sh — list ALL gates it implements; does it include: min-size, required definitions, meta-schema validity, stable $id, parse, two-generation byte-identity, truncation-must-fail? Anything missing vs GOAL B2 item 3.
4. python fallback mirror: python/banodoco_timeline_schema/__init__.py try/except import fallback — still present? generated.py committed TypedDicts shape.
5. openapi/bridge.openapi.json — does it cover GET timeline, POST save, GET/HEAD assets, config_version/expected_version echo, 409 timeline_version_conflict, 422 schema_incompatible issues[{pointer,code,message}]? Quote operationIds.
6. tests/test_contract_v2.py + test_materialize_output.py — what they cover (ten-fixture parity corpus? malformed-app round-trip? 123-event replay?). Where does the parity corpus live?
7. Any GitHub workflow dir (.github/workflows) at repo root or package level?

Output: ranked findings <300 words + checklist table GOAL-item→present/absent(file:line). Unknowns/risks separate.
