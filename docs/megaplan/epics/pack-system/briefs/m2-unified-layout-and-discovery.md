# Milestone 2: Unified Layout And Discovery

## Outcome

Make pack layout and discovery agree. Runtime discovery, validation, scaffolding,
skills discovery, and agent-facing search should all use one pack model.

## Scope

In scope:

- Reconcile:
  - `astrid/core/pack.py` runtime discovery
  - `astrid/packs/validate.py` schema validation
  - `python3 -m astrid packs new` scaffold output
  - documented pack layout in `docs/creating-packs.md`
  - existing flat in-repo pack layout
- Define and support the canonical layout for new packs.
- Keep compatibility with existing flat packs long enough for M3 migration.
- Add layout validation/linting that catches:
  - duplicate capability ids
  - missing manifests
  - invalid pack dependencies
  - aliases pointing nowhere
  - unsupported content roots
- Prove the layout by migrating or creating one representative non-trivial pack
  only if needed. This should be a proof, not the full migration.
- Add pack-aware discovery:
  - `packs list/inspect/status`
  - pack/category/status/visibility filters on list/search/inspect
  - unified capability search/list/inspect if M0 chose it
  - JSON output suitable for agent consumers
- Update `astrid/skills/discovery.py` and generated agent docs to understand
  the canonical layout.
- Hide/deprecate obvious examples or duplicates in discovery as soon as the
  fields exist, without doing broad file moves.

Out of scope:

- Full `builtin` breakup.
- Large capability tree moves.
- Remote/network pack registry.
- Pack installation from arbitrary URLs.
- Full dependency isolation per pack.

## Constraints

- Discovery should sit on the stable layout and capability identity from M1.
- Do not create a second catalog parallel to the existing registries unless M0
  explicitly requires it.
- Keep existing `executors`, `orchestrators`, and `elements` CLIs working for
  backward compatibility.

## Done Criteria

- New packs scaffold into the canonical layout.
- Existing packs continue to load through compatibility paths.
- Pack validation and runtime discovery agree on accepted manifests.
- Agent-facing discovery can answer: what can I call, what does it need, what
  does it return, what pack owns it, and is it default-visible?
- Skills/AGENTS generation no longer assumes only the old flat layout.
- Tests cover layout variants, pack filters, capability search, JSON inspect,
  and hidden/deprecated visibility behavior.

## Touchpoints

- `astrid/core/pack.py`
- `astrid/packs/cli.py`
- `astrid/packs/validate.py`
- `astrid/skills/discovery.py`
- `astrid/core/executor/cli.py`
- `astrid/core/orchestrator/cli.py`
- `astrid/core/element/cli.py`
- `docs/creating-packs.md`
- `docs/skills-install.md`
- `tests/test_pack_yaml_schema.py`
- `tests/test_packs_cli.py`
- `tests/test_pack_discovery.py`
- `tests/test_canonical_cli.py`

## Anti-Scope

- Do not solve all future package distribution mechanics.
- Do not move Seinfeld/training ownership here.
