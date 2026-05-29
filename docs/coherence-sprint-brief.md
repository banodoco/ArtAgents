# Astrid Coherence Sprint — megaplan brief

**Status:** ready to launch *after* `astrid-quality-sprint-20260528` merges to main (this plan builds on its deliverables: `astrid/core/subprocess_env.py`, `astrid/core/pack_discovery.py`, the extracted `gate.py` modules, the hygiene/CI/coverage/constraints work, and the Remotion/`clip_extract` honesty fixes — do **not** redo those).

**Launch command (post-merge):**
`python -m megaplan init --project-dir <Astrid> --robustness full --from-doc docs/coherence-sprint-brief.md "<the Goal section below>"`

## Goal

Kill the **"twin / drift" duplication** in the Astrid runtime, establish **single sources of truth**, give the runtime a **canonical status/error contract**, and make the **agent-facing surface honest**. Source: a 5-lens codebase audit (core decomposition, error model, pack-author ergonomics, CLI/agent surface, test architecture). The unifying defect: the same rule is encoded in two places that silently diverge, and human text leaks onto machine-readable channels.

## Why

- The two most common defect classes found span every subsystem: (1) **twin/drift** — Executor/Orchestrator are hand-maintained copies of one concept; `packs validate` and the runtime loader are different validators; two `EventLogError` hierarchies; status vocabularies that don't match; CI exclusion duplicated as a path list vs markers. (2) **human/machine stdout mixing** — the exact bug class hit twice during the quality sprint, present natively in `executors run`.
- These cause real, observed failures: a "valid" pack that explodes at load; `success=False`/`error=None`-while-a-task-flips-`blocked`; cold agents pointed at session-gated commands by the README.

## Milestones (sequence quick-wins first to de-risk the structural work)

### M1 — Surface honesty (quick wins, all S)
- `executors run`: send the `shlex.join(command)` echo to **stderr**, keep stdout payload-only; add `--json`. (`astrid/core/executor/cli.py:811`)
- Rewrite README "Getting Started" to lead with `next`/`status`/`attach` — it currently instructs cold agents to run session-gated `list`/`inspect`/`run` (contradicts `docs/discovery-for-agents.md`).
- Alias `ls`↔`list` across all noun groups (`ls` for projects/sessions/runs, `list` for packs/executors/elements today).
- Add `enum` constraints to the 6 taxonomy fields in `astrid/packs/schemas/v1/pack.json:114-119` (a typo silently drops a pack from every filter).

### M2 — One validator (M)
- Make `packs validate` (`astrid/packs/validate.py:303`, JSON Schema) call the runtime validators (`validate_executor_definition`/`validate_orchestrator_definition`) after the schema pass — or generate the JSON Schemas from the `astrid/contracts/schema.py` dataclasses. One source of truth.
- Reconcile the fictional `runtime:` block: loaders read `metadata.runtime_module` and ignore the documented `runtime:` block (`executor.json:16`, `orchestrator.json:5`). Promote the load-bearing keys to first-class schema fields or make resolvers honor `runtime:`; drop the double-declaration in built-in orchestrators.

### M3 — Capability core unification (M–L; SPLIT into granular tasks)
- Extract the duplicated schema-validator primitives from `executor/schema.py` + `orchestrator/schema.py` into `astrid/contracts/` (parameterize the error class). [task A]
- Migrate executor runner/registry/folder onto a generic `Capability` base. [task B]
- Migrate orchestrator + element runner/registry/folder onto it + parity tests. [task C]
- Also relocate `_run_is_complete` out of `task/events.py` (it lazy-imports `plan.py` to dodge a cycle and is monkeypatched in `lifecycle.py:69`) into a proper run-state module.

### M4 — Canonical status/error contract (M; SPLIT)
- One `RunStatus` enum **including `blocked`** in `contracts/`; map the external reigh Title-Case wire format at the boundary only. [task A]
- Structured `ExecError{code,type,message,recovery}` on `ExecutorRunResult`/`GenerationResult`; make `ok` derive from `error is None`, not `returncode is None` (built-ins must set `returncode=0`). [task B]
- Merge the two `EventLogError` hierarchies (`task/events.py:56` vs `timeline/eventlog/types.py:14`) under a shared base. [task C]
- Add a `code:` slug to `TaskRunGateError` + the worker `_fail` path so agents branch on codes, not prose. [task D]

### M5 — Test ergonomics (M; SPLIT)
- Adopt the existing `mint_session`/`seed_project` factories (the 8-field `Session(...)` literal is copy-pasted in ~30 files); add `make_session(**overrides)`. [task A]
- Add one `run_cli(main, argv) -> CliResult` helper; standardize the 54 files reinventing stdout capture. [task B]
- Replace the `--ignore=` path list in `scripts/reshape/run_ci_checks.sh:11-24` with `@pytest.mark.integration`/`opt_in` markers (the suite already filters on them). [task C]
- **Sandbox `tests/agentic/`**: it writes to the developer's real `~/Documents/reigh-workspace/astrid-projects` + `~/.astrid` (`tests/agentic/cleanup.py:43`) and is invisible to pytest (CI never runs it; grades on stderr regex). Point it at `$TMPDIR` and add an offline meta-test. [task D]

## Success criteria (sketch — refine in `plan`)
- `must`: `executors run` stdout is pure JSON; `packs validate` rejects what the runtime loader rejects; Executor/Orchestrator share one validator-primitive module; a single `RunStatus` enum incl. `blocked` is the only status vocabulary in core; `tests/agentic/` never writes outside a sandbox root.
- `should`: capability runner/registry duplication eliminated; `ls`/`list` symmetric; README cold-start sequence works for a fresh agent.

## Constraints / lessons baked in
- **Granular tasks only.** T9 and T12 in the prior sprint were god-tasks that overran a single worker turn. Every M3/M4/M5 milestone is pre-split above so each task fits one turn.
- Build **on top of** the quality-sprint deliverables; do not duplicate or revert them.
- Suggested: `--robustness full`. Pick vendor per `megaplan-decision`; the megaplan watchdog/output-budget fixes now make the Claude executor viable for larger tasks, but keep tasks granular regardless.
