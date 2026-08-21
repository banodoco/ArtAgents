# Astrid Pack Contract

This is the Milestone 0 contract for Astrid's pack-first capability system. It
names the model later milestones implement; it does not change runtime behavior
by itself.

## Locked Decisions

- Every discoverable executor, orchestrator, and element belongs to a pack.
- A pack is the distribution and namespace container, not the only taxonomy
  axis.
- Built-in means default-enabled and Astrid-supported. It does not require one
  monolithic `builtin` pack.
- External must not mean "uses network or API." Adapter packs model separately-owned
  substrates such as VibeComfy, RunPod, fal, or Moirae.
- Agents discover capabilities through manifest-backed list/search/inspect
  surfaces, not source-tree guessing.
- Public id migration requires tested alias infrastructure first.
- Existing element fork and local-pack behavior is useful precedent for broader
  fork and override work.

## Vocabulary

- **Pack**: a named namespace and distribution unit containing capabilities and
  pack-level metadata. A pack can be bundled with Astrid, local to a user, or
  obtained from another source.
- **Default-enabled pack**: a pack whose visible, supported capabilities appear
  in normal agent discovery without extra flags. This is the target meaning of
  "built-in."
- **Optional pack**: a pack that is valid and inspectable but not shown in the
  default agent discovery set until explicitly enabled or requested.
- **Personal pack**: a user-owned local pack for experiments, private tools, or
  forks. It must not be silently overwritten by Astrid updates.
- **Adapter pack**: a pack that integrates a separately-owned substrate,
  service, CLI, model host, or runtime. Adapter does not imply unsafe; it means
  ownership and support differ from Astrid core.
- **Example pack**: a teaching, fixture, or scaffold pack. It can be validated
  and inspected, but it should not clutter default discovery.
- **Capability**: an executable or renderable thing an agent can discover and
  use. Current capability kinds are `executor`, `orchestrator`, and `element`.
- **Alias**: an alternate public id that resolves to a canonical capability id.
  Aliases preserve old ids during moves and must be validated before any public
  id migration.
- **Fork**: a copied capability or pack that the user owns. A fork keeps
  provenance back to its source and can diverge.
- **Override**: a registry preference that chooses one capability instead of
  another without changing the target's public id.
- **In-place edit**: a local modification inside an installed or bundled pack.
  It is a detectable state, not the preferred customization path. Update flows
  should help promote meaningful in-place edits into forks.

## Pack Axes

Do not overload one word such as `built_in` or `external` to answer every pack
question. Pack metadata must keep these axes separate:

| Axis | Meaning | Examples |
| --- | --- | --- |
| Namespace / id prefix | The first segment of capability ids and the owning pack id. | `builtin`, `editorial`, `fal`, `iteration` |
| Distribution / source | Where the pack comes from. | bundled, local, personal, git, future registry |
| Enablement | Whether normal discovery includes the pack by default. | default-enabled, optional, disabled/hidden |
| Ownership / support | Who maintains and supports the pack. | Astrid-supported, user-owned, adapter-owned, example |
| Maturity / status | Whether the pack or capability should be used. | stable, experimental, deprecated, hidden, example |
| Trust / safety profile | What the pack may do and what review it needs. | local-only, networked, secrets, paid APIs, external binaries |

The current executor/orchestrator `kind: built_in|external` field is legacy
component metadata. Later milestones may preserve it for compatibility, but it
is not enough to describe a pack.

## Capability Identity

Later milestones should expose a shared `Capability` / `CapabilityHandle`
concept across executors, orchestrators, and elements without forcing every kind
into one registry implementation.

`CapabilityHandle` is the stable reference an agent, manifest, child edge, or
alias can point at. Its common shape is:

- `kind`: `executor`, `orchestrator`, or `element`.
- `canonical_id`: the stable public id used for canonical lookup and docs.
- `requested_id`: the id the caller used, when lookup came through an alias.
- `local_id`: the id inside the owning pack, when different from canonical id.
- `pack_id`: the owning pack namespace.
- `aliases`: old or alternate ids that resolve to the canonical id.
- `deprecation`: whether the requested id or canonical capability is
  deprecated, including replacement id, reason, and removal window when known.
