**Verdict: FAIL — rework is real on `sdk.invoke` but `kernel_admission` is still ghost; North Star not yet single-ledger.**

Delta `dddc0ae9..588018f3` (12 astrid files +621/-389) fixes the executor path, leaves pack shims and fallback/elegance debt.

### What now passes (evidence)

* **B2.1 `CapabilityTaskHandler` PASS** — `capability_handler.py:17-20` imports `validate_result_manifest, prepare_media_file, discover_manifest_path, load_manifest_output_artifacts`; `199` `prepare_media_file(...).digest/.byte_size` replaces ad-hoc `hashlib`; `221` reuses service validation; `184-194` evidence-only `outputs:[]`; exported at `task_executor/__init__.py:25,39`; `ASTRID_INTERNAL_INVOCATION` scoped at `81`; `out=None when project set` at `87/112`.

* **B2.2 `sdk.invoke` kernel path PASS (when it succeeds)** — `_kernel_invoke:316` `compute_spec_hash`, `345-354` `RunRepository.create(children=[{capability, spec}], idempotency_key)`, `360-361` `TaskRepository.claim(claim_key=idempotency_key+":claim")`, `364` `CapabilityTaskHandler`, `365-375` `ExecutionService.execute` / `381` `complete` via `MediaRepository`; `EventAppendService+ReceiptService` threaded at `332-336`; `DatabaseWriter(db_path, core_only_registry)` correct at `326-329`; dry_run exempt at `444`. Live probe: `astrid.invoke(..., project_root=tmp)` creates `kernel.sqlite3` with `runs=1, tasks=1, events=6, receipts=5, attempts=1, leases=1` and surfaces real `kernel_run_id/task_id/attempt_id` (not ULID synthesis; `_kernel_ids_for_invoke:288-295` now dead code).

* **Zero authoritative `run.json` outside `core/project` PASS** — `grep write_json_atomic.*run\.json` outside `core/project` = 0; `grep write_json_atomic` in `packs/video_editing` = 0; `grep prepare|finalize_project_run` in packs = 0; `executor/runner.py:852-867` returns `None, request` (no ledger). `core/project/run.py:321,482` remains sole authority (derived projection).

* **Pack shim threading PASS (structural)** — `event_talks:585-602`, `thumbnail_maker:506-522`, `hype/project_adapter:38-54` all pre-parse `--projects-root`, `resolve_projects_root(None)` fallback, `admit_orchestrator_project_run(projects_root=projects_root)`.

### Why still FAIL — evidence-backed issues (fix before ship)

**P0 — `kernel_admission.py` is ghost (3 broken imports hidden by `except: pass`)**

Live: `admit_orchestrator_project_run` always returns `mkdir` context, never creates kernel row — `exists kernel.sqlite3 == False` in probe.

* `kernel_admission.py:51` `DatabaseWriter(root)` — needs 2 args `DatabaseWriter(path, registry)` (`writer.py:303`). Also wrong path (directory `root`, not `root/kernel.sqlite3` or `database_path(root)`). Fix: `db_path = Path(root)/"kernel.sqlite3"; writer = DatabaseWriter(db_path, registry)`.
* `kernel_admission.py:47,50` `from ... database import ensure_database` — `database.py` exports only `open_database`. `ImportError` every call. Fix: delete `ensure_database` call; `DatabaseWriter` already opens/migrates on construction (or call `open_database` if needed).
* `kernel_admission.py:53` `from ...events.registry import EventAppendService` — wrong module. Correct: `from astrid.core.events.service import EventAppendService` (`service.py:272`; `registry.py` has none). Proven `ImportError` on import.

All three swallowed at `93-94,85-87,63-64` `except Exception: pass` → callers see filesystem `run_root` but kernel has zero `events/receipts`. This is the exact second-ledger ghost the North Star kills.

**P0 — `sdk.invoke` silent fallback masks kernel failures (elegance = ghost)**

