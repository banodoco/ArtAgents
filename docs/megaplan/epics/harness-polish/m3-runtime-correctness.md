# m3 — Runtime Correctness

## Outcome
The task-run engine never silently stalls or loses an event. Every step terminates with an
explicit, replayable terminal event **through a single choke-point**; gate errors that should
halt a run actually halt it; and the codebase has ONE error model (designed first, then applied)
instead of a mix of swallowed exceptions, `-O`-stripped asserts, and silent fallbacks. Highest-stakes
sprint: today these bugs can silently stall or corrupt a run — in production, a stuck pipeline with no error.

## Prep first (`+prep` is on) — do these BEFORE planning fixes
1. **Design the error model from the EXISTING good pattern, not a new layer.** The repo already has the
   right convention: narrow-catch-and-surface (`astrid/core/element/cli.py:42-44`,
   `astrid/core/orchestrator/cli.py:52-54` catch named exception tuples and surface to stderr) and a typed
   error hierarchy (`astrid/core/task/events.py:56-81` — `EventLogError → StaleTailError/StaleEpochError`
   with `.expected`/`.actual`). `docs/error-model.md` must **document this as the convention and describe
   post-fix reality** — it does NOT introduce a new base-class hierarchy or a `Result[T,E]` framework.
2. **Build a COMPLETE inventory** of every `except` and every runtime-validation `assert` in non-pack
   `astrid/`. The 6–8 sites listed below are a *starting set*; the real tree has 50+ `except` sites and
   20+ silent swallows (e.g. `skills/harnesses/base.py:73-74`, `skills/discovery.py:70-71,141-142`,
   `core/session/binding.py:87-88,120-121`, `core/session/cli.py:866-867`, `core/task/gate.py:1592-1593`,
   `core/timeline/migration.py:189-200,581-582`, `core/timeline/projection.py:959-960`,
   `core/project/cli.py:566,657,676,844`, `core/orchestrator/{folder.py:237,registry.py:323,337}`,
   `run_audit.py:581-582` and `pipeline.py:656-661` which swallow `KeyboardInterrupt`/`OSError`). Commit the
   inventory; triage each site **fixed / justified-with-reason / deferred-with-ticket**.
3. **Map the terminal-event paths and design the `_finalize_step` choke-point** (see below).
4. **Determine `threads/` liveness** (does any in-process concurrent caller touch `ThreadIndexStore`?) and
   **write the verdict** — this is an m3→m5a handoff artifact; m5a must not have to guess.
5. **Ground-truth the step model from CODE, not the planning docs.** `idea.md` and archived `docs/archive/project.md` contradict
   each other on the `code`/`attested`/`nested` model; the code is authoritative for this work.

## Scope (IN)
**The single choke-point (the root fix, not N patches):**
- Introduce one `_finalize_step(decision, result) -> TerminalEvent` that ALL dispatch paths funnel through,
  so no path can skip emitting a terminal event. This replaces the surgical per-path patches below with one
  guaranteed seam. The specific bugs it must close:
  - **Vanishing terminal event for attested steps.** `gate.py:1877-1879` `record_dispatch_complete` returns
    early for `step_kind == "attested"` with no event; `pipeline.py:174-175` calls it unconditionally in a
    `finally`. Result: attested steps can vanish from the log and stall cursor replay.
  - **Discarded inline-check result.** `_run_inline_checks` is surfaced on one path (`gate.py:1543`,
    `_dispatch_attested` snapshots pre/post counts → `GateDecision.inline_check_result`) but **discarded** on
    the other (`gate.py:1979`, `record_dispatch_complete`). Make the choke-point surface it on both — mirror
    the working logic at `gate.py:1541-1551`.
- **`repeat.until` swallows real gate errors.** `gate.py:929` catches `(TaskPlanError, TaskRunGateError, …)`
  broadly and turns genuine rejections (e.g. unknown step path from `resolve_produces_ref`) into
  `(False, reason)`, burning iterations to `max_iterations`. Narrow the catch so genuine gate errors propagate.
- **`_enter_repeat_for_each` control-flow mismatch.** `gate.py:1153-1155` `_reject(..., abort=False)` RAISES,
  but caller `_auto_traverse_to_leaf` (`gate.py:656`) treats it as a continue; the exception aborts dispatch
  instead of advancing to the next for_each item (`return None` at `:1151` is unreachable). Reconcile.
- **`ThreadIndexStore.locked()` per-fd flock hazard.** `astrid/threads/.../index.py:62-69` — per the prep
  liveness verdict, either fix the guard (separate fd / threading lock) if there are concurrent in-process
  users, or document "no in-process concurrent users" and scope accordingly.

**The silent-failure sweep + assert→raise (apply the error model from prep):**
- Convert every site triaged "fix" in the inventory to narrow-catch / log+raise / structured-error — never
  silent continue. Named seed sites: `pipeline.py:100-102`, `pipeline.py:656-661` (KeyboardInterrupt + silent
  `OSError` on `os.kill`; also replace its `time.sleep(0.1)` poll with `Popen.wait(timeout=…)`),
  `run_audit.py:581-582` (`except KeyboardInterrupt: pass`), `orchestrate/cli.py:490-491`,
  `threads/provenance.py:141-142`, `skills/__init__.py:241-242`, `audit/context.py:214-217`,
  `structure.py:114-116,144-146` (NOTE: this catches `except Exception` — validation-error→append-to-list;
  the earlier claim that it catches `KeyboardInterrupt` was wrong, correct it). For `orchestrate/cli.py:223-224`
  the catch is the **narrow** `OrchestrateDefinitionError` — the fix is warn-before-return, not broaden.
