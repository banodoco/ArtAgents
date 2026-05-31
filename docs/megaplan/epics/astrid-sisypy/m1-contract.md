# M1 — Freeze the contract + minimal Sisypy adapter + capture + smoke

Companion: `docs/megaplan/epics/astrid-sisypy/design.md` (§2 = the classified check battery + the THREE-logs correction). Read it. This milestone deliberately does NOT implement the check battery (that is M2) — it freezes the contract everything else builds on.

## Outcome
1. A FROZEN `tests/agentic/ADAPTER.md` contract, written and committed FIRST, before adapter code.
2. A minimal Sisypy adapter + runner embedded at `tests/agentic/` that primes an Astrid workspace, captures an Astrid evidence pack matching the ADAPTER.md layout, and runs ONE structural (fake-actor) smoke scenario end-to-end. No integrity checks beyond what Sisypy's base provides.

## Scope (IN)
### A. `tests/agentic/ADAPTER.md` — the frozen contract (write + commit this first)
Must specify, concretely and verified against the actual code:
- **Evidence-pack layout**: every file/dir the Astrid pack contains on top of Sisypy's core pack (Sisypy core: report.md, stdout/stderr.log, actions.jsonl, tree_before/after.txt, git_diff.patch, manifest.json — see sisypy/docs/evidence.md).
- **The THREE persistence logs, each with its EXACT capture path and verifier function** (do NOT conflate — this was the #1 review finding):
  - Timeline chain — `<proj>/<slug>/timelines/<ulid>/assembly.jsonl` (+ `assembly.head.json`, `assembly.identity.json`) → verifier `LocalFsBackend.verify_chain()` in `astrid/core/timeline/eventlog/local_fs.py`.
  - Task-run chain — `<proj>/<slug>/runs/<id>/events.jsonl` → verifier `astrid.core.task.events.verify_chain(path)`. Artifact hashes are in `produces_check_passed.cas_sha256` events (see `astrid/core/task/events.py` make_produces_check_passed_event), NOT in run.json.
  - Audit ledger — `<proj>/<slug>/runs/<id>/audit/ledger.jsonl` → verifier `verify_audit_ledger()` in `astrid/audit/graph.py` (NOT verify_chain).
  - Also document `run.json`/`current_run.json` (run record; path/source-path artifacts, no hashes) and `.astrid-session`, `plan.json`.
  - Note `assembly.json` (derived projection) is REGENERATED on normal reads (`astrid/core/timeline/crud.py`); only a frozen read-only snapshot taken before regeneration is usable for projection-fidelity.
- **Check result shape**: the JSON each check returns — `{id, status: pass|fail|na, evidence_refs, detail}` — and that `na` is scored as pass (skip).
- **The check CLASSIFICATION** (copy design §2): UNIVERSAL U1-U6, CONDITIONAL C1-C4, SCENARIO-SPECIFIC S1-S2 — with the trigger that makes each conditional/scenario check apply, and the erasure/repair exemption for S1. M1 only DOCUMENTS these; M2 implements them.
- **Dispatch model**: how Sisypy actors map to Astrid's existing model values (claude via Agent tool; deepseek-v4-pro / kimi-k2p5 via hermes-subagent) and how structural/fake mode is selected.

### B. Minimal adapter + runner
- `tests/agentic/adapter.py` subclassing Sisypy's project adapter (start from `FakeProjectAdapter`; see sisypy/docs/embedding.md). Implement: `prime()` (translate Astrid priming verbs create_project/start/ack/write/touch/env, preserving ASTRID_SESSION_ID threading), `build_env()` (structural strips creds/GPU), `capture()` (freeze the three logs + heads + run.json/current_run.json + plan.json + .astrid-session + a frozen read-only assembly.json snapshot, exactly per ADAPTER.md; best-effort, missing artifact → skip note, never crash), `command_policy()`/`canonical_bypass_patterns()` (port existing bypass patterns), `classify_success()` (Astrid → Sisypy proof ladder).
- `tests/agentic/runner.py` wiring Sisypy `cli()`/`console_cli()` to the adapter (sisypy/docs/embedding.md).
- ONE smoke scenario `tests/agentic/scenarios/_smoke.yaml` + brief that runs fake/structural and exercises capture of at least the task-run events log + tree.
- A pytest (mirror `vibecomfy/tests/test_sisypy_integration.py`) asserting the adapter satisfies the Sisypy interface and the smoke run produces a well-formed pack matching ADAPTER.md.

## Locked decisions
- Suite stays at `tests/agentic/`. The legacy harness (`runner.py` legacy, `auditor.py`, `assessor.py`, `capture.py`, `universal_checks.py`) STAYS in place this milestone — coexist; if `runner.py` name collides, preserve old as `runner_legacy.py`. No decommission until M5.
- Sisypy is imported, never modified; shared Sisypy package must not import Astrid.
- Evidence-over-narrative: capture freezes files; nothing reads live repo state at check time (checks are M2).

## Open questions for the planner
- Dependency wiring for Sisypy (editable install vs pyproject vs PYTHONPATH) matching Astrid packaging + CI.
- Whether each verifier is callable as a library function (confirm signatures: `LocalFsBackend.verify_chain`, `astrid.core.task.events.verify_chain`, `astrid.audit.graph.verify_audit_ledger`) or must be shelled via CLI; ADAPTER.md records the chosen call.
- How/when to snapshot the read-only `assembly.json` before regeneration (capture hook ordering).

## Constraints
- Structural mode: NO network/GPU/cloud/model-downloads.
- Capture is best-effort + total-functional (missing artifact → documented skip, never an exception).

## Done criteria
- `tests/agentic/ADAPTER.md` exists, committed, and is internally consistent with the actual verifier signatures (cite them).
- `python -m tests.agentic.runner --help` works.
- `python -m tests.agentic.runner _smoke --actor fake --mode structural --no-parallel --verbose` produces an evidence pack matching ADAPTER.md (the three logs captured when present, with skip notes when absent).
- The pytest passes.

## Touchpoints
- `tests/agentic/` (new ADAPTER.md, adapter.py, runner.py, _smoke scenario+brief, pytest). Read-only: `astrid/core/timeline/eventlog/local_fs.py`, `astrid/core/timeline/crud.py`, `astrid/core/task/events.py`, `astrid/audit/graph.py`+`context.py`, `astrid/core/project/run.py`/`paths.py`/`schema.py`, the Sisypy repo, vibecomfy integration test.

## Anti-scope
- Do NOT implement the integrity check battery (M2).
- Do NOT migrate the 29 scenarios (M3) or build net-new scenarios (M4/M5).
- Do NOT decommission the legacy harness.
- Do NOT modify `astrid/` production code or the Sisypy repo (read only). Filed tickets already track Astrid defects; if a defect blocks capture, document it in ADAPTER.md, don't fix Astrid here.
