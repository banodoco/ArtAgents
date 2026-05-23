# Milestone 1: Capability Identity And Aliases

## Outcome

Land the shared identity substrate that makes packs useful: a common capability
handle, provenance, list/search/inspect metadata, public-id aliases, and minimal
safety declarations. This milestone should not move capability directories.

## Scope

In scope:

- Implement the M0-approved `Capability` / `CapabilityHandle` shape without
  forcing executors, orchestrators, and elements into one registry class.
- Surface shared fields across executors, orchestrators, and elements:
  - kind
  - canonical id
  - local id
  - pack id
  - name
  - version or opaque compatibility token
  - short description / description / keywords
  - category
  - status
  - visibility
  - provenance
  - aliases and deprecation metadata
  - safety/cost/secrets/network declarations
- Add a structured provenance record:
  - origin/source
  - pack id
  - manifest path
  - content root
  - resolved alias, when applicable
- Surface inputs and outputs where schemas already exist. Do not invent a new
  full type system in this milestone.
- Add public-id alias/deprecation resolution:
  - old id -> canonical id
  - alias metadata in inspect JSON
  - cycle and missing-target validation
  - clear behavior for child refs that point through aliases
- Preserve old registry APIs and current `builtin.*` lookups.
- Preserve executor/orchestrator `kind: built_in|external` as legacy metadata
  unless M0 explicitly deprecates it.
- Add tests for common metadata parsing, alias resolution, alias cycles,
  missing targets, deprecated alias inspect output, provenance, and safety
  metadata parsing.

Out of scope:

- Moving files between packs.
- Pack enable/disable UX.
- Full cross-registry graph planning.
- Runtime enforcement of every safety policy unless a small obvious check falls
  out naturally.
- Agent-assisted update merging.

## Constraints

- Keep old `registry.get("builtin.render")` style callers working.
- Do not break existing element priority/fork behavior.
- Avoid a broad schema rewrite if thin adapters around existing schemas are
  enough.
- Treat unknown worktree changes as user work.

## Done Criteria

- Common capability identity appears in list/search/inspect JSON for
  executors, orchestrators, and elements.
- Alias resolution is tested before any id migration can begin.
- Alias cycles and missing targets fail validation.
- Cross-pack child/dependency validation can resolve aliases according to M0.
- Safety/cost/permission metadata can be declared and inspected.
- Provenance metadata is not re-derived ad hoc in each CLI.

## Touchpoints

- `astrid/contracts/schema.py`
- `astrid/core/_search.py`
- `astrid/core/executor/schema.py`
- `astrid/core/executor/registry.py`
- `astrid/core/orchestrator/schema.py`
- `astrid/core/orchestrator/registry.py`
- `astrid/core/element/schema.py`
- `astrid/core/element/registry.py`
- `tests/test_canonical_aliases.py`
- `tests/test_default_registry_scopes.py`
- `tests/test_pack_discovery.py`

## Anti-Scope

- Do not migrate `builtin` ids.
- Do not introduce a remote registry.
- Do not add a speculative capability-graph engine.
