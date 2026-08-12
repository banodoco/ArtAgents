# Task T3.2 — Enforce the Remotion outer lock [HARD]

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`.
You have `workspace-write` permissions. Python: `PYENV_VERSION=3.11.11`.

## Context

Batch 3 of "Pluggable Timeline Renderers". T3.1 (before you) extracted the
Remotion backend to `astrid/packs/rendering/backends/remotion/`. The
exploration findings (`.oracle/findings/16-registry-lock.txt`) documented the
registry race: element-registry generation (`scripts/gen_effect_registry.py`)
mutates SHARED generated files (package `*.generated.ts`, shim families,
`_active_theme` symlink) with no lock, and the Remotion subprocess reads them.
Your job: one NON-RECURSIVE cross-process lock spanning registry-state reads,
all registry/shim/theme-pointer writes, active-theme selection, the complete
Remotion render, and the `gen-types` writer path.

## Change

1. `astrid/packs/rendering/backends/remotion/lock.py`:
   - `remotion_render_lock` — a file lock on `remotion/.astrid-registry.lock`
     (mirror the `filelock`/`_lock_for` pattern from the asset cache), held
     from BEFORE registry-state reads through generation AND the full
     Remotion render, released in `finally`.
   - Must be NON-RECURSIVE (a render must not deadlock if it re-enters).
2. Route `_regenerate_element_registries` (or its extracted equivalent) and
   the full render through the lock.
3. Update `scripts/gen_effect_registry.py`, `scripts/gen_remotion_types.py`,
   and `remotion/package.json` so the `gen-types` writer uses the SAME lock
   (the locked writer entrypoint). Developers running gen-types must not
   bypass the lock.
4. Add `tests/packs/rendering/test_remotion_locking.py`:
   - lock acquired during generation+render (spy/assert);
   - two concurrent renders serialize (second waits for first);
   - gen-types acquires the same lock;
   - non-recursive: a render that internally calls the writer does not
     deadlock;
   - release on failure (exception path releases).
5. Keep `tests/packs/rendering/test_render_remotion_registry.py` passing.

## Acceptance

- `pytest -q tests/packs/rendering/test_remotion_locking.py tests/packs/rendering/test_render_remotion_registry.py` passes (or same 2 pre-existing env failures only).
- `pytest -q tests/packs/rendering` has no NEW failures.

Run ONLY those commands. Do NOT run the full suite, formatters, linters. Do
NOT modify `contracts.py`, `schemas/`, `docs/contracts/`, `transport.py`,
`assets.py`, `publication.py`, or Batch-1 frozen files. Preserve all existing
work. Report: files changed, test results, the lock design.
