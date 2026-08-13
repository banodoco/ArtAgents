# Task T7.4 — Implement pinned replay and drift acknowledgement [HARD]

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`.
You have `workspace-write` permissions. Python: `PYENV_VERSION=3.11.11`.
T7.3 (replay bundle) runs first and defines `ReplayBundle`/
`write_replay_bundle`.

## Context

Batch 7 (final) of "Pluggable Timeline Renderers". Your job: the `replay`
CLI route that replays a captured bundle — pinning the qualified renderer,
request, and manifest digests — refusing SILENT backend substitution, and
requiring explicit drift acknowledgement before replay proceeds.

## Change

1. `astrid/core/rendering/cli.py` + `gateway/dispatch.py`: add the `replay`
   verb:
   - `replay <bundle-dir>` — re-runs the pinned backend command from the
     bundle's localized inputs, with the pinned request digest;
   - PINNED: the bundle records the qualified renderer id + manifest
     digest + request digest; replay resolves the SAME id and refuses to
     proceed if the current manifest digest differs (silent backend
     substitution is refused);
   - DRIFT: if the manifest/request digest drifted, replay requires an
     explicit `--acknowledge-drift` flag; without it, exit non-zero with a
     clear message;
   - PROOF: after an acknowledged fixture correction (e.g. the bundle's
     input was fixed), replay succeeds and produces the expected output.
2. Reuse the frozen protocol: replay runs the same transport command with
   the same request/result JSON shapes; never bypasses the service contract.
3. Add `tests/core/rendering/test_replay.py`:
   - replay of a fresh bundle succeeds and reproduces the output;
   - manifest-digest drift is refused without `--acknowledge-drift`;
   - acknowledged drift proceeds;
   - request-digest mismatch is refused (bundle tampering);
   - the replay route reports the pinned ids/digests in its output.

## Acceptance

- `pytest -q tests/core/rendering/test_replay.py` passes.
- `pytest -q tests/core/rendering` has no NEW failures.

Run ONLY those commands. Do NOT modify `contracts.py`, schemas, the
backends, `service.py`, or `astrid/sdk/rendering.py`. Preserve all existing
work. Report: files changed, test results, the replay contract.
