# Milestone 4: Forks, Overrides, And Agent Updates

## Outcome

Make editable packs practical. Users and agents should be able to fork,
override, inspect local edits, and apply safe updates without silently
overwriting local work or hiding permission/cost changes.

## Scope

In scope:

- Extend the existing element fork/local-pack precedent to:
  - executor capabilities
  - orchestrator capabilities
  - whole packs where feasible
- Keep these concepts distinct:
  - alias: old id redirects to canonical id
  - fork: copied capability or pack that the user owns
  - override: registry preference to use one capability instead of another
  - in-place edit: dirty supported state that can be promoted to a fork
- Define shallow versus deep forks:
  - shallow fork copies one capability and preserves dependencies
  - deep fork copies the dependency closure where requested and safe
- Add inspectable fork/override provenance:
  - forked_from
  - upstream version or compatibility token
  - local edit state
  - override target
- Add a minimal update workflow:
  - detect local edits
  - compare upstream/default changes
  - flag permission/cost/secrets/network escalation
  - propose safe changes
  - apply only explicit/safe updates
  - validate
  - write a report
- Use git status/worktree state as an input to safety decisions.
- Add tests with local fixture packs, not real network providers.

Out of scope:

- Full semantic three-way merge powered by an LLM.
- Network-backed package updates.
- Dependency isolation or virtualenv-per-pack.
- Runtime sandboxing beyond surfacing safety metadata and obvious guardrails.

## Constraints

- Do not overwrite local user edits silently.
- Prefer auditable reports over opaque "agent fixed it" behavior.
- Preserve old element fork behavior.
- Keep update behavior deterministic in tests; do not call real LLMs.

## Done Criteria

- A user can fork a representative executor/orchestrator/element into a local
  or personal pack.
- Overrides are visible in inspect/list/search output.
- In-place edits can be detected and reported.
- Update reports clearly show local changes, upstream changes, alias/compat
  changes, and safety/cost permission changes.
- Tests cover fork, override, dirty local edit, update report, and safety
  escalation detection.

## Touchpoints

- `astrid/core/element/`
- `astrid/core/executor/`
- `astrid/core/orchestrator/`
- `astrid/core/pack.py`
- `astrid/packs/cli.py`
- `astrid/packs/validate.py`
- local/personal pack handling
- tests around pack discovery and element fork behavior

## Anti-Scope

- Do not build a hosted marketplace.
- Do not let agent update commands run hidden network/tool executions in tests.
