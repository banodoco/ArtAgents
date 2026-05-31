# M1 — Embed Sisypy + foundation (adapter, runner, evidence capture, universal checks)

Companion design doc: `docs/megaplan/epics/astrid-sisypy/design.md` (read it — §2 lists the 12 universal checks, §6 the migration mapping).

## Outcome
A working Sisypy harness embedded in Astrid at `tests/agentic/` that can run a scenario end-to-end with the **fake** actor in **structural** mode, freeze an Astrid-specific evidence pack, and apply the 12 universal data-integrity/evidence checks over that frozen pack. This milestone is the architectural keystone the other three milestones build on — its adapter API surface and evidence-pack contract are the handoff artifact.

## Scope (IN)
- Add Sisypy as a dependency the runner can import (the Sisypy repo is a sibling at `/Users/peteromalley/Documents/reigh-workspace/sisypy`; install `-e` or vendor per whatever Astrid's existing dep strategy is — DO NOT modify the Sisypy repo).
- Create `tests/agentic/adapter.py` subclassing Sisypy's project adapter base (start from `FakeProjectAdapter` per Sisypy's `docs/embedding.md`). Implement the Astrid-specific overrides:
  - `prime()` / workspace priming — translate Astrid's existing priming verbs (`create_project`, `start`, `ack`, `write`, `touch`, `env`) into Sisypy's prime hook, preserving the `ASTRID_SESSION_ID` threading.
  - `build_env()` — structural vs live env (strip creds/GPU in structural mode).
  - `capture()` — freeze Astrid-specific evidence into the pack ON TOP of Sisypy's core capture: the timeline event log `assembly.jsonl` + `assembly.head.json` + `assembly.identity.json`, the run record `run.json`/`current_run.json`, per-step `events.jsonl`, the audit `ledger.jsonl` (where present), `plan.json`, `.astrid-session`, and the output of `verify_chain` on each chained log.
  - `command_policy()` / `canonical_bypass_patterns()` — port the existing bypass patterns (`python -m astrid.packs.X.run`, `from/import astrid.packs.X`, direct `astrid/packs/X/run.py`).
  - `classify_success()` — map Astrid evidence onto Sisypy's proof ladder (authored→…→artifact_proven) per design §6.
- Create `tests/agentic/runner.py` wiring `cli()` / `console_cli()` to the Astrid adapter (per `docs/embedding.md`).
- Implement the **12 universal checks** (design §2) as `project_universal_checks()` over the frozen evidence pack — deterministic Python, no LLM:
  1 claim-vs-evidence, 2 canonical-bypass, 3 no-mutation-on-read, 4 append-not-rewrite, 5 chain-integrity (verify_chain on assembly.jsonl / run events.jsonl / ledger.jsonl), 6 artifact-provenance (produces path exists + sha256 match), 7 projection-fidelity (project_to_assembly(events)==assembly.json), 8 head/sidecar consistency, 9 idempotent-reattach, 10 no-cross-project-leak, 11 auditability, 12 deliverable-shape.
  Each check reads only frozen files and returns a structured pass/fail/na with evidence refs. Checks that don't apply to a given pack return `na`, never error.
- One smoke scenario (`tests/agentic/scenarios/_smoke.yaml` + brief) that runs with the fake actor in structural mode and exercises capture + at least 3 universal checks end-to-end.
- A pytest (mirror `vibecomfy/tests/test_sisypy_integration.py`) asserting the adapter satisfies the Sisypy interface and the structural smoke run produces a well-formed evidence pack.

## Locked decisions
- Keep the suite at `tests/agentic/` (replace the bespoke harness in place — see anti-scope for what stays until M2).
- Evidence-over-narrative: universal checks read FROZEN evidence only, never live repo state.
- The shared Sisypy package must NOT import Astrid code; all Astrid semantics live in the adapter.
- Reference embedder is `vibecomfy/tests/test_sisypy_integration.py` + Sisypy `docs/embedding.md`, `docs/evidence.md`.

## Open questions for the planner to resolve
- Dependency wiring: editable-install Sisypy vs add to pyproject vs PYTHONPATH shim — pick what matches Astrid's existing `pyproject`/packaging and is reproducible in CI.
- Whether `verify_chain` is callable as a library function from the adapter or must be shelled via `astrid timelines audit` / `astrid events verify` — inspect `astrid/core/timeline/eventlog/local_fs.py` and `astrid/core/timeline/cli.py`.
- Where the projection comparison gets the canonical `assembly.json` (it may be derived-on-read, not persisted) — see `astrid/core/timeline/projection.py`.

## Constraints
- Structural mode must run with NO network, NO GPU, NO cloud spend, NO model downloads.
- Universal checks must be fast (whole battery < a few seconds on a small pack) and total-functional (a missing artifact → `na`/`skip`, never a crash) — mirror Sisypy's best-effort partial-capture contract.

## Done criteria
- `python -m tests.agentic.runner --help` works.
- `python -m tests.agentic.runner _smoke --actor fake --mode structural --no-parallel --verbose` produces an evidence pack under `out/agentic/reports/` containing the Astrid-specific captures and a universal-checks result block.
- The new pytest passes.
- A short `tests/agentic/ADAPTER.md` documents the adapter API surface, the evidence-pack contents, and the 12 universal checks — this is the handoff artifact M2–M4 cite.

## Touchpoints
- `tests/agentic/` (new adapter.py, runner.py, ADAPTER.md, _smoke scenario+brief)
- read-only refs: `astrid/core/timeline/eventlog/local_fs.py`, `projection.py`, `astrid/core/project/run.py`/`paths.py`/`schema.py`, `astrid/core/task/events.py`, `astrid/core/orchestrator/cli.py`, the Sisypy repo, the vibecomfy integration test.

## Anti-scope
- Do NOT migrate the 29 existing scenarios yet (that's M2) — leave the existing `runner.py`/`auditor.py`/`assessor.py`/`scenarios/*.yaml` in place, renamed or sidelined as needed so both can coexist until M2 cuts over. If a name collides on `runner.py`, preserve the old one as `runner_legacy.py` and note it.
- Do NOT build net-new scenarios (M3/M4).
- Do NOT modify the Sisypy repo or any `astrid/` production code (only read it). If a real Astrid bug blocks a check, note it (there are already filed tickets) and make the check report it, don't fix Astrid here.