- `status` and `visibility`: stable/experimental/example/hidden/deprecated and
  default-visible or explicit-only.
- `provenance`: source, manifest path, content root, fork source, and override
  state when relevant.

`Capability` is the inspectable definition behind a handle. It includes the
handle fields plus the kind-specific contract already present today:

- Executors expose declared inputs, outputs, command/runtime invocation,
  isolation, cache behavior, binaries, and safety/cost/secrets/network
  declarations where available.
- Orchestrators expose declared inputs, outputs, runtime invocation, child
  executors, child orchestrators, and the same safety/cost/secrets/network
  declarations where available.
- Elements expose element kind (`effects`, `animations`, or `transitions`),
  source/priority/editability, fork target, dependencies, defaults, schema, and
  safety declarations where relevant.

Canonical inspect output should make identity resolution explicit. Inspecting a
capability through any current or future surface should show at least:

- requested id, when different from canonical id;
- canonical id;
- capability kind;
- owning pack id;
- alias/deprecation state;
- status and visibility;
- provenance and manifest path;
- fork or override state, when present;
- inputs, outputs, dependencies, and safety/cost/secrets/network declarations
  that the capability kind can already inspect.

Alias and deprecation behavior is part of identity, but it is future-facing for
M0. Later milestones should implement:

- old public id to canonical id resolution before lookup fails;
- inspect output that records the requested alias and canonical target;
- warnings or structured metadata for deprecated aliases;
- validation for alias cycles, missing targets, and conflicting aliases;
- child executor/orchestrator references that can resolve through aliases only
  after alias validation exists;
- tests before any public id moves.

M0 defines this identity and alias policy only. It does not rename existing ids,
move capabilities, add alias manifests, or implement alias resolution.

## Historical: M0 Discovery Behavior (2025)

> **Note:** This section is a dated historical record. M0 discovery was
> intentionally over-visible: it loaded every immediate child of `astrid/packs/`
> with a `pack.yaml`/`pack.yml`/`pack.json` manifest, did not enforce
> visibility/status filtering, exposed only `--kind built_in|external` on
> executor/orchestrator surfaces, and did not consume the pack contract in
> skill discovery. The target M1-M3 contract below describes the intended
> behavior that later milestones progressively implement.

## Target M1-M3 Discovery Contract

Later milestones should make normal agent discovery show only visible
capabilities from default-enabled packs. Hidden, example, deprecated, personal,
or optional capabilities should require explicit enablement, `--all`, or
specific filters after those mechanics exist.

Target list/search/inspect surfaces should make these questions answerable
without source reading:

- What capability can I call?
- Which pack owns it?
- Is it default-visible, optional, hidden, example, or deprecated?
- What inputs and outputs does it declare?
- Does it use network, secrets, paid services, external binaries, or unusual
  local file access?
- Did I resolve an alias, fork, or override?

A future unified `capabilities list/search/inspect` surface is required by this
contract. Its target behavior is:

- list capabilities across executors, orchestrators, and elements without
  losing kind-specific fields;
- search by id, alias, pack id, status, visibility, safety profile, and
  keywords;
- inspect a canonical capability handle with requested id, canonical id, owning
  pack, alias/deprecation state, provenance, inputs/outputs, and safety data;
- keep existing executor, orchestrator, and element list/search/inspect CLIs
  working while exposing equivalent pack-aware metadata;
- make `--all` or explicit filters the way to include hidden, example,
  deprecated, optional, and personal capabilities once filtering is implemented.

M0 does not implement unified capability discovery, `--all`, status filters,
visibility filters, enable/disable mechanics, or hidden/example/deprecated
enforcement.

## Manifest And Runtime Convergence

The current system has two related but different pack paths:

