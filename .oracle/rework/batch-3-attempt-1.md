# REWORK batches 3+4 attempt 1 — fix fan-out + kernel reader + ledger

North Star: ONE store, ONE execution path. Anti-patterns: fake ids, second ledger, per-reader sqlite blocks, orphan mkdir.

## Tasks
### R3.1 Fix B3 fan-out N=4 (P0)
- In astrid/core/project/kernel_admission.py or astrid/sdk/invocation.py or astrid/core/execution/orchestrator/runner.py — wherever orchestrator admission lives — replace children=[] with children=[{capability,spec,run_ordinal,depends_on}] N=4 hard chain (plan, fetch, render, publish) using compute_spec_hash for idempotency keys. Use RunRepository.create with depends_on kind hard. Verify: 1 run + 4 tasks, events per task (created, claimed, started, completed), receipts, hard dependency chain, zero run.json authoritative.

### R3.2 One kernel reader (P1)
- New astrid/core/kernel/read.py with kernel_run_info(slug,run_id) and kernel_runs_for_project(slug) via open_database + RunRepository/DatabaseWriter. Replace 6 sqlite3 blocks (attached:227, timeline_visualize:259, frozen:630, guidance:154, project:164, banodoco_worker:198) with single helper. Fix project_id ULID vs slug inconsistency and banodoco_worker double query. Narrow except Exception to sqlite3.Error.

### R3.3 Banodoco worker single-write projection
- Collapse write+patch to one atomic write_run_record with authority kernel/import.

### R3.4 Harness honesty
- tests/test_run_ledger_conformance.py: assert kernel runs/tasks/events/receipts, not just records==[]; add ≥6 caps empirical harness per B4.2.

Verify: grep zero unauthorized run.json writers, full suite green, docs alignment green.
