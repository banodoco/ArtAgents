**Verdict: FAIL** — batch 2 is a veneer, not ONE store/ONE path. Three pooled critiques (muse-spark) concur: every 2.x task fakes kernel admission.

### Why it fails the North Star + B2 acceptance

**B2 requires:** ≥3 executors via `sdk.invoke` → kernel `run/task` with hash-chained `events/receipts/attempts/leases`, `succeeded`, zero authoritative `run.json`; `CapabilityTaskHandler` in-process + manifest synthesis + media classification + relaxed `complete`; 3 pack shims via shared kernel helper. **Delta `dddc0ae9..f0cad9ea` (10 files, +348/-178) does none.**

#### 2.2 `sdk.invoke` — faked, not admitted
* `astrid/sdk/invocation.py:288-294` `_kernel_ids_for_invoke` = `generate_lowercase_ulid()` + `uuid4.hex`. No `RunRepository.create`, no `compute_spec_hash`, no idempotency, no `UoW`.
* `astrid/sdk/invocation.py:346-394` still calls `run_executor`/`run_orchestrator` directly (`execution_mode="subprocess"` default, `316`), then `417-429` post-hoc stamps `kernel_run_id/kernel_task_id/kernel_attempt_id` onto `raw_result` if not `dry_run/skipped`. `except Exception: pass` silently leaves them `None`. Zero imports of `RunRepository`, `ExecutionService`, `CapabilityTaskHandler`, `ASTRID_INTERNAL_INVOCATION`.
* `astrid/sdk/results.py:129-156` adds `kernel_*` fields — shape-stable (additive) → passes shape check, fails semantics: ids point nowhere. No events/receipts exist to assert.
* `astrid/core/project/kernel_admission.py:23-43` docstring claims "same kernel admission path as `sdk.invoke`" — both are fake: `ULID + mkdir` under `projects_root/<slug>/runs/<id>` or `/tmp/astrid-kernel-<id>` (all pack callers omit `projects_root` so they land in `/tmp`). Ignores `tool_id`/`argv`. No writer.

**Run contract v2 violated:** `astrid/core/project/run.py:320-321` still `write_json_atomic(run.json)` at `prepare` as authority; `astrid/core/execution/orchestrator/runner.py:595` still calls it. `astrid/core/execution/executor/runner.py:852-868` demoted to `return None, request` with comment "kernel owns ledger" but no kernel write replaces it — project executor runs now have *neither* kernel row nor `run.json` in that path. Ghost comment `858-859` attributes ownership to `sdk.invoke/CapabilityTaskHandler` which `invoke` never calls. Dead import `prepare_project_run:42` remains; `_finalize_project_executor:984-1014` still finalizes if a context existed.

#### 2.1 `CapabilityTaskHandler` — disconnected harvest veneer
* `astrid/core/task_executor/capability_handler.py:1-222` exists but: never classifies `PreparedMedia` vs evidence, never calls `ExecutionService`/`TaskRepository.complete`, not exported from `astrid/core/task_executor/__init__.py`, unreachable from `sdk.invoke`. Harvest duplicates `discover_manifest_path` then ad-hoc `rglob` + sort + `sha256(read_bytes())` (`133-210`), invents `outputs=[{path, content_hash, bytes, ordinal, is_primary, role}]` without declared-output filtering. Empty staging returns `outputs: []` with `created: task.created_at or ""` (`190-202`) — fails `validate_result_manifest` (`_shared/result_manifest.py:385-401` rejects empty `outputs`/`created`). ExecutionService contract (`service.py:350-364`, `659-695`) requires *exactly one primary* `PreparedMedia` via `prepare_media_file`; handler bypasses it. In-process `ASTRID_INTERNAL_INVOCATION=1` + `run_executor` is present, but completion via relaxed `result` param (`repositories/tasks.py:3640-4165`) is never exercised — bespoke adapters `generate_image/task_adapter.py:276-344` and `timeline_visualize/task_adapter.py:261-292` remain the only real handlers.