`invocation.py:552-553` `except Exception: pass` after `_kernel_invoke` then `555-646` fallback to legacy `run_executor/run_orchestrator` with `kernel_*=None`. Kernel bug (handler `TypeError: expected str, bytes or os.PathLike object, not NoneType` seen in live probe — handler received `projects_root=None`, `staging_dir` handling) silently succeeds via fallback with `ok=True` but no kernel rows. Caller cannot distinguish. **KISS fix:** delete fallback block `555-646`, let `_kernel_invoke` failures raise `CapabilityInvocationError`; keep only `dry_run` exemption. `sdk.invoke` is the thin admission wrapper — it must be one path.

**P1 — Orchestrator/executor runner asymmetry**

Executor `runner.py:852-867` is single-ledger; orchestrator `runner.py:582-614,668-677` still `prepare_project_run`/`finalize_project_run` → `run.py:321,482` authoritative `run.json`. Mixed fleet = two authorities. Gate requires zero authoritative writes — demote orchestrator to projection (`write only when not ASTRID_INTERNAL_INVOCATION` or via `TASK_RUN_ID_ENV` attached path at `run.py:238-290`) or document as derived.

**P1 — Pack admission duplication / wrong fan-out**

`kernel_admission.py:66-70` reinvents `hashlib.sha256(json.dumps(tool_id+argv))[:32]` vs canonical `compute_spec_hash` used by `sdk` (`invocation.py:342-343`); `children=[]` zero-child run vs `children=[{capability, spec}]` one-child task. Pack runs have no child task to `claim/start/complete`. **KISS fix:** extract one helper `admit_kernel_run(*, project, kind, spec|tool+argv, projects_root) -> KernelAdmissionContext` that resolves root once, computes `compute_spec_hash`, does `projects.create + runs.create`, returns `fanout.run_id` (delete pre-generated `run_id=ULID:36` and derive `run_root` from real id). Both SDK and pack call it (pack wrapper = 6 lines).

**P2 — Elegance debt (cut scope)**

* `invocation.py:288-295` `_kernel_ids_for_invoke` dead code — delete (grep shows zero callers).
* `invocation.py:342-344` duplicate `spec_payload`/`child_spec` byte-identical — one dict: `child_spec = {...}; idempotency_key = compute_spec_hash(child_spec, [])`.
* `invocation.py:297-304` `_resolve_projects_root` duplicate of `foundation.project_paths.resolve_projects_root` with extra `cwd` fallback — delete wrapper.
* `executor/runner.py:892-922 + 924-953` duplicate `_validate_project_owned_inputs` — delete one; `984-1009` `_finalize_project_executor` unreachable — delete or gate.
* `invocation.py:360-381` `f"{idempotency_key}:claim/:exec/:complete"` semantics undocumented — claim idempotency means duplicate invoke reuses same `attempt` (not new lease); if each `sdk.invoke` should be new attempt, nonce needed.
* **Generation parity harness missing** — `tests/v10/test_generation_roundtrip.py` proves kernel-only path; no `direct run_executor vs kernel sdk.invoke byte-compare` for `generation.generate_image` as brief requires §2.1. Pack slices `62 passed,1 skipped` vacuously green (assert `records==[]` without asserting kernel rows) — add one test: `direct = run_executor(req) ; kernel = sdk.invoke(...) ; assert direct_bytes == kernel_bytes` + `kernel.sqlite3` events/receipts.

### Minimal fix order (KISS)

1. Fix `kernel_admission.py` imports/signatures (3 lines) and remove `ensure_database` pre-generation ULID.
2. Unify admission helper, switch pack `hashlib` → `compute_spec_hash`.
3. Delete `sdk.invoke` fallback + dead ULID helper + duplicate spec/resolve; surface kernel errors.
4. Demote orchestrator runner ledger or gate behind invocation flag.
5. Add generation byte-compare parity test; tighten `test_run_ledger_conformance` to assert kernel `events/receipts/attempts/leases` not just `records==[]`.

Until (1)+(2) land, `≥3 executors via sdk.invoke` gate is true for `sdk` path but pack orchestrators remain filesystem-only ghosts; run-contract v2 (`kernel owns ledger, FS at most derived projection`) is not yet honest for orchestrators.


