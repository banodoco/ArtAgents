# Task T6.6 — Prove the scaffold golden path

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`.
You have `workspace-write` permissions. Python: `PYENV_VERSION=3.11.11`.
T6.5 (scaffold) runs first and defines `create_renderer_scaffold`; this task
proves the golden path from a fresh directory AND an installed wheel.

## Context

Batch 6 of "Pluggable Timeline Renderers". Your job: end-to-end proof that a
scaffolded renderer works — creation, static validation, generated test,
trusted installation, and a deterministic two-second smoke — both in a fresh
directory and from the installed wheel.

## Change

1. `tests/core/rendering/test_scaffold_install.py`:
   - fresh-directory flow: `create_renderer_scaffold` into a temp dir →
     static validation passes (`validate_pack`, manifest checks) → the
     generated `test_renderer.py` passes → install the pack into a temp
     `ASTRID_PACKS_PATH` extra root → registry discovery finds
     `rendering.<name>` → a deterministic smoke render (mocked or tiny)
     produces a valid output in <2s.
   - installed-wheel flow: after `scripts/smoke_wheel_install.sh` builds and
     installs the wheel, run the same golden path using the INSTALLED
     scaffold module + installed fixture templates, and run the generated
     test inside the wheel venv.
2. Deterministic smoke: the generated renderer must produce a byte-stable
   output for the same input (no timestamps, no random ids) within two
   seconds.
3. Wire the installed-wheel scaffold proof into
   `scripts/smoke_wheel_install.sh` (append a section that scaffolds,
   validates, installs, and smoke-renders inside the wheel venv).

## Acceptance

- `pytest -q tests/core/rendering/test_scaffold_install.py` passes.
- `bash scripts/smoke_wheel_install.sh` passes (now including the
  installed-wheel scaffold golden path).

Run ONLY those commands. Do NOT modify `service.py`, `provenance.py`, the
backends, `contracts.py`, schemas, the facade, `astrid/sdk/rendering.py`, or
`scaffold.py` (T6.5's file). Preserve all existing work. Report: files
changed, test results, the golden-path evidence.
