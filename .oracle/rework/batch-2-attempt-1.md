# REWORK batch 2 attempt 1 — make sdk.invoke a real kernel admission

North Star: ONE store and ONE execution path — every invocation as kernel run+task. Anti-patterns: fake ULID as kernel id, second ledger, silent divergence.

## Findings (oracle batch-2)
- sdk.invoke synthesizes kernel ids, never touches RunRepository/ExecutionService/CapabilityTaskHandler
- CapabilityTaskHandler exists but disconnected, ad-hoc hashing, not exported
- Pack shims fake admission (mkdir), still write run.json/pack_events.jsonl, hype broken
- Tests weakened to expect zero run.json instead of proving kernel events

## Tasks
### R2.1 Fix sdk.invoke (XHARD if needed, else normal)
- In astrid/sdk/invocation.py, replace ULID synthesis with real admission: compute_spec_hash for idempotency, RunRepository.create with one child task, claim, start, construct CapabilityTaskHandler(capability_kind, capability_id, projects_root), ExecutionService.execute/complete|fail, surface real kernel_run_id/task_id/attempt_id in InvocationResult. Use projects_root from request or derive from resolved project. Keep ledger exemption for dry_run/skipped (no admission). Remove ghost comment attributing ownership to handler. Imports: RunRepository, TaskRepository, ExecutionService, CapabilityTaskHandler, compute_spec_hash, UnitOfWork.
- Verify: 3 executors via sdk.invoke → kernel events/receipts/attempts/leases, succeeded, zero authoritative run.json; generation roundtrip parity harness passes.

### R2.2 Wire CapabilityTaskHandler to kernel
- Export handler from astrid/core/task_executor/__init__.py. Fix handler: use discover_manifest_path + load_manifest_output_artifacts + prepare_media_file + validate_result_manifest (reuse service validation, don't reimplement). Handle evidence outputs per batch-1 relaxed contract. Dry-run/skipped not admitted.
- Verify: same 3 executors as above; no ad-hoc hashing.

### R2.3 Repair pack shims
- Make kernel_admission.py call real RunRepository.create (or delete and route packs through sdk.invoke with projects_root threading). Remove all run.json/pack_events.jsonl writes and finalize_project_run calls from the 3 pack orchestrators; fix hype/project_adapter missing import and KernelAdmissionContext mismatch; ensure projects_root threaded.
- Verify: pack slices green, grep zero non-projection run.json writers.

