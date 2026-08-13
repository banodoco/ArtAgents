# Task T7.1 — Complete renderer CLI discovery and smoke

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`.
You have `workspace-write` permissions. Python: `PYENV_VERSION=3.11.11`.

## Context

Batch 7 (final) of "Pluggable Timeline Renderers". Batches 1-6 froze
contracts, backends, service, facade, SDK, scaffold, and parity. Your job:
the renderer CLI verbs `list`, `inspect`, `validate`, `smoke` alongside the
existing `create`.

## Change

1. `astrid/core/rendering/cli.py::main` + `gateway/dispatch.py::_dispatch_renderers`
   + `_TOP_LEVEL_HANDLERS` + `gateway/help.py`:
   - `list` — print all discovered renderer/planner/finalizer qualified ids
     (from the default registries) as plain lines.
   - `inspect <id>` — print the candidate's manifest fields (command,
     operations, required_binaries, capabilities, source pack, eligibility)
     as readable text.
   - `validate <path>` — run `validate_pack` on a pack directory and report
     errors/warnings; exit non-zero on errors.
   - `smoke <id>` — run a direct-service render with a generated minimal
     timeline/assets (the scaffold's own deterministic smoke pattern),
     print the output path + provenance sidecar path, exit non-zero on
     failure. Uses the PUBLIC service (no ledger); never mutates project
     state.
   - Keep each verb's output stable, plain-text, and free of a universal
     JSON envelope (T7.2 locks the JSON contract).
2. Add `tests/core/rendering/test_cli.py`:
   - `list` shows the four built-ins;
   - `inspect rendering.ffmpeg` shows command/operations/capabilities;
   - `validate` on the scaffold output passes and on a broken pack fails
     with non-zero exit;
   - `smoke rendering.ffmpeg` (or a scaffolded pack in an extra root)
     produces a real output + sidecar through the service;
   - unknown id / bad args → non-zero exit with a clear message.

## Acceptance

- `pytest -q tests/core/rendering/test_cli.py` passes.
- `pytest -q tests/core/rendering` has no NEW failures.

Run ONLY those commands. Do NOT modify `service.py`, `provenance.py`, the
backends, `contracts.py`, schemas, the facade, or `astrid/sdk/rendering.py`.
Preserve all existing work. Report: files changed, test results, the CLI
verb shapes.
