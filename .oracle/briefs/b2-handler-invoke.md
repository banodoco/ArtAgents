# BATCH 2 — CapabilityTaskHandler + sdk.invoke rewiring + pack orchestrator shims

You are a normal-pool executor (openrouter/meta/muse-spark-1.2-contributor) in the worktree /Users/peteromalley/Documents/reigh-workspace/Astrid-unified-oracle (branch oracle-unified-execution). Base b4c70e0a, batch 1 committed dddc0ae9. NO git commands. NO formatters.

## Tasks (all normal, one batch, dependent order: 2.1 → 2.2 → 2.3)
### 2.1 Generic TaskHandler
New file astrid/core/task_executor/capability_handler.py: class CapabilityTaskHandler implements TaskHandler (service.py:113). For capability_kind in {executor, orchestrator}, capability_id, request dict → build ExecutorRunRequest(execution_mode="in_process", out=staging/out) or orchestrator equivalent, call run_executor/run_orchestrator in-process under ASTRID_INTERNAL_INVOCATION=1 (same as sdk.invoke invocation.py:361-362). Harvest outputs: prefer capability's manifest.json (discover_manifest_path) else walk staging/out for concrete files; classify by extension/mime into PreparedMedia managed import vs evidence entry; complete via ExecutionService with materialize_prepared loop + evidence facts in params. Keep validate_result_manifest re-verification. Handler failures → fenced fail path (service.py:367-392). Dry-run/skipped requests never admitted (preserve ledger exemption).

Verify: parity probe — generate_image + timeline_visualize through generic handler produce byte-equal outputs vs bespoke adapters/harness; harness at tests/v10/test_generation_roundtrip.py:310-558.

### 2.2 sdk.invoke admission
Modify astrid/sdk/invocation.py::invoke to admit kernel run+task (RunRepository.create with one child task, compute_spec_hash idempotency key), claim/start, CapabilityTaskHandler execute, complete/fail; return kernel ids in InvocationResult (public shape stable, additive). Remove executor runner's prepare_project_run write path for project-mode invocations (runner.py:876) — run dir retained as output/staging only. Update ~48 run.json-shape test expectations per E7 census (list in batch 1 findings). Update run-ledger-contract conformance meta-tests. See northstar one-store pillar.

Verify: full sdk invoke suite; ≥3 executors via sdk.invoke → kernel events/receipts/terminal succeeded, zero authoritative run.json writes.

### 2.3 Self-managing pack orchestrators shim
Rewire astrid/packs/video_editing/orchestrators/{event_talks/run.py:648, hype/project_adapter.py:86, thumbnail_maker/run.py:550} that currently call prepare_project_run directly — route through the same admission path as 2.2 (shared helper).

Verify: pack test slices green.

## North Star context
One store, one execution path, every run observable. Anti-patterns: second ledger, silent divergence, ghost verbs, per-executor adapters, scope creep. Cut overengineering.

## Constraints
- Fresh basetemp /tmp/b2-*; rm -rf after.
- Do not touch user-in-flight files (wavespeed, model_catalog, generate_audio/generate_image, docs/generation, test_generation_backend_registry).
- If an expected file is missing, check worktree HEAD (batch 1 committed).

## Report (<300 words)
Per sub-task: file:line, verification output, elegance notes (flag overengineering).
