# M3 — Net-new scenarios: data retention + orchestrator execution (the 4 focus areas)

Companion: `docs/megaplan/epics/astrid-sisypy/design.md` (§4 build-first list, §2 universal checks) and `tests/agentic/ADAPTER.md` (M1). Read both.

## Outcome
A set of net-new agentic scenarios on the Sisypy harness that directly cover the user's four focus areas — (1) timeline usage, (2) data retention/persistence correctness, (3) orchestrator execution, (4) data retention RESULTING FROM orchestrator execution — each proving its claim from a frozen evidence pack, not narrative.

## Scope (IN) — build these scenarios (YAML + brief + any priming + assessment rubric)
1. **`orchestrator_run_persists`** [Execution×Operate, FOCUS-3+4] — agent runs an orchestrator end-to-end; the pack is frozen and we assert: `run.json.status==success`, `events.jsonl` chain verifies, every declared `produces` path exists with sha256 matching its attestation event, and `finalize_project_run` actually wrote the run-level artifacts. The flagship retention-from-execution test.
2. **`artifact_pipeline`** [Execution×Compose, FOCUS-4] — orchestrator A's output artifact is consumed as input by orchestrator B; assert the provenance chain stays intact across the handoff (no orphan artifacts, hashes line up, both runs' event logs verify). Distinct from the existing `sequential_orchestrators` (which tests session handoff, not artifact data-flow).
3. **`timeline_compose_edit`** [Timeline×Compose, FOCUS-1] — agent builds a meaningful multi-track timeline from scratch (tracks + clips + audio bindings + transitions + effects + theme); assert chain-integrity + projection-fidelity hold after the composite edit. This single compositional test is meant to retire the value of the ~9 isolated single-verb timeline scenarios.
4. **`durability_after_crash`** [Data-Retention×Repair, adversarial, FOCUS-2] — prime a state where an append was interrupted mid-write (or simulate the head/jsonl desync window); assert the system detects the inconsistency on reopen (head-rebuild / verify) rather than silently serving stale state. (Ties to filed ticket on the head/jsonl desync window — the scenario PROBES the behavior, it does not fix Astrid.)
5. **`timeline_large_audit`** [Integrity×Operate, scale L, FOCUS-1+2] — pre-seed a 500+ event timeline; agent runs `timelines audit` / `events verify`; assert chain verification completes correctly and within budget (catches scale regressions; everything else in the suite runs on 1-3 events).
6. **`concurrent_same_project_writers`** [Infra×Operate, adversarial, FOCUS-2] — two writers target the same project; assert exactly one holds the lease and the other is cleanly rejected (StaleEpochError / NotWriterError), with no interleaved/corrupted event log.
7. **`session_corruption_recovery`** [Infra×Repair, adversarial, FOCUS-2] — `.astrid-session` is corrupted/stale; agent must detect, diagnose, and recover (re-attach or re-init) rather than binding to a wrong/sibling project.

## Locked decisions
- Use the M1 universal checks as the backbone — these scenarios add scenario-specific enforced/graded items ON TOP, they don't re-implement integrity checks.
- Adversarial priming (interrupted writes, pre-seeded large logs, corrupted session files, concurrent writers) is set up deterministically in the adapter prime hook / scenario priming, so structural runs are reproducible.
- Each scenario must be runnable structurally (fake actor) for CI well-formedness AND meaningfully gradeable with a real actor.

## Open questions for the planner
- How to deterministically simulate a mid-append crash / head-desync in priming without modifying `astrid/` — e.g. truncate the head sidecar, or stage a jsonl with one extra line vs head count. Inspect `astrid/core/timeline/eventlog/local_fs.py`.
- How to pre-seed a 500-event timeline cheaply (scripted appends in priming vs a fixture file) while keeping the chain valid.
- How to drive two concurrent writers within one scenario run (two primed sessions + ordering) under the Sisypy actor model.
- Which real orchestrator to use for `orchestrator_run_persists`/`artifact_pipeline` that runs without GPU/network (likely a small `video_editing` or `editorial` executor with a local/dry path) — inspect `astrid/packs/`.

## Constraints
- Structural mode: no network/GPU/spend. Where a real orchestrator would need GPU, use a dry-run/local executor or a stub pack so the persistence assertions still have real files to check.
- Adversarial scenarios assert the system's DETECTION/RECOVERY behavior; they must not depend on a specific Astrid bug being unfixed (if the head-desync ticket gets fixed, the scenario should still pass by asserting detection happens).

## Done criteria
- All 7 scenarios load and structurally pass (`--actor fake --mode structural`).
- Each scenario's assessment rubric names the exact frozen-evidence assertion it proves (per design §4).
- A short note maps each scenario to its focus area(s) and matrix coordinates.

## Touchpoints
- `tests/agentic/scenarios/` (7 new YAML), `tests/agentic/briefs/` (7 new briefs), possibly small additive adapter priming helpers (coordinate with M1 contract), read-only `astrid/core/timeline/*`, `astrid/core/project/*`, `astrid/packs/*`.

## Anti-scope
- Do NOT touch `astrid/` production code or fix the filed bugs — scenarios probe behavior only.
- Do NOT re-migrate M2 scenarios or build M4's discoverability/authoring/refuse scenarios.
- Do NOT change M1's adapter contract non-additively.
