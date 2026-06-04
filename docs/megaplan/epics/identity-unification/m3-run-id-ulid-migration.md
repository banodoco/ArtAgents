# M3 — Run-id ULID migration: decide grandfathering, then tighten

## Outcome
A deliberate, documented decision on non-ULID run ids — then validator tightening that matches it. Handoff artifact: `docs/contracts/run-id-migration.md`.

## Context (the trap this milestone exists for)
`validate_run_id` (project/paths.py:50) accepts dots/colons/128 chars; threads requires strict ULIDs (threads/ids.py:58). The run-ledger contract declares run IDs are ULIDs — but the codebase's OWN tests/fixtures use `task-run-1`, `run-1` etc. (tests/test_task_env_contract.py:26, test_task_kernel_dispatch.py:168, migration tests throughout). Blind replacement breaks them. Adversarial review verdict: this is a migration decision, not a validator swap.

## Scope
1. Inventory every non-ULID run-id producer/consumer (tests, fixtures, task kernel paths, any real on-disk runs in astrid-projects).
2. DECIDE (planner, in the contract doc): grandfather task-step synthetic ids as a named distinct id kind vs migrate fixtures to ULIDs vs keep dual grammar with an explicit predicate. Decision criteria: blast radius on contract-locked threads, on-disk reality, run-ledger contract wording.
3. Implement per decision; round-trip conformance (generate → project-layer write → threads-layer read) for the ULID class; update run-ledger contract doc wording if the decision refines it.

## Locked decisions
No silent breakage: whatever the decision, every currently-passing test passes or is deliberately migrated in the same diff; on-disk historical runs remain readable.

## Anti-scope
No timeline/session work (M1/M2); no threads internals; UUID-validator dedup is quickwins item 4 (verify landed; do not redo).