*Elegance:* Delete the ad-hoc hashing/sorting walk; reuse `discover_manifest_path` + `load_manifest_output_artifacts` and the service's `prepare_media_file`/`validate_result_manifest`. KISS is one generic path, not a dict that mimics a manifest while the real validation lives elsewhere. YAGNI: handler should *be* the `TaskHandler` that `ExecutionService` validates, not a parallel manifest factory.

#### 2.3 Pack shims — staging-only fake, one broken
* Same `kernel_admission.py` fake. All three omit `projects_root`.
* `event_talks/run.py:23-26` still imports unused `prepare/finalize_project_run`; `387-444` still writes `run.json` + `pack_events.jsonl` (second event log). `637-666` replaces `prepare` with fake admit but never finalizes.
* `thumbnail_maker/run.py:22-23` cleanest — drops `prepare/finalize` imports — but still writes `run.json:271-297` + `pack_events.jsonl:300-313`, fake admit `545-550`.
* `hype/project_adapter.py:34-55` comments "staging-only", calls fake admit; `15-22` leaves unused `bind_managed_timeline`; `hype/run.py:118-207` still calls `finalize_project_run` on a `KernelAdmissionContext` (no `.run`/`.run_json_path`/`.root` → `project_context.run.get` at `151` is `AttributeError`; `NameError` at `project_run_env` — imported name removed but call `63-64` remains). Second ledger remains terminal authority via `hype/runner.py:35-43` `_write_run_json`.

#### Contract/test honesty
* `tests/test_run_ledger_conformance.py:32--` registry now asserts `records == []` for `TestSDKImageProject:432`, `TestSDKVideoOut:475`, etc. — tests were weakened to expect zero `run.json` instead of proving kernel events/receipts replaced them. Generation roundtrip parity not proven (vs direct-mode byte-compare required by tasklist 2.1). Pack slices cannot be green with `hype` type mismatch.

### What to fix (minimal, KISS)
1. **Make `sdk.invoke` the thin admission wrapper:** `RunRepository.create` + `compute_spec_hash` idempotency → `claim/start` → construct `CapabilityTaskHandler(capability_kind, capability_id, projects_root)` → `ExecutionService.execute/complete|fail` (or handler does `claim/start`/`complete` via `TaskRepository.complete(result=...)` under relaxed contract). Surface real `kernel_run_id/task_id/attempt_id` from the created rows. Default `execution_mode="in_process"` when routed through handler; keep subprocess path only for historical readers.
2. **Wire the handler to the kernel:** export it, have it call `prepare_media_file` + `validate_result_manifest`, return `PreparedMedia` for media-like outputs and evidence entries otherwise, call `complete` with `outputs OR result` (batch 1 relaxation). Delete bespoke-adapter duplication once parity passes by reusing declared `manifest.json` outputs.
3. **Repair pack shims or delete them:** either route all three through the real `sdk.invoke`/handler path with `projects_root` threading, or make `kernel_admission.py` actually call `RunRepository`/`EventStore`. Remove pack-local `run.json`/`pack_events.jsonl` writes and `finalize_project_run` calls; fix `hype/project_adapter.py` missing `project_run_env` import and `KernelAdmissionContext` vs `ProjectRunContext` mismatch. Until kernel-backed, staging-only helper is ghost behavior — cut it.
4. **Restore authoritative `run.json` semantics:** demote `prepare_project_run`/`finalize_project_run` to derived projection (`write once from kernel state at finalize, authority: kernel`) or delete; don't leave orchestrator runner writing authority while executor runner writes nothing. Remove dead imports, deduplicate `_validate_project_owned_inputs`.
5. **Prove B2 gate empirically:** ≥3 executors (e.g. `generation.generate_image`) via `sdk.invoke` → assert kernel `events`/`receipts`/`succeeded` + `attempts/leases` + managed outputs byte-identical to direct mode, and `grep -r "write_json_atomic.*run.json"` shows zero non-projection writes.

Do not ship ULID synthesis as "kernel ids" — it hides the second-ledger divergence the North Star exists to kill.

0
