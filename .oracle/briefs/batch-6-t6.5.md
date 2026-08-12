# Task T6.5 — Add the exact four-file scaffold

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`.
You have `workspace-write` permissions. Python: `PYENV_VERSION=3.11.11`.
T6.2 (public SDK) may be in flight; the scaffold should reference
`astrid.sdk.rendering` patterns if present, else the raw-command fixture
patterns from Batch 2.

## Context

Batch 6 of "Pluggable Timeline Renderers". Your job: the exact four-file
renderer scaffold — `astrid/core/rendering/scaffold.py::create_renderer_scaffold`
plus the initial `create` route in the rendering CLI
(`astrid/core/rendering/cli.py::main` and
`gateway/dispatch.py::_dispatch_renderers`).

## Change

1. `astrid/core/rendering/scaffold.py::create_renderer_scaffold(name, dest)`:
   - Writes EXACTLY four files: `pack.yaml`, `renderer.yaml`, `render.py`,
     `test_renderer.py`. No fifth file, no generated placeholders ("TODO",
     "FIXME", "XXX", "lorem", "example.com").
   - Generated glue is within 50 nonblank/non-comment lines per file.
   - `render.py` is a thin, working raw-command renderer (reuse the
     Batch-2 raw fixture patterns; reference the shared `RenderContext`
     helpers if available) that statically validates and produces a valid
     `RenderResult`.
   - `test_renderer.py` is a runnable pytest file with one deterministic
     smoke test (generates a tiny fake output or runs the renderer with
     mocked ffmpeg/remotion — no real GPU needed).
   - `pack.yaml`/`renderer.yaml` declare the qualified id (derived from
     the name: `rendering.<name>` or the user-supplied id), the command
     `[python3, render.py]`, `operations: [support, render]`, and
     `required_permissions: [project_files, subprocess]`.
   - Collision: refuse to overwrite an existing directory/file unless
     `force=True`.
   - Ownership: files are created with the caller's uid/gid (no sudo).
   - Command containment: the manifest command is exactly the scaffold
     file path (no absolute host paths, no shell).
2. Route `astrid renderers create <name>` through
   `astrid/core/rendering/cli.py::main` and
   `gateway/dispatch.py::_dispatch_renderers` (add the `create` verb to the
   renderers dispatch; `main` delegates).
3. `tests/core/rendering/test_scaffold.py`:
   - exactly four files, no placeholders, line budgets respected;
   - collision refused; force overwrites;
   - static validation of the generated pack/renderer.yaml passes
     (`validate_pack` / manifest validation);
   - the generated test file passes when run on the scaffold output;
   - the `create` CLI route writes to the requested directory.

## Acceptance

- `pytest -q tests/core/rendering/test_scaffold.py` passes.
- `pytest -q tests/core/rendering` has no NEW failures.

Run ONLY those commands. Do NOT modify `service.py`, `provenance.py`, the
backends, `contracts.py`, schemas, the facade, or `astrid/sdk/rendering.py`.
Preserve all existing work. Report: files changed, test results, the
scaffold layout.
