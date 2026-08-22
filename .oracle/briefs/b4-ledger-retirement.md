# BATCH 4 — reader flip + derived projection

You are openrouter/meta/muse-spark-1.2-contributor in worktree /Users/peteromalley/Documents/reigh-workspace/Astrid-unified-oracle. NO git commands. NO formatters.

## Tasks
### 4.1 Flip readers to kernel-first
Rewire internal readers to kernel lookups: astrid/core/rendering/attached.py:197, astrid/core/contracts/timeline_visualize.py:145, astrid/packs/rendering/executors/timeline_visualize/frozen.py:559 (ownership checks), astrid/core/threads/record.py attribution/provenance, experiments, project listings. Use kernel-first with FS fallback; keep load_run_record for historical dirs. Delete prepare/finalize_project_run authority semantics from both runners (executor/runner.py:876, orchestrator/runner.py:595,670). Keep run directories as storage only.

### 4.2 Final verification harness
Empirical harness: ≥6 representative capabilities (media generation, file-only executor, timeline_visualize, orchestrator with children, banodoco worker, attached-render consumer) each asserted as kernel run+task with correct event chain/receipts/terminal status and zero authoritative run.json. Host runs full pytest tests/ + astrid --help.

Verify: full suite green, grep zero production run.json writers, docs alignment green.
