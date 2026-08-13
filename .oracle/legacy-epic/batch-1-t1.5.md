# Task T1.5 — Lock the discovery and eligibility matrix (DeepSeek Flash)

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. You
MAY edit files (file, web, terminal toolsets). Python:
`PYENV_VERSION=3.11.11`.

## Context

Batch 1 of "Pluggable Timeline Renderers". T1.4 (registries) ran before you;
it created `astrid/core/rendering/registry.py` and
`tests/fixtures/renderer_packs/discovery/` fixture packs. Your job is to
extend the discovery/eligibility matrix tests with edge cases — do NOT
re-architect anything. Read `tests/core/rendering/test_registry.py` first to
follow its existing patterns.

## Change

Extend `tests/core/rendering/test_registry.py` (or add
`tests/core/rendering/test_registry_matrix.py` following the same style)
with these cases, all static (no fixture command ever executes):

- static no-import: asserting discovery/listing/inspection never imports
  backend code (e.g. spy on `sys.modules` for the fixture pack modules, or
  assert no backend module name is imported after `load_default_registries`);
- precedence: two packs in different layers declaring the same qualified
  renderer id → higher `priority_index` wins; record the evidence;
- conflict: same-layer same-id collision → deterministic conflict report;
- alias: bare `remotion`/`ffmpeg` resolve to `rendering.remotion` /
  `rendering.ffmpeg`; alias chain of two hops resolves; alias cycle rejected;
- override: `OverrideStore` redirect changes winner; override target that
  does not exist rejected; override resolving back to the facade rejected;
- eligibility edges (use/add fixture packs under
  `tests/fixtures/renderer_packs/discovery/`):
  - source-pack renderer eligible;
  - env-layer renderer discoverable + inspectable but NOT executable
    (invocation raises structured registry error);
  - installed pack with valid trust audit + accepted permissions eligible;
  - installed pack with corrupt/missing install record excluded (fail
    closed);
  - inactive installed revision not discovered;
  - explicit extra root renderer eligible with trust method recorded;
  - ineligible higher-precedence candidate cannot shadow an eligible
    lower-precedence implementation;
- `hybrid` is not registered in the renderer registry under any name;
- permission: a renderer whose required permissions exceed its pack's
  declared permissions is ineligible;
- resolve_evidence: for a resolved id, evidence contains source kind, pack
  id, manifest digest, alias chain, override, priority, eligibility reason.

## Acceptance

- `pytest -q tests/core/rendering/test_registry.py tests/core/rendering/test_registry_matrix.py` passes (or the single file if you extended in place).
- All matrix tests run WITHOUT executing any fixture command (no subprocess
  to fixture backends).

Run ONLY those acceptance commands. Do NOT run the full suite, formatters,
or linters. Do NOT modify `astrid/core/rendering/registry.py` (T1.4 owns it;
if you find a genuine bug, note it in your report instead of fixing).
Do not touch files outside `tests/core/rendering/` and
`tests/fixtures/renderer_packs/discovery/`. Preserve all existing work.
Report: cases added, results, any registry defects found.
