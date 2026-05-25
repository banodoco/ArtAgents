# m2 — Test Integrity (make green mean green)

## Outcome
Every test in the default `pytest` run actually asserts something real, and a green CI is
trustworthy enough to refactor on top of. This milestone is the safety net for m3/m4/m5 —
its deliverable is *trust*, not coverage numbers.

## Scope (IN)
- **Fix the double-executing test harness.** `tests/agentic/.../test_runner.py:191-206`:
  `run_fixture()` calls `gate_command()` (which dispatches via `LocalAdapter.dispatch()` →
  `subprocess.Popen`, `astrid/.../adapter/local.py:58-66`) and THEN unconditionally calls
  `subprocess.run(cmd_argv, ...)` on the same command — every code step runs twice. The
  production path (`astrid/pipeline.py:169-172`) correctly branches on `decision.adapter`. Update
  the harness to mirror production: when an adapter dispatched the step, do not re-run it.
  **Deliverable check:** a named test `test_runner_dispatches_exactly_once` that mocks
  `subprocess.run`/`Popen` and asserts exactly one execution per step. (Not "if feasible" — this is
  the load-bearing m2 deliverable.)
  This bug also masks real runtime behavior, so fixing it may surface failures — that is expected
  and in-scope to investigate (but runtime *fixes* belong to m3; here, characterize + xfail with a
  tracking note if a genuine product bug surfaces, and hand it to m3).
- **Delete the regression denylist.** `tests/test_sprint1_regression.py:313-366`
  `TestFullExistingSuitePasses` runs pytest as a subprocess and filters real FAILED lines through a
  `KNOWN_FAILURES` set (e.g. `test_root_help_explains_canonical_gateway`). Remove the denylist and
  fix (or correctly xfail-with-reason) whatever it was masking. Reconsider whether a
  meta-test-that-runs-pytest is even the right mechanism; if it only exists to host the denylist,
  retire it.
- **Remove zombie skips.** `tests/test_task_inline_checks.py:157-161`
  `test_attested_sentinel_only_check_rejected_at_load` is `@pytest.mark.skip` with a reason admitting
  the validation it tests "has never existed in source." Either delete the test or (if the validation
  *should* exist) file it as a product gap for the relevant milestone — do not leave a forever-skipped
  test posing as coverage.
- **Kill sleep-based races — across the whole `tests/adapter/` directory, not just one file.**
  `tests/adapter/test_local.py:106,121,138,158,172` use `time.sleep(0.3)`; the sibling
  `tests/adapter/test_remote_artifact_real.py:277` uses `time.sleep(0.05)` ("give it a tiny moment
  to exit") — same race-by-sleep anti-pattern. Replace ALL with deterministic waiting, mirroring the
  **production** adapter at `astrid/.../adapter/local.py:58-66` which already uses `Popen` + real
  completion signals. No `time.sleep` as a synchronization primitive anywhere in `tests/adapter/`.
- **Decide the policy on opt-in-only tests** and apply it consistently:
  `tests/test_renderer_parity.py:56` (skips unless `ASTRID_RENDERER_PARITY=1`),
  `tests/packs/builtin/generate_image/.../test_e2e.py:466` (skipif on optional deps),
  `tests/test_hype_cut_invariants.py:289` (skips unless `HYPE_*` env set). Either wire them into a
  documented CI lane (e.g. a marked `integration` job) or move them out of the default-collected suite
  so they stop posing as coverage. **Touch only the test scaffolding/markers — not pack source.**

## Scope (OUT / anti-scope)
- **No product/runtime fixes** to `astrid/` source — if the un-lied tests reveal a real bug, characterize
  it and hand it to m3 with a tracking xfail; do not fix it here. (Exception: the test_runner double-exec
  itself is test-harness code and is in-scope.)
- **No pack refactors.** Where a test lives under `tests/packs/**`, only adjust its markers/skips, never
  the pack it exercises.
- Do not chase coverage % or add new feature tests — this is about making existing tests honest.
- Do not unify the two fixture families wholesale (noted below as an open question, decide deliberately).

## Locked decisions
- `time.sleep` is banned as a test synchronization primitive in the touched files.
- A skipped/xfail test must carry a reason that points at a real, trackable cause — no aspirational skips.
- Real bugs surfaced here are handed to m3, not fixed in m2.

## Open questions (resolve during plan)
- Duplicate session-seeding fixtures: `tests/conftest.py`
  (`attached_session`/`_seed_identity_and_session`/`mint_session`/`seed_project`) vs
  `tests/_lifecycle_fixtures.py` (`bind_writer_session`/`setup_run`/`make_pack`). Decide whether to
  unify now or just document the split — unifying is only in-scope if it's low-risk; otherwise note it
  and leave for a later cleanup.
- For each opt-in test: is the right answer "CI integration lane" or "remove from default suite"? Decide per test.

## Constraints
- The default `pytest -q` run after this milestone must have **zero unconditional skips that hide
  nonexistent or broken behavior**, and no test that asserts nothing.
- Don't make the suite slower in the default lane (no newly-unskipped heavyweight integration tests
  running by default — gate them behind a marker/lane instead).

## Done criteria (mechanically checkable)
- Named test `test_runner_dispatches_exactly_once` exists and passes (mocks execution, asserts one call/step).
- `grep -rn "KNOWN_FAILURES" tests/` returns empty; `test_sprint1_regression.py` passes honestly or is retired with rationale.
- `grep -rn "pytest.mark.skip" tests/` shows no skip whose reason is "the thing under test doesn't exist."
- `grep -rn "time.sleep" tests/adapter/` returns empty (no sleep-as-synchronization).
- Opt-in test policy is recorded in `docs/ci-lanes.md` (marker→lane map) AND `pytest -m "not integration and not opt_in"`
  (or the agreed marker) collects ZERO of the three enumerated opt-in tests.
- The m3 bug-handoff list is recorded in `EPIC.md` (handoff section), not a separate file.
- **CI-green policy:** the default `pytest` lane is configured to pass with zero allowed failures (no denylist
  can return) — recorded in the CI config so the next milestone can't normalize red again.

## Touchpoints
- `tests/agentic/.../test_runner.py:191-206`, `astrid/.../adapter/local.py:58-66`, `astrid/pipeline.py:169-172`
- `tests/test_sprint1_regression.py:313-366`
- `tests/test_task_inline_checks.py:157-161`
- `tests/adapter/test_local.py:106,121,138,158,172`
- `tests/test_renderer_parity.py:56`, `tests/packs/builtin/generate_image/.../test_e2e.py:466`, `tests/test_hype_cut_invariants.py:289`
- `tests/conftest.py`, `tests/_lifecycle_fixtures.py` (open question only)
