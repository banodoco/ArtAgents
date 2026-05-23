# Milestone 0: Thin Pack Contract

## Outcome

Write the short contract that later milestones implement. This milestone should
lock Astrid's pack-first model without trying to settle every future registry,
update, or packaging policy in detail.

## Scope

In scope:

- Inspect the current pack/discovery surfaces:
  - `astrid/core/pack.py`
  - executor, orchestrator, and element registries/CLIs
  - `astrid/packs/cli.py` and `astrid/packs/validate.py`
  - `astrid/skills/discovery.py`
  - `docs/creating-packs.md`
  - current `astrid/packs/*/pack.yaml` files
- Define the small vocabulary:
  - pack
  - default-enabled pack
  - optional pack
  - personal pack
  - adapter pack
  - example pack
  - capability
  - alias
  - fork
  - override
  - in-place edit
- Separate the axes currently overloaded into "built-in" and "external":
  - namespace / id prefix
  - distribution/source location
  - enablement policy
  - ownership/support boundary
  - maturity/status
  - trust/safety profile
- Define the shared `Capability` / `CapabilityHandle` concept:
  - `kind`: `executor`, `orchestrator`, or `element`
  - canonical id and local id
  - pack id
  - aliases / deprecation state
  - status and visibility
  - provenance
  - inspectable inputs and outputs where already available
  - safety/cost/secrets/network declarations
- Decide the minimum pack manifest fields needed now:
  - id, name, description
  - author or namespace
  - source block (`bundled`, `local`, `git`, etc.)
  - enablement/default visibility
  - dependencies on other packs
  - compatibility/version policy, either semantic or explicitly opaque
- Decide the alias/deprecation policy before public ids move.
- Decide how default discovery behaves for agents:
  - which packs/statuses are shown by default
  - how `--all` or explicit filters expose hidden/example/deprecated items
  - whether a unified `capabilities search/list/inspect` surface is required
- Reconcile the intended relationship between:
  - `astrid/core/pack.py` minimal runtime parser
  - `astrid/packs/validate.py` richer schema validation
  - `packs new` scaffold layout
- Account for existing element fork/local-pack priority semantics.
- Produce a first placement map for current pack groups:
  - default-enabled core
  - optional workflow
  - adapter/substrate
  - personal pack
  - example/test
  - deprecated/hidden/delete

Out of scope:

- Moving capability directories.
- Implementing pack enable/disable.
- Implementing fork/update commands.
- Full semantic merge/update policy.
- Remote or hosted pack registry.

## Locked Decisions

- Every discoverable executor, orchestrator, and element belongs to a pack.
- A pack is the distribution/namespace container, not the only taxonomy axis.
- "Built-in" means default-enabled and Astrid-supported; it does not require a
  monolithic `builtin` pack.
- "External" must not mean "uses network/API"; adapter packs are for
  separately-owned substrate semantics such as VibeComfy or RunPod.
- Agents discover capabilities through manifest-backed list/search/inspect
  surfaces, not source-tree guessing.
- Public id migration requires tested alias infrastructure first.
- The existing element fork/local-pack behavior is useful precedent.

## Done Criteria

- A concise contract document exists and later milestones can cite it.
- The contract defines pack axes, default-enabled semantics, capability
  identity, alias/deprecation semantics, and the default agent discovery
  contract.
- The contract says how `pack.py`, `packs/validate.py`, and scaffolded pack
  manifests should converge.
- The contract includes a concrete first placement map for the current repo.
- Anything not needed to unblock M1-M3 is explicitly deferred.

## Touchpoints

- `astrid/core/pack.py`
- `astrid/core/executor/`
- `astrid/core/orchestrator/`
- `astrid/core/element/`
- `astrid/packs/`
- `astrid/skills/discovery.py`
- `docs/creating-packs.md`
- `docs/creating-tools.md`
- `docs/megaplan/epics/pack-system/`

## Anti-Scope

- Do not split `builtin` here.
- Do not add a remote package manager.
- Do not delete or move `astrid/packs/seinfeld`; coordinate with the
  builtin-training epic.
