# Task T6.2 — Add the public rendering SDK

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`.
You have `workspace-write` permissions. Python: `PYENV_VERSION=3.11.11`.

## Context

Batch 6 of "Pluggable Timeline Renderers". M1 handoff (T6.1) is enforced
first. Your job: the public rendering SDK surface in
`astrid/sdk/rendering.py` — `renderer_main`, `render`, `support` — wrapping
the canonical core DTOs with NO new wire fields or semantics.

## Change

1. `astrid/sdk/rendering.py`:
   - `renderer_main()` — thin entrypoint that reads a v1 render/support
     request, dispatches through the public service/backend, and writes the
     validated result (mirror the raw-command backend's stdin/file protocol
     exactly; reuse the frozen transport request/result JSON shapes).
   - `render(...)` — public convenience that builds a `RenderRequest` from
     friendly args and calls the shared `RenderService` (or the facade),
     returning the published output path.
   - `support(...)` — public convenience that resolves a qualified backend
     and returns its `SupportReport`.
   - Reuse core DTOs (`RenderRequest`, `RenderResult`, `SupportReport`),
     `sdk.results._json_safe`, and the core validation functions. Heavy
     imports (service, transport, backends) MUST be function-local so the
     SDK top-level stays cheap and lazy.
2. Wire equivalence is REQUIRED: SDK serialization must produce the SAME
   fields as the raw fixture/backend path. No SDK-only fields, no
   semantics drift. If a mismatch is found, STOP and report to the M1 gate —
   do not paper over it.
3. Update:
   - `astrid/_SDK_EXPORTS` (top-level `astrid` exports),
   - `astrid/sdk/__init__.py::__all__`,
   - `tests/_sdk_contract.py::EXPECTED_PUBLIC_NAMES` (add the new names),
   - preserving exact lazy public-export ordering and collision checks.
4. Add `tests/test_sdk_rendering.py`:
   - `renderer_main` round-trips a raw fixture request and writes the same
     result JSON as the raw backend;
   - `render`/`support` produce valid outputs through a FakeTransport-backed
     service;
   - lazy imports: importing `astrid.sdk.rendering` does NOT import the
     backends/transport eagerly (assert via import hook or sys.modules);
   - wire-field parity between SDK and raw paths.
5. `tests/test_sdk_public_surface.py` must pass (public names contract).

## Acceptance

- `pytest -q tests/test_sdk_rendering.py tests/test_sdk_public_surface.py` passes.
- `pytest -q tests/core/rendering` has no NEW failures.
- Wire parity: SDK output JSON == raw fixture output JSON for the same
  request (semantically identical fields).

Run ONLY those commands. Do NOT modify `service.py`, `provenance.py`, the
backends, `contracts.py`, schemas, or the facade. Preserve all existing
work. Report: files changed, test results, the SDK API shape.