- **Convert `-O`-stripped runtime-validation asserts to raises.** Seed: `core/executor/install.py:239,245`,
  `core/session/cli.py:711`, `core/runpod/sweeper.py:149`, plus any surfaced by the prep `assert` grep
  (e.g. `core/timeline/events/schema/types.py:1027`, `core/executor/cli.py:520` — triage debug-only vs runtime).
- **Default audit-ledger verification.** `audit/cli.py:18-23` vs `audit/report.py:103`: verify the hash chain
  by default (or make non-verification a loud, explicit opt-out).
- **Fix the `json_schema` false-positive.** `verify/checks.py:99-122` validates only `required` keys; it is
  **re-exported as a first-class DSL primitive** (`orchestrate/__init__.py:15-16`), so every DSL user gets a
  fake validator. Implement real validation (`type`/`properties`/`pattern`/`enum`) OR rename with a committed
  rationale if full validation is architecturally infeasible.

## Scope (OUT / anti-scope)
- **No pack source changes.** Minimal call-site updates only where a pack consumes a changed core interface.
- **No taxonomy renames, no god-module splits, no CLI restructuring** — those are m5a/m5b. Touch `gate.py`
  surgically; do NOT split it here. (m4 has deferred its `pipeline.py`/`lifecycle.py` work to m5b too — keep
  m3's `pipeline.py` edits minimal and behavior-focused so m5b can restructure cleanly; note them in handoff.)
- Do not redesign the event schema or cursor model — fix bugs within the existing design.
- Do not delete `threads/` — only make its locking honest / write the liveness verdict; m5a acts on it.
- Do not build a `Result[T,E]` / decorator framework — the error model is the existing narrow-catch convention.

## Locked decisions
- One choke-point (`_finalize_step`) guarantees terminal events; don't patch paths individually.
- The error model is **documented from the existing pattern**, designed in prep, applied in the sweep (in that order — fixing sites before the model guarantees rework).
- `assert` is not runtime validation — convert to explicit raises.
- Every bug fix ships with a NAMED regression test that fails before / passes after.
- Tests assert via stable interfaces (CLI exit codes, event-log contents) where possible, so m4/m5b restructuring doesn't obsolete them.

## Open questions (resolve in prep)
- Exact set of dispatch paths that must funnel through `_finalize_step`.
- Per inventory site: narrow-catch vs log+raise vs structured-error.
- `threads/` liveness: concurrent in-process callers, or cross-process only?

## Constraints
- **Production-incident stakes** — every change needs a test; behavior-preserving where already correct.
- No new external dependencies.

## Done criteria (mechanically checkable)
- Four NAMED tests exist and pass: `test_attested_step_emits_terminal_event`,
  `test_produces_check_failure_surfaces_to_main`, `test_repeat_until_gate_error_propagates`,
  `test_for_each_advances_on_non_abort_reject`.
- A committed `except`/`assert` inventory with per-site triage exists; every "fix"-triaged site is changed.
- `_finalize_step` exists and is the sole emitter of terminal events (one call site in the dispatch loop).
- `test_audit_report_verifies_by_default` passes (CLI without `--verify` verifies the chain).
- `json_schema` either validates beyond `required` (`test_json_schema_validates_full_schema`) or is renamed
  with a committed rationale file.
- A written `threads/` liveness verdict is in the m3→m4/m5a handoff (EPIC.md).
- `docs/error-model.md` documents the existing convention (post-fix reality), referencing
  `core/element/cli.py:42-44` and `core/task/events.py:56-81`.
- No runtime-validation `assert` remains at the triaged sites (grep + inventory cross-check).

## Touchpoints
- `astrid/core/.../gate.py:656,929,1153-1155,1543,1541-1551,1592-1593,1877-1879,1979`, `:282-345` (cursor context)
- `astrid/pipeline.py:100-102,169-175,656-661`
- `astrid/core/task/run_audit.py:581-582`, `astrid/orchestrate/cli.py:223-224,490-491`, `orchestrate/__init__.py:15-16`
- `astrid/threads/provenance.py:141-142`, `astrid/threads/.../index.py:62-69`
- `astrid/skills/__init__.py:241-242` (+ harnesses/base.py, discovery.py from inventory), `astrid/audit/context.py:214-217`, `astrid/structure.py:114-146`
- `astrid/core/executor/install.py:239,245`, `core/session/cli.py:711`, `core/runpod/sweeper.py:149`, `core/timeline/events/schema/types.py:1027`, `core/executor/cli.py:520`
- `astrid/audit/cli.py:18-23`, `astrid/audit/report.py:103`, `astrid/verify/checks.py:99-122`
- Existing pattern references (read, don't edit): `core/element/cli.py:42-44`, `core/orchestrator/cli.py:52-54`, `core/task/events.py:56-81`
- New: `docs/error-model.md`
