# Task T1.4 — Build trusted rendering registries [HARD]

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`.
You have `workspace-write` permissions. Python: `PYENV_VERSION=3.11.11`.

## Context

Batch 1 of "Pluggable Timeline Renderers". T1.2 (contracts) and T1.3 (pack
extension) ran before you; read their results first:
- `astrid/core/rendering/contracts.py` (DTOs; T1.2)
- `astrid/core/pack/registry.py::pack_rendering_manifest_paths` (T1.3)
- `.oracle/plan.md` resolved decisions 2–5 (registry semantics, trust
  eligibility, aliases/overrides)
- Exploration findings: `astrid/core/pack/discovery.py`,
  `astrid/core/pack/store.py` (installed active revisions),
  `astrid/core/registry/base.py` (CapabilityRegistry),
  `astrid/core/pack/alias_resolver.py`, `astrid/core/pack/override.py`
  (OverrideStore), `astrid/core/execution/executor/registry.py` +
  `astrid/core/execution/orchestrator/registry.py` (`load_default_registry` —
  currently OMITS OverrideStore; retrofit it).

Your job: renderer/planner/finalizer registries over existing primitives with
derived execution eligibility. NO new pack loader, NO new plugin system.

## Change

1. `astrid/core/rendering/registry.py`:
   - `RendererRegistry`, `PlannerRegistry`, `FinalizerRegistry` built over
     `CapabilityRegistry`; register candidates discovered via
     `discover_pack_metadata()` + `pack_rendering_manifest_paths()` +
     static manifest parsing (NO importing/executing backend code for
     discovery — parse YAML only).
   - `load_default_registries(project_root=None)` returning all three,
     wired with `AliasResolver` + `OverrideStore(project_root)`.
   - Resolution order: alias → canonical id → override target → registry
     winner. Winner determined by `DiscoveredPack.priority_index` (NOT the
     executor registry's `metadata["priority"]`).
   - Execution eligibility derived from discovery context (plan decision 2):
     source=executable; local=executable; extra=executable only when
     explicitly supplied via extra_pack_roots (record trust method); env=
     discoverable+inspectable but NON-executable; installed=executable only
     when active revision has a valid installation trust audit + accepted
     permissions. Missing/corrupt install records fail closed; inactive
     revisions undiscoverable.
   - Only execution-eligible candidates enter the executable registry, so an
     ineligible higher-precedence candidate cannot shadow trusted code.
   - Alias cycles and overrides resolving back to the facade fail before
     invocation (raise a structured registry error).
   - Programmatic compatibility aliases: bare `remotion` → `rendering.remotion`,
     bare `ffmpeg` → `rendering.ffmpeg`. `hybrid` is NEVER a renderer alias
     (it is a planner translation; leave it out of the renderer registry).
   - Resolution evidence: expose per-id `resolve_evidence` with source kind,
     pack id, manifest digest, alias chain, override, priority, eligibility
     reason — so inspection can answer "why this backend".
2. `astrid/core/execution/executor/registry.py::load_default_registry` and
   `astrid/core/execution/orchestrator/registry.py::load_default_registry`:
   wire `OverrideStore(project_root)` into the constructed registries
   (currently CLI-only post-attachment; the plan fixes this). Preserve
   existing executor/orchestrator behavior otherwise.
3. `tests/core/rendering/test_registry.py`:
   - static no-import discovery (discovery never imports backend code);
   - precedence by priority_index;
   - conflict reporting;
   - alias chain resolution and cycle rejection;
   - override resolution and invalid-target rejection;
   - eligibility: source/local executable; env non-executable; installed
     active-with-audit executable; corrupt/missing install record excluded;
     inactive revision excluded; explicit extra root executable;
   - ineligible higher-precedence candidate does not shadow trusted lower;
   - programmatic `remotion`/`ffmpeg` aliases resolve to qualified ids;
     `hybrid` is not registered as a renderer;
   - resolve_evidence shape.
   Use `tests/fixtures/renderer_packs/discovery/` for fixture packs (add
   fixture packs there as needed: a trusted source pack, an env-layer pack,
   an installed pack with a valid trust record, one with a corrupt record,
   one inactive).
4. `tests/packs/test_pack_discovery_metadata.py` and `tests/test_override.py`:
   update/extend for the retrofit without breaking existing assertions.

Do NOT implement transport (T2), the service (T4), or backends (T3).

## Acceptance

- `pytest -q tests/core/rendering/test_registry.py tests/test_override.py tests/packs/test_pack_discovery_metadata.py` passes.
- `pytest -q tests/core/rendering` has no failures.
- `pytest -q tests/core/execution tests/test_default_registry_scopes.py` has no NEW failures (retrofit is behavior-preserving).

Run ONLY those commands. Do not run the full suite, formatters, linters.
Do not modify `docs/contracts/` (T1.2 owns it) or backend modules. Preserve
all existing work; never reset. Report: files changed, test results, the
eligibility matrix you implemented.