- `astrid/core/pack/discovery.py`: permissive runtime loading. It should keep current
  in-repo packs working while later milestones teach it the richer contract.
  Its job is to find loadable pack manifests and provide normalized runtime
  pack definitions; it should not become the authoring linter or policy manual.
- `astrid/core/pack/validate.py`: author-facing static validation. It should own
  schema-version checks, declared content-root checks, doc/entrypoint existence
  checks, and clear builder-facing errors without importing or running pack
  code.
- `python3 -m astrid.core.pack.cli new` (the internal pack CLI): scaffolded
  manifest production. It should
  create packs that satisfy the authoring schema and include the target fields
  as they become implemented, while keeping generated skeletons small.

Later milestones should converge these paths around one pack model while
preserving compatibility for existing flat in-repo packs long enough to migrate
them safely.

Responsibility boundaries:

- Runtime loading accepts compatible manifest-backed packs and returns enough
  metadata for registries to attach pack provenance.
- Validation rejects malformed authoring manifests and missing declared files
  before runtime discovery has to handle them.
- Scaffolding emits the recommended layout and manifest shape; it should not
  imply that every existing bundled pack has already migrated.
- None of these surfaces should independently invent enablement, alias,
  distribution, or safety semantics. Those fields should converge through the
  shared pack/capability contract.

Minimum pack manifest fields needed by the target contract:

- `id`, `name`, and `description`.
- author or namespace owner.
- source block: bundled, local, personal, git, or future registry source.
- enablement and default visibility.
- dependencies on other packs.
- compatibility/version policy, semantic when possible and explicitly opaque
  when not.
- ownership/support boundary.
- trust/safety summary inherited by capabilities unless overridden.

Minimum capability manifest fields needed by the target contract, whether they
live in executor, orchestrator, or element schemas:

- canonical id, local id, and owning pack id;
- capability kind;
- status and visibility;
- aliases and deprecation metadata, once alias support exists;
- provenance/source metadata;
- inspectable inputs and outputs where the kind supports them;
- safety/cost/secrets/network declarations.

## Current Pack Listing

The canonical runtime pack listing and per-pack taxonomy assignments are
maintained in **[pack-taxonomy.md](pack-taxonomy.md)**. See that document's
domain table and Example Packs section for the current `astrid/packs/`
inventory, shell classifications (`_core`, `builtin`), and example packs under
`examples/packs/`.

### Mapping Contract Axes to Taxonomy Fields

The six conceptual axes defined in §Pack Axes above map onto
`pack-taxonomy.md`'s six machine-readable fields as follows:

| Contract Axis | Taxonomy Field |
|---|---|
| Namespace / id prefix | `id` (pack-level), `domain` (grouping axis) |
| Distribution / source | `origin` |
| Enablement | `install_tier` |
| Ownership / support | `support` |
| Maturity / status | `stability` |
| Trust / safety profile | `permissions` block (pack-level, not a taxonomy enum) |

The trust/safety axis is expressed through the `permissions` block in
`pack.yaml` rather than a single taxonomy enum, since safety posture is
multi-dimensional (network access, secrets, paid APIs, external binaries).

Element precedence remains the current implementation precedent:

1. Active theme elements override other sources when an active theme is set.
2. Project `local` pack forks override bundled pack elements when a distinct
   project root is used.
3. Bundled pack elements provide the fallback managed implementation.

That precedence is documentation of current behavior, not a command to move
elements during M0. Later fork/override work should reuse this ordering where it
fits executors, orchestrators, and whole packs.

## Deferred Scope

M0 deliberately does not implement:

- pack enable/disable mechanics;
- discovery filtering or `--all` behavior;
- alias resolution;
- alias manifests or alias validation;
- public id moves;
- remote or hosted registries;
- package installation from remote sources;
- pack directory moves;
- fork/update commands;
- fork/update reports;
- dependency isolation;
- semantic merge/update intelligence;
- rich capability graph planning;
- runtime enforcement of every safety declaration;
- broad cleanup of generated or example packs.

Those are later milestone responsibilities. The contract exists so those
changes can be implemented without reusing overloaded terminology.
