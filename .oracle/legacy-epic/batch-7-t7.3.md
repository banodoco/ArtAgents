# Task T7.3 — Capture replay bundles on backend failure [HARD]

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`.
You have `workspace-write` permissions. Python: `PYENV_VERSION=3.11.11`.

## Context

Batch 7 (final) of "Pluggable Timeline Renderers". Your job:
`astrid/core/rendering/replay.py::{ReplayBundle, write_replay_bundle}` plus
service hooks so a failed backend render captures everything needed to
reproduce the failure later.

## Change

1. `astrid/core/rendering/replay.py`:
   - `ReplayBundle` — a dataclass/record holding: qualified renderer id,
     request digest, manifest digest, the exact command argv, localized
     hashed inputs (timeline/assets/theme files copied into the bundle with
     sha256 names), logs + partial results, and metadata (backend version,
     error kind, error message, recovery command).
   - `write_replay_bundle(bundle, dest)` — writes a directory with a
     `bundle.json` + the hashed input files; redacts credentials and URLs
     from logs and metadata (reuse the transport's redaction helpers).
2. Service hooks in `astrid/core/rendering/service.py` (additive; do not
   change the frozen selection order or DTOs):
   - on backend render/finalize/plan FAILURE (RendererException), capture a
     replay bundle when a host `replay_root` is configured;
   - project-run vs explicit-root ownership: when the render is attached to
     a project run (ASTRID_TASK_* env), the bundle lands under the run's
     logs dir; otherwise under the explicit `replay_root` (or a default
     sibling of the output).
   - the bundle records the EXACT command + localized hashed inputs + logs
     + partial result (if the backend wrote one before failing).
3. Add `tests/core/rendering/test_replay_bundle.py`:
   - failure captures a bundle with the qualified id, request digest,
     manifest digest, exact argv, input hashes, logs, error kind/message,
     recovery command;
   - credentials/URLs redacted from logs and metadata;
   - project-run ownership vs explicit-root ownership;
   - localized inputs are copied + hashed (no absolute host paths leak in
     the bundle);
   - no bundle on success (unless explicitly requested).

## Acceptance

- `pytest -q tests/core/rendering/test_replay_bundle.py` passes.
- `pytest -q tests/core/rendering` has no NEW failures.

Run ONLY those commands. Do NOT modify `contracts.py`, schemas, the
backends, or `astrid/sdk/rendering.py`. Service edits are additive hooks
only. Preserve all existing work. Report: files changed, test results, the
bundle schema.
