# Task — REBUILD the renderer CLI verbs (recovery)

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`.
You have `workspace-write` permissions. Python: `PYENV_VERSION=3.11.11`.

## Situation (critical)

An earlier agent implemented the `astrid renderers` CLI verbs
(`create`, `list`, `inspect`, `validate`, `smoke`, `support`) in
`astrid/core/rendering/cli.py`, plus `--json` output modes, and their tests
passed (16 in `tests/core/rendering/test_cli.py` + the T7.2 contract tests in
`tests/core/rendering/test_cli_contract.py`). That uncommitted implementation
was accidentally reverted to the committed 89-line version (which has ONLY
`create`). The TEST FILES SURVIVED and define the exact contract. Your job:
rebuild `astrid/core/rendering/cli.py` so ALL those tests pass.

## Spec (from the surviving tests)

Read `tests/core/rendering/test_cli.py` and
`tests/core/rendering/test_cli_contract.py` FIRST — they are the contract.

Verbs (all in `astrid/core/rendering/cli.py::main` / `build_parser`):
- `create <name> [dest] [--id X] [--force]` — EXISTS in the committed file;
  keep it exactly.
- `list [--pack-root PATH ...] [--json]` — prints every discovered
  renderer/planner/finalizer qualified id, one per line (plain mode). With
  `--json`, one JSON object on stdout with a stable verb-specific shape
  (exact keys per the contract test).
- `inspect <id> [--pack-root PATH ...] [--json]` — prints manifest fields as
  `key: value` lines: `id`, `kind`, `command` (e.g. `python3 run.py`),
  `operations` (e.g. `render, support`), `required_binaries` (comma-joined),
  `capabilities:` block, `clip_types`, `supports_full_timeline`,
  `source_pack`, `source_kind`, `eligibility`, `trust_method`. Unknown id →
  exit 1, stderr `unknown renderer/planner/finalizer id '<id>'` plus a hint
  listing available renderers (`renderers list`). With `--json`, one JSON
  object with the verb-specific keys.
- `validate <path> [--json]` — `validate_pack` on the directory; success →
  exit 0, stdout `valid: <resolved-path>`; errors → exit 1, stdout
  `invalid: <resolved-path>`, stderr lines starting `error:` mentioning the
  failing file; missing dir → exit 1, stderr
  `not a directory or does not exist`.
- `smoke <id> [--pack-root PATH ...] [--out PATH] [--json]` — resolve ONLY a
  renderer (a planner/finalizer id → exit 1 with
  `unknown renderer id '<id>'` plus `is a planner id` hint), render a
  minimal deterministic timeline (`{"tracks": [], "clips": []}` +
  `{"assets": {}}`) through the PUBLIC `RenderService` (smoke-tolerant
  validator: containment/size/sha256, no ffprobe), print `smoke: <id>` /
  `output: <path>` / `provenance: <path>` (plain mode); with `--json` one
  object. Unknown id → exit 1, stderr `unknown renderer id '<id>'`.
- `support <id> [--pack-root PATH ...] [--json]` — resolve the id's support
  report through the public SDK (`astrid.sdk.rendering.support`), print the
  result; unsupported → the frozen RendererError shape (kind unsupported +
  recovery). With `--json`, verb-specific keys.
- `--json` mode: EVERY verb emits exactly ONE JSON object on stdout, NO
  universal envelope (no `ok`/`status`/`data`/`result` wrapper); plain mode
  stays text.
- Exit codes: 0 success, 1 domain failure, 2 argparse errors (argparse
  raises SystemExit(2) for missing/bad args).
- Session independence: identical output for same inputs across cwd.
- Trust denial: an `ASTRID_PACKS_PATH`-discovered (env) pack is refused in
  contexts that require trusted eligibility, with a clear message.
- `gateway/dispatch.py::_dispatch_renderers` + `_TOP_LEVEL_HANDLERS["renderers"]`
  must route to `cli.main` (check the current dispatch — it may already
  exist; keep `replay` routing intact — `_dispatch_replay` exists and routes
  to `renderers_cli.main(["replay", ...])`; the `replay` subparser + `_cmd_replay`
  handler are being added by a concurrent task, so DO NOT add them, but DO
  NOT break the existing `_dispatch_replay` either — if the `replay` verb is
  absent from the parser, that is expected for now; a concurrent task adds
  it).

## Reuse

- Registries: `astrid.core.rendering.registry.load_default_registries` with
  `extra_pack_roots` from `--pack-root`.
- Validation: `astrid.core.pack.validate.validate_pack`.
- Service: `astrid.core.rendering.service.RenderService` (public), with a
  smoke validator that checks containment/size/sha256 but NOT ffprobe.
- SDK support: `astrid.sdk.rendering.support`.
- Errors: `astrid.core.rendering.errors` structured error helpers; JSON
  output must use the frozen error shapes (see the contract test).

## Acceptance

- `pytest -q tests/core/rendering/test_cli.py` → 16 passed.
- `pytest -q tests/core/rendering/test_cli_contract.py` → all passed.
- `pytest -q tests/core/rendering` → no NEW failures (pre-existing
  model-trends env failure in `test_render_remotion_registry.py` is
  expected; the `replay` verb may be absent — its tests are run by a
  concurrent task).

Run ONLY those commands. Do NOT modify `service.py`, `provenance.py`, the
backends, `contracts.py`, schemas, the facade, `astrid/sdk/rendering.py`, or
`astrid/core/gateway/dispatch.py` (beyond verifying `_dispatch_renderers`
routes to cli.main). Preserve all existing work. Report: the rebuilt CLI
shape, test results.
