# m3 — Runtime Correctness

## Outcome
The task-run engine never silently stalls or loses an event. Every step terminates with an
explicit, replayable terminal event; gate errors that should halt a run actually halt it; and
the codebase has ONE error model instead of a mix of swallowed exceptions, `-O`-stripped
asserts, and silent fallbacks. This is the highest-stakes sprint: today these bugs can
silently stall or corrupt a run, which in production = a stuck pipeline with no error.

## Scope (IN)
**Runtime event/cursor bugs (all in `astrid/core/.../gate.py` + `astrid/pipeline.py`):**
- **Vanishing terminal event for attested steps.** `gate.py:1877-1879` `record_dispatch_complete`
  returns immediately when `step_kind == "attested"` with no event emitted, but `pipeline.py:174-175`
  calls it unconditionally in a `finally`. Ensure every step (attested included) reaches a terminal
  event (`step_completed`/`step_attested`/`step_failed`) so cursor replay can't stall.
- **Discarded inline-check result.** `_run_inline_checks` is called from two paths with asymmetric
  surfacing: `gate.py:1543` (`_dispatch_attested` snapshots pre/post counts, populates
  `GateDecision.inline_check_result`) vs `gate.py:1979` (`record_dispatch_complete` discards the
  return). A code step with a failed `produces` check appends `produces_check_failed` but the caller
  never learns — the run silently stalls. Make both paths surface the failure to `main()`.
- **`repeat.until` swallows real gate errors.** `gate.py:929` `_evaluate_repeat_until_expression`
  catches `(TaskPlanError, TaskRunGateError, ...)` broadly and turns ALL of them — including genuine
  rejections like an unknown step path from `resolve_produces_ref` — into `(False, reason)`, burning
  iterations to `max_iterations` instead of halting. Narrow the catch so genuine gate errors propagate.
- **`_enter_repeat_for_each` control-flow mismatch.** `gate.py:1153-1155` calls
  `_reject(..., abort=False)` which RAISES, but the caller `_auto_traverse_to_leaf` (`gate.py:656`)
  treats it as a normal continue; the exception propagates through `gate_command` and aborts dispatch
  instead of advancing to the next for_each item. The `return None` at `:1151` is unreachable. Reconcile
  intended control flow (advance vs. abort) and make the code match it.
- **`ThreadIndexStore.locked()` per-fd flock hazard.** `astrid/threads/.../index.py:62-69` uses
  `fcntl.flock` whose locks are per open-file-description; threads sharing the handle don't block each
  other. Confirm whether any in-process concurrency touches `ThreadIndexStore`; if so, fix the guard
  (separate fd per acquisition, or a threading lock layered on top). If `threads/` is confirmed dead
  (see m5), document that and scope the fix to "no in-process concurrent users" rather than over-building.

**The silent-exception sweep + one error model (cross-cutting):**
- Replace failure-hiding `except Exception: pass` / silent fallbacks at minimum:
  `astrid/pipeline.py:100-102` (nudge errors incl. import errors),
  `astrid/orchestrate/cli.py:490-491` (disambiguation warnings) and `:223-224` (cost-collection early return),
  `astrid/threads/provenance.py:141-142` (`return "Unknown thread"` swallows all index errors),
  `astrid/skills/__init__.py:241-242` (`fs_record = None` hides adapter-discovery failures),
  `astrid/audit/context.py:214-217` (`register_outputs` silently drops missing files),
  `astrid/structure.py:114-116,144-146` (catches `KeyboardInterrupt`/`SystemExit`).
  For each: either narrow the catch, log+re-raise, or surface a structured error — never silently continue.
- **Convert `-O`-stripped asserts used as runtime validation into real raises:**
  `astrid/core/executor/install.py:239,245` (before git clone), `astrid/core/session/cli.py:711`,
  `astrid/core/runpod/sweeper.py:149`.
- **Default audit-ledger verification.** `astrid/audit/cli.py:18-23` vs `astrid/audit/report.py:103`:
  the hash chain is only verified with `--verify`; the default report path renders unverified. Verify
  by default (or make non-verification a loud, explicit opt-out).
- **Fix the misnamed/partial `json_schema` check.** `astrid/verify/checks.py:99-122` validates only
  `required` keys and ignores `type`/`properties`/`pattern`/`enum`, giving false-positive "ok". Either
  implement real schema validation or rename it to reflect what it actually checks and document the limit.

## Scope (OUT / anti-scope)
- **No pack source changes.** Where a pack consumes a changed core interface, update only the minimal
  call site; do not refactor the pack.
- **No taxonomy renames, no god-module splits, no CLI restructuring** — those are m5. Touch `gate.py`
  surgically; do not split it here even though it's large.
- Do not redesign the event schema or cursor model — fix the bugs within the existing design.
- Don't "fix" `threads/` by deleting it (that's m5); here, only make its locking honest or document the constraint.

## Locked decisions
- One error model: failures are surfaced (raised or returned as structured errors), never silently swallowed.
- `assert` is not a runtime-validation mechanism — convert to explicit raises.
- Bug fixes must come with a regression test that fails before / passes after (m2 made the suite trustworthy).

## Open questions (resolve during prep/plan — `+prep` is on)
- Map the full `start → next → gate_command → adapter.dispatch → wait → record_dispatch_complete` path
  and enumerate every place a terminal event can be skipped. Prep should produce this map before planning fixes.
- For each broad `except`: is the right fix narrow-catch, log+raise, or structured-error return? Decide per site.
- Is `threads/` actually reached by concurrent in-process callers today, or only cross-process? Determines the flock fix shape.

## Constraints
- **Production-incident stakes** — a regression here is a silently stuck pipeline. Every change needs a test.
- Behavior-preserving where behavior is already correct; only the silent-failure and stall paths change.
- No new external dependencies.

## Done criteria
- Regression tests prove: an attested step emits a terminal event; a failed `produces` check surfaces to
  the caller rather than stalling; a genuine `repeat.until` gate error halts the run; the for_each path
  advances/aborts as intended.
- A grep shows no remaining failure-hiding `except ...: pass` / silent fallback at the enumerated sites.
- No runtime-validation `assert` remains at the enumerated sites.
- Audit report verifies the hash chain by default.
- `json_schema` check either validates beyond `required` or is renamed + documented.
- `docs/error-model.md` (short) states the project's error-handling convention.

## Touchpoints
- `astrid/core/.../gate.py:929,1153-1155,1543,1877-1879,1979`, `:656`, `:282-345` (cursor replay context)
- `astrid/pipeline.py:100-102,169-175`
- `astrid/orchestrate/cli.py:223-224,490-491`
- `astrid/threads/provenance.py:141-142`, `astrid/threads/.../index.py:62-69`
- `astrid/skills/__init__.py:241-242`, `astrid/audit/context.py:214-217`, `astrid/structure.py:114-146`
- `astrid/core/executor/install.py:239,245`, `astrid/core/session/cli.py:711`, `astrid/core/runpod/sweeper.py:149`
- `astrid/audit/cli.py:18-23`, `astrid/audit/report.py:103`, `astrid/verify/checks.py:99-122`
- New: `docs/error-model.md`
