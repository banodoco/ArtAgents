# Task T2.1 — Implement command transport and process lifecycle [HARD]

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`.
You have `workspace-write` permissions. Python: `PYENV_VERSION=3.11.11`.

## Context

Batch 2 of "Pluggable Timeline Renderers". Batch 1 froze the contracts:
`astrid/core/rendering/contracts.py` (RenderRequest, RenderResult, RenderPlan,
SupportReport, RendererError, etc.), `schemas/v1/*.json`,
`docs/contracts/render-backend-v1.md`. The frozen wire protocol is:

```text
<manifest command...> render|support|plan|finalize \
  --request <absolute-request.json> \
  --result <absolute-result.json>
```

Commands run with `shell=False`, pack root as `cwd`, sanitized environment,
absolute request/result paths. The result FILE is authoritative; stdout/stderr
are captured as logs.

## Change

Add `astrid/core/rendering/transport.py` implementing `CommandTransport`:

- `run(verb, command, *, request_path, result_path, cwd, env, timeout)` — or a
  design matching the frozen contract. Four verbs: `render`, `support`,
  `plan`, `finalize`.
- Binary preflight: `shutil.which` on the command's executable (or resolve
  pack-relative script paths); missing binary → structured `RendererError`
  with `kind="binary_missing"`.
- Sanitized environment: build from `os.environ` filtered to a safe subset
  (reuse `astrid/core/subprocess_env.py::build_child_subprocess_env` or
  similar), NO `shell=True`.
- Process sessions: `start_new_session=True` (or process group), so
  interruption kills the whole tree; on timeout/interrupt, terminate the
  process group and reap (waitpid) — no zombies, no orphans.
- Timeout: kill + reap on expiry → `kind="timeout"`.
- Result parsing: after success, read and validate the result file with the
  frozen DTOs; absent file → `kind="invalid_artifact"`; malformed JSON →
  structured failure; incompatible protocol version → `kind="protocol"`.
- stdout/stderr captured as redacted logs in the failure/result details.
- Map subprocess nonzero exit → `kind="internal"` (or the frozen error kinds;
  see `contracts.RendererErrorKind`). Interruption (KeyboardInterrupt or
  SIGINT) → `kind="interrupted"`, cleanup then re-raise/exit appropriately.
- All failures are renderer-qualified (`backend` = qualified id passed in).

Follow the frozen contracts exactly — do NOT invent new error kinds or
response shapes. Add `tests/core/rendering/test_transport.py`:
- successful render (use a tiny fixture script that writes a valid result
  JSON);
- missing binary;
- nonzero exit;
- timeout (script sleeps; assert kill + reap + no orphan process);
- interruption (SIGINT; assert process group terminated and reaped);
- absent result file;
- malformed result JSON;
- incompatible protocol version;
- stdout/stderr captured;
- env sanitization (assert host env vars like secrets NOT passed).

## Acceptance

- `pytest -q tests/core/rendering/test_transport.py` passes.
- `pytest -q tests/core/rendering` has no NEW failures.

Run ONLY those commands. Do NOT run the full suite, formatters, or linters.
Do NOT modify `contracts.py`, `schemas/`, `docs/contracts/`, or other batch
files (an agent may be editing `tests/core/rendering/test_contracts.py` —
avoid it; another works on the asset cache). Preserve all existing work.
Report: files changed, test results, the exact transport design.
