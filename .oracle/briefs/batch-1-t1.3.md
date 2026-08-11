# Task T1.3 — Add the exact rendering pack extension [HARD]

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`.
You have `workspace-write` permissions. Python: `PYENV_VERSION=3.11.11`.

## Context

Batch 1 of "Pluggable Timeline Renderers". T1.2 (contracts/schemas) is being
built in parallel by another agent under `astrid/core/rendering/` — do not
touch that directory. Read first:
- `.oracle/plan.md` (resolved decision 1: strict `extensions.rendering`)
- `astrid/core/pack/schemas/v1/pack.json`
- `astrid/core/pack/_common.py` (normalizer; `PACK_ALIAS_KINDS`,
  `PackAliasKind`, `_optional_pack_extensions`)
- `astrid/core/pack/alias_resolver.py` (`extract_pack_aliases`)
- `astrid/core/registry/base.py` (`CapabilityRegistry`) and
  `astrid/core/pack/registry.py` (around `pack_rendering_manifest_paths` /
  line 259 area)

Your job: make `pack.yaml` able to declare renderer/planner/finalizer
manifests under `extensions.rendering` WITHOUT a new component walker or a
new capability kind. The exploration findings established: schema and
normalizer must change in lockstep; `additionalProperties: false` currently
rejects unknown top-level keys; alias kinds are hardcoded to
executor/orchestrator/element.

## Change

1. `astrid/core/pack/schemas/v1/pack.json`: add an optional top-level
   `extensions` object allowing `extensions.rendering` with arrays
   `renderers`, `planners`, `finalizers` of pack-relative manifest paths
   (strings). Keep everything else strict.
2. `astrid/core/pack/_common.py`: extend the normalizer to carry
   `extensions.rendering` through (mirror how existing optional extensions
   like `generation`/`timeline` are normalized, if any; otherwise add
   `_optional_pack_extensions` handling). Extend `PACK_ALIAS_KINDS` /
   `PackAliasKind` with `renderer`, `planner`, `finalizer` (used by alias
   extraction).
3. `astrid/core/pack/alias_resolver.py::extract_pack_aliases`: handle the new
   alias kinds.
4. `astrid/core/pack/registry.py`: add `pack_rendering_manifest_paths(pack)`
   returning `(renderers, planners, finalizers)` manifest paths from the
   normalized extension, with containment checks (paths must stay inside the
   pack root — reject `..`/absolute escapes).
5. Add `tests/packs/test_pack_rendering_extensions.py`:
   - a `pack.yaml` with `extensions.rendering` round-trips through schema
     validation and the normalizer with identical field values;
   - unknown keys inside `extensions.rendering` are rejected;
   - a manifest path escaping the pack root is rejected;
   - alias extraction recognizes renderer/planner/finalizer aliases.
6. Update `tests/packs/test_pack_yaml_schema.py` if it asserts the strict
   allowlist, and `tests/test_canonical_aliases.py` for the new kinds, so the
   existing suites stay green.

Do NOT implement registry lookup/eligibility (T1.4), transport (T2), or any
backend. Only schema, normalizer, alias kinds, manifest-path helper, and
tests.

## Acceptance

- `pytest -q tests/packs/test_pack_yaml_schema.py tests/packs/test_pack_rendering_extensions.py tests/test_canonical_aliases.py` passes.
- `pytest -q tests/packs` has no NEW failures.

Run ONLY those commands. Do not run the full suite, formatters, or linters.
Do not modify files under `astrid/core/rendering/`,
`docs/contracts/`, or `tests/core/rendering/` (T1.2 owns those). Preserve all
existing work; never reset. Report: files changed, test results, any
normalizer decisions.
