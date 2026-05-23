# Milestone 5: Integration, Docs, And Agent Proof

## Outcome

Prove the pack-first system works end to end for both humans and agents:
creation, discovery, old-id compatibility, migration, fork/override, update
reports, skills install, and docs.

## Scope

In scope:

- Run cross-cutting validation over:
  - pack validation
  - capability list/search/inspect JSON
  - old id alias behavior
  - cross-pack child refs
  - default discovery cleanliness
  - hidden/deprecated/example visibility
  - fork/override inspectability
  - update reports
  - skills install/list/doctor
- Add or update docs:
  - pack model
  - creating packs
  - creating tools
  - discovery for agents
  - aliases versus forks versus overrides
  - personal packs
  - adapter packs
  - update workflow
- Add one agent-facing proof scenario:
  - a cold agent is asked for a media/art task
  - it uses discovery rather than source grep
  - it selects the right capability kind
  - it can inspect inputs/outputs/safety before run
- Regenerate indexes and AGENTS capability tables as needed.
- Verify compatibility with related epics:
  - builtin-training placement decisions
  - timeline/thread event-sourcing work
  - skills installation work

Out of scope:

- New large pack migrations.
- New remote registry/install system.
- LLM-powered semantic merge.
- Broad unrelated docs rewrite.

## Constraints

- Docs should describe the implemented system, not the aspirational future.
- The agent proof should be cheap and deterministic.
- Do not hide known limitations; document deferred remote registry,
  dependency-isolation, and semantic-merge work explicitly.

## Done Criteria

- Chain-level tests pass or failures are documented with concrete blockers.
- Capability index and generated skill/docs surfaces are current.
- A cold-agent discovery scenario proves the model is usable without source
  reading.
- `AGENTS.md` and pack skills accurately describe the new pack model.
- Remaining deferred work is listed as explicit future work, not ambiguous TODOs.

## Touchpoints

- `AGENTS.md`
- `docs/creating-packs.md`
- `docs/creating-tools.md`
- `docs/skills-install.md`
- `scripts/gen_capability_index.py`
- `astrid/skills/discovery.py`
- `tests/test_doctor_setup.py`
- `tests/test_canonical_cli.py`
- `tests/test_pack_discovery.py`
- `tests/test_packs_cli.py`

## Anti-Scope

- Do not relitigate the core architecture unless integration reveals a concrete
  implementation blocker.
