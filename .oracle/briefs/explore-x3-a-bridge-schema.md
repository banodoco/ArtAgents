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
# EXPLORE X3 — A bridge & schema incident fixes (read-only)
Repo: A = /workspace/goalmd-20260822/repos/Astrid (exec-goal @ 17b2bbb6 = WIP snapshot of main@dd1bbe3a). READ-ONLY.

Verify each incident fix is PRESENT in this snapshot, quoting file:line:
1. Element-corpus lru_cache + clear hook: astrid/core/element/registry.py (~:185 area) and catalog.py _clear_registry_cache seam.
2. Identity-first UUID resolution without event replay: astrid/core/timeline/paths.py.
3. Record-threaded registry killing redundant resolutions: astrid/core/integrations/reigh/local_bridge.py.
4. app-bag acceptance: banodoco_schema.py _TRACK_ALLOWED/_CLIP_ALLOWED contain 'app'; also report exact line numbers of _CLIP_ALLOWED and _BRIDGE_CANONICAL_TOP_KEYS (GOAL cites :389-396 and :43-120) and whether output is stripped from canonical writes.
5. local_bridge_server.py: full route inventory (method+path list); does do_POST read expected_version and return 409 on mismatch (CAS)? Quote handler lines. Is there still PUT-registry / health / projects / sources / timelines-list / checkpoints / audio-video-proxy routes (B5 shrink targets)?
6. How `astrid serve` starts (module/function, --port flag, default project root resolution) and whether port 0 is supported.
7. git show 17b2bbb6 --stat | head -60: which of the 43 files look incident-related vs unrelated CLI WIP (two lists).
Output: ranked findings <300 words + fact table. Unknowns/risks separate.
