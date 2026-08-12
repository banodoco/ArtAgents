# Task T2.6 — Locked video-plus-sidecar publication [HARD]

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`.
You have `workspace-write` permissions. Python: `PYENV_VERSION=3.11.11`.

## Context

Batch 2 of "Pluggable Timeline Renderers". The frozen provenance contract
(`astrid/core/rendering/provenance.py`, `write_provenance_v2`) exists.
Publication must: lock each output, rename the video first, atomically write
its hashed provenance sidecar LAST (the sidecar is the commit marker),
handle previous-output cleanup conservatively, and recover crash orphans
without ever treating an incomplete video+sidecar pair as committed.

## Change

Add `astrid/core/rendering/publication.py`:

- `publish_render_result(video_path, provenance_payload, *, out_path,
  sidecar_path, previous_outputs)`:
  - Acquire a per-output file lock (mirror the `filelock` pattern from the
    asset cache / `_lock_for`).
  - Validate the video exists and is non-empty BEFORE publishing.
  - Rename (os.replace) the video into place FIRST.
  - Write the hashed provenance sidecar ATOMICALLY LAST
    (`write_json_atomic`; the sidecar contains the video's sha256 and the
    output path).
  - Crash-orphan recovery: if a video exists but its sidecar is missing or
    its recorded sha256 doesn't match the video, treat the pair as
    incomplete — never report success; either repair (re-render) or delete
    conservatively per the caller's policy.
  - Previous-output cleanup: `previous_outputs` (from the existing
    `_delete_previous_render_outputs_for_timeline` behavior in run.py) —
    delete only outputs whose sidecar `timeline` matches and whose pair is
    complete (never delete a live render's output); make the delete atomic
    per pair (sidecar first, then video — the video without sidecar is
    orphan-recoverable).
- Replace in `astrid/packs/rendering/executors/render/run.py` the current
  non-atomic `_delete_previous_render_outputs_for_timeline` and the video
  write + sidecar write with the new publication path, preserving observable
  behavior (same filenames, same sidecar contents, same cleanup semantics).
- Add `tests/core/rendering/test_publication.py`:
  - happy path: video + sidecar published, sidecar sha256 matches;
  - lock contention: two concurrent publishers serialize (no interleave);
  - crash-orphan: video without sidecar → not committed, conservative
    recovery; sidecar with wrong hash → not committed;
  - previous-output cleanup: matching timeline pair deleted; non-matching
    kept; incomplete pair never deleted; live render output never deleted;
  - video missing/empty → structured failure before any rename;
  - atomicity: sidecar write failure leaves video visible but pair
    uncommitted (recoverable).

## Acceptance

- `pytest -q tests/core/rendering/test_publication.py` passes.
- `pytest -q tests/core/rendering` has no NEW failures.
- Existing render cleanup tests (e.g. `test_render_remotion_registry.py`
  cleanup cases) still pass.

Run ONLY those commands. Do NOT run the full suite, formatters, or linters.
Do NOT touch `contracts.py`, `schemas/`, `docs/contracts/`, `transport.py`,
`assets.py`, `asset_cache.py`, or `provenance.py` (reuse
`write_provenance_v2`). Preserve all existing work. Report: files changed,
test results, the publication protocol.
