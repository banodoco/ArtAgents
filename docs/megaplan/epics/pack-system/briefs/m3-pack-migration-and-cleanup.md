# Milestone 3: Pack Migration And Cleanup

## Outcome

Move Astrid's real capabilities into the pack model and clean the catalog so
agents see useful tools by default. Migration, hiding, deletion, aliases, and
capability-index regeneration happen as one phased program.

## Scope

In scope:

- Produce and validate a dry-run migration map before moving files.
- Classify every current pack/capability as:
  - default-enabled core
  - optional workflow
  - adapter/substrate
  - personal pack
  - example/test
  - deprecated
  - hidden
  - delete
- Clean before broad migration where safe:
  - duplicate `clip_extract` scaffold packs
  - redundant Comfy wrapper examples
  - historical examples that should not appear in default discovery
  - obvious dead scaffolds
- Move low-level Astrid-owned capabilities first:
  - media primitives
  - understanding
  - render/cut/validate where coordination permits
  - generation helpers
  - review helpers
- Move workflow/adapters second:
  - high-level workflows
  - compute/runpod
  - comfy/vibecomfy
  - upload
  - iteration if ownership is clear
- Preserve old ids through aliases and deprecation metadata.
- Update child executor/orchestrator references, pack dependencies, docs, tests,
  generated indexes, and skill output.
- Coordinate explicitly before touching paths also owned by:
  - builtin-training epic
  - timeline-event-sourcing work
  - thread/iteration work
- Leave Seinfeld/training deletion or genericization to the builtin-training
  epic unless that epic has already landed and the placement is unambiguous.

Out of scope:

- Behavior refactors during file moves.
- Full package registry/install work.
- Agent-assisted update merging.
- Rewriting timeline or training internals.

## Constraints

- Physical moves require aliases to already be tested.
- Every move must preserve list/search/inspect and direct run behavior.
- Do not migrate a capability that should be deleted just to delete it later.
- Treat personal/user material conservatively; hide or move to a personal pack
  only when ownership is clear.

## Done Criteria

- Dry-run map is checked in or emitted in a reproducible form.
- Default discovery no longer shows duplicate scaffold/example clutter.
- Useful low-level capabilities no longer depend on one monolithic `builtin`
  identity, except through compatibility aliases.
- Adapter/substrate capabilities live in clearly named packs.
- Old public ids still resolve or fail with intentional deprecation messages.
- Capability index and skills output are regenerated.
- Tests cover representative old-id aliases, new ids, search filters,
  cross-pack child refs, and clean default discovery.

## Touchpoints

- `astrid/packs/builtin/`
- `astrid/packs/external/`
- `astrid/packs/iteration/`
- `astrid/packs/upload/`
- duplicate scaffold packs under `astrid/packs/`
- `scripts/gen_capability_index.py`
- `AGENTS.md`
- `docs/megaplan/epics/builtin-training/`
- `tests/test_canonical_cli.py`
- `tests/test_default_registry_scopes.py`
- `tests/test_pack_discovery.py`

## Anti-Scope

- Do not silently delete user-owned assets or outputs.
- Do not migrate Seinfeld/training unless ownership has been resolved by the
  builtin-training epic.
