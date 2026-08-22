# BATCH 1.1 — relax TaskRepository.complete (evidence-only completions)

You are a normal-pool executor (stealth/ox-alpha) in the worktree /Users/peteromalley/Documents/reigh-workspace/Astrid-unified-oracle (branch oracle-unified-execution). NO git commands. NO formatters.

## Task
Relax `TaskRepository.complete` so evidence-only completions work without media outputs:
1. astrid/core/repositories/tasks.py `_normalize_completion_outputs` (~3941): add a second accepted entry kind — evidence output `{ordinal, is_primary, role, path?, digest?, byte_size?, label?}` persisted with NULL `media_id`, facts in `params_json`. Keep: unique non-negative ordinals; exactly-one-primary generalized across BOTH kinds (an evidence primary takes role='result'); PreparedMedia entries unchanged.
2. `complete` (~3517): rule becomes "≥1 output OR non-empty `result`" — new optional `result: Mapping` parameter; the summary rides in the core.task.completed event payload and the receipt's result_json. Zero-output + non-empty-result must succeed; empty both → current error.
3. NO DDL change (task_outputs.media_id stays NOT NULL; catalog stays single-descriptor v1).
4. Tests: extend tests/v10/test_task_executor.py (or a sibling): zero-output complete with result replays via receipt; evidence-only primary works; mixed media+evidence ordinals unique; stale/losing unaffected; existing media paths byte-identical behavior.

## Constraints
- Do not touch user-in-flight files (generation backends, model_catalog, util/{credentials_scope,http}, generate_audio/generate_image dirs, docs/generation/**, tests/core/model_catalog/**, test_generation_backend_registry.py, generation/backends tests).
- Fresh basetemp /tmp/b11-t; rm -rf after.

## Verify
pytest tests/v10/test_task_executor.py tests/v10/test_generation_roundtrip.py -q --basetemp=/tmp/b11 → green; python3 -c "import astrid" clean.

## Report (<250 words)
Change sites (file:line), new test names, verification output.
