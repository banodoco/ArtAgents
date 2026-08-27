# MEGADO TASKLIST — unified execution (frozen after pre-execution review)

Base: b4c70e0a · Worktree: ../Astrid-unified-oracle · Models: all openrouter:stealth/ox-alpha (user-pinned both classes)

## Batch 1 — completion relaxation + docs v2 (parallel-safe)
| # | Task | Class | Verify |
|---|---|---|---|
| 1.1 | Relax TaskRepository.complete: optional `result: Mapping` param; rule becomes ≥1 output OR non-empty result; exactly-one-primary only when outputs exist. Update _normalize_completion_outputs. Tests: zero-output complete w/ result replays via receipt; stale/losing unaffected; existing media-output paths unchanged. | normal | tests/core/test_task_executor.py + new cases |
| 1.2 | docs/contracts/run-ledger-contract.md v2: single-ledger contract (kernel = execution authority; FS run.json = derived projection written once from kernel state at finalize, stamped `"authority":"kernel"`, `kernel_task_id`, `kernel_run_id`; never read back as authority). SKILL.md + async-completion.md + creating-tools.md aligned. | normal | grep gates + docs-alignment |

Checkpoint B1: full tests/v10/test_task_executor.py green; conformance meta-test against new doc table green; `import astrid` clean.

## Batch 2 — CapabilityTaskHandler + sdk.invoke rewiring
| # | Task | Class | Verify |
|---|---|---|---|
| 2.1 | astrid/core/task_executor/capability_handler.py: CapabilityTaskHandler(TaskHandler) — ExecutorRunRequest(execution_mode="in_process", out=staging/out) → run_executor; orchestrator variant run_orchestrator; harvest outputs: prefer capability manifest.json else walk staging/out; classify extension/mime → PreparedMedia vs evidence entry; complete via relaxed contract. ASTRID_INTERNAL_INVOCATION=1 env. | normal | roundtrip vs direct-mode byte-compare (generation.generate_image) |
| 2.2 | sdk.invoke rewiring: admit run+one child task (RunRepository.create, compute_spec_hash idempotency key), claim/start, CapabilityTaskHandler execute, complete/fail; InvocationResult gains kernel ids (public shape stable). Update ~48 run.json-shape test files per E7 census; update run-ledger-contract conformance meta-tests. | normal | full sdk invoke suite + conformance |
| 2.3 | Self-managing pack orchestrators: event_talks/run.py:648, hype/project_adapter.py:86, thumbnail_maker/run.py:550 → shared admission shim. | normal | pack test slices |

Checkpoint B2: ≥3 executors via sdk.invoke → kernel events/receipts/succeeded, zero authoritative run.json writes; suite slices green.

## Batch 3 — remaining writers + orchestrator children
| # | Task | Class | Verify |
|---|---|---|---|
| 3.1 | Remaining run.json writers: experiment_import/run.py:527, threads/record.py:24 → kernel-first or documented non-authority. | normal | grep zero unauthorized writers |
| 3.2 | Orchestrator children as kernel child tasks where plans are static; dynamic planned_commands stay runtime-admitted. | normal | orchestrator slice |

## Batch 4 — reader flip + final verification
| # | Task | Class | Verify |
|---|---|---|---|
| 4.1 | Flip internal readers (doctor, threads attribution/provenance, timeline_visualize/frozen.py:553-587 ownership checks, experiments, project listings) to kernel-first with FS fallback; delete prepare/finalize_project_run authority semantics; keep load_run_record for historical dirs. | normal | full suite green |
| 4.2 | Empirical process harness (df-pattern): ≥6 representative capabilities each asserted as kernel run+task with correct events/receipts/terminal status and zero authoritative run.json. | normal | harness output |

## North Star alignment
Every batch advances ONE store / ONE execution path / every-run-observable / honest-docs / KISS. Anti-patterns guarded: no second authority (projection write-once-from-kernel), no silent divergence (fail-closed binding), no ghost claims, no per-executor adapters, no serve/GPU supervision scope creep.

## Classification rationale
All tasks normal: bounded, mechanically specified, locally verifiable; no irreducible judgment kernel exceeds the normal pool. Zero [XHARD].
