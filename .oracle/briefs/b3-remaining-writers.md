# BATCH 3.1 — remaining run.json writers + orchestrator children

You are openrouter/meta/muse-spark-1.2-contributor in worktree /Users/peteromalley/Documents/reigh-workspace/Astrid-unified-oracle (branch oracle-unified-execution). NO git commands. NO formatters.

## Tasks
### 3.1 Remaining writers
- astrid/packs/iteration/executors/experiment_import/run.py:527 and astrid/core/threads/record.py:24 write run.json as authority. Rewire to kernel-first: check if a kernel run exists for the project/run, if so write run.json as derived projection (authority: kernel) or skip authoritative write. If no kernel run, document as non-authority storage. Remove authoritative semantics from these writers. Keep load_run_record for historical dirs.

### 3.2 Orchestrator children as kernel tasks
- For orchestrators with static plans (where child list is known at admission), admit children at run creation time (fan-out). For dynamic planned_commands (runtime-built), admit per-step via task client. Implement for at least one orchestrator (e.g. video_editing/event_talks or a test orchestrator) as proof, with hard-dependency edges where order matters.

Verify: grep zero unauthorized run.json writers outside core/project; orchestrator with N children → 1 run + N tasks, correct claimed/started/completed chains, dependent unblocks, zero run.json authoritative writes.

North Star: ONE store, ONE execution path, honest docs.
