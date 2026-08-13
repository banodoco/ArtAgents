# Task T7.2 — Freeze CLI JSON and error behavior

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`.
You have `workspace-write` permissions. Python: `PYENV_VERSION=3.11.11`.
T7.1 (CLI verbs) runs first.

## Context

Batch 7 (final) of "Pluggable Timeline Renderers". Your job: freeze the
renderer CLI's JSON output and error behavior with contract tests — verb-
specific JSON keys, session independence, conflicts, trust denial,
unsupported support, recovery guidance, and interruption — WITHOUT a
universal envelope or an independent exit-code layer.

## Change

1. Add `tests/core/rendering/test_cli_contract.py`:
   - each verb (`create`, `list`, `inspect`, `validate`, `smoke`, `replay`
     when it exists) has a STABLE, verb-specific JSON shape when `--json`
     is passed (assert the exact keys per verb; no universal envelope);
   - plain mode stays human-readable text;
   - session independence: two invocations in different cwd/workspaces
     produce identical output for the same inputs;
   - conflict: `create` into a colliding dest → structured error;
   - trust denial: an untrusted pack in an extra root is refused with a
     clear message;
   - unsupported support: `support` on a backend that declines → the frozen
     `RendererError` shape (kind unsupported, recovery guidance);
   - interruption: a cancelled/KeyboardInterrupt path raises cleanly
     without a traceback dump;
   - exit codes: non-zero on failure, zero on success, WITHOUT inventing an
     independent exit-code taxonomy beyond 0/non-zero.
2. Keep `tests/test_astrid_error_contract.py` and
   `tests/test_exec_error_contract.py` green (do not weaken them).

## Acceptance

- `pytest -q tests/core/rendering/test_cli_contract.py` passes.
- `pytest -q tests/test_astrid_error_contract.py tests/test_exec_error_contract.py` passes.

Run ONLY those commands. Do NOT modify `service.py`, `provenance.py`, the
backends, `contracts.py`, schemas, the facade, or `astrid/sdk/rendering.py`.
Preserve all existing work. Report: files changed, test results, the frozen
contracts.
