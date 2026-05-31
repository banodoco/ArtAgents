# M4 — Net-new scenarios: data retention + orchestrator execution (the 4 focus areas)

Companion: `docs/megaplan/epics/astrid-sisypy/design.md` (§4 build-first, §2 checks) + `tests/agentic/ADAPTER.md` (M1) + M2 checks. Read them. NOTE (review corrections applied below): artifact hashes come from `produces_check_passed.cas_sha256`, NOT run.json; timeline writers use flock+version-conflict (no lease — lease is task-run only).

## Outcome
Net-new Sisypy scenarios covering the user's four focus areas — (1) timeline usage, (2) data-retention/persistence correctness, (3) orchestrator execution, (4) data retention RESULTING FROM orchestrator execution — each proving its claim from a frozen evidence pack using the M2 checks plus scenario-specific assertions.

## Scope (IN) — build these (YAML + brief + priming + assessment)
1. **`orchestrator_run_persists`** [FOCUS-3+4] — agent runs an orchestrator end-to-end; assert: task-run `events.jsonl` verifies via `task.events.verify_chain`; run reaches terminal success via `finalize_project_run` (assert the terminal event in events.jsonl, AND run.json.status — but treat run.json artifacts as path/source only); every declared `produces` exists AND its hash matches the corresponding **`produces_check_passed.cas_sha256`** event (M2 check C2). The flagship retention-from-execution test.
2. **`artifact_pipeline`** [FOCUS-4] — orchestrator A's produced artifact is consumed by orchestrator B; assert provenance holds across the handoff: both runs' task-run chains verify, B's input resolves to A's `produces` artifact, hashes line up via cas_sha256, no orphan artifacts. Distinct from existing `sequential_orchestrators` (session handoff, not artifact data-flow).
3. **`timeline_compose_edit`** [FOCUS-1] — agent builds a multi-track timeline from scratch (tracks+clips+audio bind+transitions+effects+theme); assert timeline chain verifies via `LocalFsBackend.verify_chain`, head/sidecar consistency (C1), and projection-fidelity (C4) against a frozen read-only assembly.json snapshot. Retires the value of the ~9 single-verb timeline scenarios.
4. **`timeline_concurrent_version_conflict`** [FOCUS-2] — TWO writers append to the SAME timeline; assert serialization via flock + that the losing append hits the version/CAS conflict (`EventLogStaleVersionError` per `astrid/core/timeline/eventlog/local_fs.py`), with the timeline chain still valid afterward. (Timeline has NO writer lease — do not assert lease semantics here.)
5. **`taskrun_concurrent_lease`** [FOCUS-2+3] — TWO task-run writers contend for the same run; assert exactly one holds the lease (lease.json/epoch) and the other is cleanly rejected (StaleEpochError/NotWriterError), no interleaved/corrupted `events.jsonl`. (This is where lease semantics live.)
6. **`durability_after_crash`** [FOCUS-2, adversarial] — prime the head/jsonl desync window (e.g. a timeline whose assembly.head.json event_count disagrees with assembly.jsonl line count); assert the system DETECTS the inconsistency on open/verify rather than serving stale state. Ties to a filed ticket; asserts detection, not a fix.
7. **`timeline_large_audit`** [FOCUS-1+2, scale L] — pre-seed a 500+ event valid timeline; agent runs audit/verify; assert chain verification completes correctly and within budget.

## Locked decisions
- M2 universal+conditional checks are the backbone; these add scenario-specific enforced/graded items.
- Artifact correctness is proven via `produces_check_passed.cas_sha256` (C2), never via a nonexistent run.json hash.
- Concurrency: timeline = version/CAS conflict; task-run = lease. Two SEPARATE scenarios (#4, #5) — do not conflate.
- Adversarial priming is deterministic in the prime hook so structural runs reproduce.

## Open questions for the planner
- Deterministic priming for: the head/jsonl desync (stage head.json count ≠ jsonl lines); a valid 500-event timeline (scripted appends keeping the chain valid); two concurrent writers within one scenario run.
- A GPU/network-free orchestrator for #1/#2 (a small editorial/video_editing executor with a local/dry path) — inspect `astrid/packs/`.
- How `finalize_project_run` normalizes terminal status (so #1 asserts the right terminal signal) — `astrid/core/project/run.py:235-268`.

## Constraints
- Structural mode: no network/GPU/spend. Where a real orchestrator needs GPU, use a dry/local executor or stub so persistence assertions still have real files.
- Adversarial scenarios assert DETECTION/RECOVERY behavior and must still pass if the underlying Astrid ticket is later fixed.

## Done criteria
- All 7 scenarios load and structurally pass (fake actor, structural).
- Each scenario's assessment names the exact frozen-evidence assertion + which M2 check(s) it leans on.
- A note maps each scenario to its focus area(s) and matrix coordinates.

## Touchpoints
- `tests/agentic/scenarios/` (7 new), `tests/agentic/briefs/` (7 new), additive adapter priming helpers (coordinate with M1 contract). Read-only: `astrid/core/timeline/*`, `astrid/core/task/events.py`, `astrid/core/project/run.py`, `astrid/packs/*`.

## Anti-scope
- Do NOT modify `astrid/` production code or fix filed bugs — scenarios probe only.
- Do NOT build M5's discovery/authoring/refuse scenarios; do NOT decommission legacy harness.
- Do NOT change M1/M2 contracts non-additively.
