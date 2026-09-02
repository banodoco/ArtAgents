# Astrid Platform Contract

This document is the normative platform contract for the public Python SDK,
canonical pack manifests, and the disclosure-only trust model. The active pack
grammar is strict v2; older manifest forms are not supported.

For user-facing safe-use guidance, see [SECURITY.md](../../SECURITY.md). For a
friendlier SDK walkthrough, see [docs/sdk.md](../reference/sdk.md).

## Contract Scope

Astrid has one public Python import boundary:

```python
import astrid
```

The contract is defined by:

- the exact top-level names exported by `astrid.__all__`;
- documented signatures and DTO categories reachable from `import astrid`;
- the strict-v2 schema at `astrid/core/pack/schemas/v2/pack.json`;
- disclosure-only trust/install rules in this document.

The contract is not defined by internal module layout, registry internals, or
CLI implementation modules.

## Public SDK Boundary

### Supported Top-Level Exports

`astrid.__all__` is the source of truth for the supported top-level Python SDK
surface in v1. It contains exactly 28 names:

- Functions: `discover`, `get_capability`, `invoke`, `generate`,
  `read_events`, `subscribe_events`
- DTOs: `Capability`, `DiscoveryResult`, `EventStreamRecord`,
  `InvocationResult`, `CapabilityHandle`, `Port`, `Output`, `AliasRecord`,
  `Provenance`, `SafetyDeclaration`, `ExecError`
- Exceptions: `AstridSDKError`, `CapabilityNotFoundError`,
  `CapabilityAmbiguousError`, `CapabilityValidationError`,
  `CapabilityMissingInputError`, `CapabilityPreconditionError`,
  `CapabilityRuntimeError`, `CapabilityLeaseError`,
  `CapabilityEventLogError`, `UnsupportedCapabilityError`,
  `CapabilityInvocationError`

Anything importable from `astrid` outside this list is out of contract for v1.

### Public Boundary Rule

The supported import pattern is:

```python
import astrid
```

Callers may access the supported names as `astrid.<name>`. This is the public
boundary Astrid commits to for v1.

### Non-Contract Surfaces

The following surfaces are explicitly out of the v1 public contract, even if
they are importable today:

- `astrid.sdk` as a direct import target
- Everything under `astrid.core.*`
- Everything under `astrid.packs.*`
- Registry internals, resolver internals, and helper functions used to build
  DTOs
- CLI implementation modules and verb routing modules (for example gateway and command-entry internals)
- Internal tests, fixtures, and generated discovery payload shapes not exposed
  through the documented DTO contract

These surfaces may change in any minor or patch release without deprecation.

## SemVer And Deprecation

Astrid follows SemVer for the public boundary defined above.

- Patch releases may fix bugs and clarify behavior without breaking the
  documented v1 contract.
- Minor releases may add new top-level keyword parameters, DTO fields, manifest
  schema fields, and discovery metadata when those additions are backward
  compatible.
- Major releases may remove or break previously public v1 surfaces.

### Deprecation Window

The default deprecation window for a public v1 surface is **two minor
releases**.

Example: if a deprecation first ships in `1.4.0`, the surface remains supported
through `1.5.x` and may be removed no earlier than `1.6.0`.

This two-minor rule is the concrete v1 policy unless a stricter per-surface
guarantee is documented. It is intentionally conservative while broader SDK
governance remains lightweight.

Deprecations should use the existing alias/deprecation metadata model where
possible and should point callers at the replacement surface.

## DTO Stability Tiers

Astrid v1 uses three stability tiers for data returned from the public SDK.

### Tier 1 — Stable Contract Fields

These names, signatures, and top-level DTO fields are SemVer-guarded:

- Exported names in `astrid.__all__`
- Function signatures for `discover()`, `get_capability()`, `invoke()`,
  `generate()`, `read_events()`, and `subscribe_events()`
- The existence of these DTO types: `Capability`, `DiscoveryResult`,
  `InvocationResult`, `EventStreamRecord`, `CapabilityHandle`, `Port`,
  `Output`, `AliasRecord`, `Provenance`, `SafetyDeclaration`, `ExecError`
- `Capability` top-level fields: `id`, `capability_type`, `native_kind`,
  `handle`, `inputs`, `outputs`, `schema`, `defaults`, `definition`
- `DiscoveryResult` top-level fields: `executors`, `orchestrators`, `elements`,
  `capabilities`, `packs`, `generation_backends`, `element_kinds`,
  `generation_features`, `generation_modes`
- `InvocationResult` top-level fields: `capability_id`, `capability_type`,
  `native_kind`, `ok`, `error`, `manifest_path`, `raw_result`
- `EventStreamRecord` top-level fields: `source`, `line`, `timestamp`, `kind`,
  `hash`, `payload`
- The exported exception names and their place in the public exception family

### Tier 2 — Evolving/Additive Fields

These fields are part of the public contract, but may grow additional keys or
keyword parameters in minor releases:

- Fields on `CapabilityHandle`, `Port`, `Output`, `AliasRecord`, `Provenance`,
  `SafetyDeclaration`, and `ExecError`
- New keyword-only parameters on `discover()`, `get_capability()`, `invoke()`,
  and `generate()`
- The key sets of `to_dict()` results for public DTOs
- Pack records in `DiscoveryResult.packs`
- Records in `DiscoveryResult.generation_backends`,
  `DiscoveryResult.element_kinds`, `DiscoveryResult.generation_features`, and
  `DiscoveryResult.generation_modes`

Tier 2 means Astrid will not silently remove or rename existing documented
fields in a v1 minor or patch release, but additive growth is allowed.

### Tier 3 — Opaque/Evolving Payloads

These values are public return fields, but their internal key names, nesting,
and value shapes are intentionally treated as opaque payloads:

- `Capability.schema`
- `Capability.definition`
- `Capability.defaults`
- `InvocationResult.raw_result`
- `InvocationResult.error`
- `EventStreamRecord.payload`
- Nested output of `DiscoveryResult.to_dict()`

Callers may serialize these payloads, display them, or pass them through, but
should not build brittle logic around undocumented nested keys.

## Manifest And Schema Contract

### Canonical v2 pack manifest

Every pack has exactly one `pack.yaml` with `schema_version: 2`. The required
identity fields are `schema_version`, `id`, `name`, and `version`; the pack
must declare at least one contribution. `pack.yml`, `pack.json`,
`schema-pack.yaml`, schema-less YAML, flat legacy mappings, unknown fields, and
path escapes are rejected.

The normative pack grammar is
`astrid/core/pack/schemas/v2/pack.json`. It covers identity, taxonomy,
capabilities/content roots, extensions, optional bundled database ownership,
structured documentation, standalone resources, dependencies, permissions,
secrets, and authoring exclusions.

The canonical loader is the single read-normalize-validate path used by
`BundledCatalog`. Its projections carry pack identity, provenance, immutable
database declarations, documentation, and confined resource handles. Consumers
must use those projections rather than independently reparsing manifests or
reconstructing ownership.

### Component and extension manifests

Executor, orchestrator, element, renderer, planner, and finalizer manifests
remain typed component contracts under their existing schemas. They do not
create another pack identity or database authority. The owning pack's v2
manifest declares content roots and pack-relative rendering extension paths.

### Database contribution

Trusted bundled packs may declare a `database` block containing migration
identity, owned tables, vocabulary, repositories, conformance, CLI mounts,
bridge mounts, and positive dependency migration heads. Migration SQL remains
the authority for DDL and transformations. External packs cannot declare a
database contribution during beta.

## Pack Extensions

The strict-v2 `extensions` block carries pack-owned typed extensions. Generation
taxonomy entries and rendering backend/planner/finalizer paths remain typed
registry inputs; they do not create a second pack identity or database owner.
The canonical catalog preserves their owning pack and confined resource handles.

Packs may declare generation extensions under
`pack.extensions.generation.backends`, `features`, and `modes`, and rendering
extensions under `pack.extensions.rendering.renderers`, `planners`, and
`finalizers`. The v2 pack schema validates the declaration; the existing typed
registries consume the corresponding projections.

Element-kind extensions use `pack.extensions.elements.kinds`. Element
capabilities remain scoped by their owning pack and kind. Agents discover them
through `astrid.discover()` and `astrid.get_capability()`; direct imports from
internal registries are not part of the public SDK boundary.

Declared extension paths are pack-relative. The source and installed closure
checks require every rendering extension file to resolve within its owner root.

## Disclosure-Only Trust And Security

Every pack trust summary carries the fixed disclosure block:

```python
TRUST_BLOCK = {
    "sandbox": "none",
    "runs_with_user_process_permissions": True,
    "permission_enforcement": "disclosure_only",
}
```

Permissions are pack-level disclosure metadata. They require `id` and `reason`,
may include `access` and `services`, and are validated by the strict-v2 pack
schema. They do not create sandbox rules, configure `IsolationMetadata`, or
enforce filesystem, subprocess, network, or environment access.

Secrets are separate component declarations:

| Concept | Declared in | Meaning |
|---|---|---|
| Permissions | v2 pack manifest | Capability domains such as network, files, subprocess, and environment |
| Secrets | executor/orchestrator manifest | Specific environment variable names |

Trust acknowledgement remains required before installing or updating an
external pack. `extract_trust_summary()` is the canonical source used by
install, update, inspect, agent-facing views, and SDK discovery; consumers
must not reconstruct it independently.

## Validation Boundary

`python3 -m astrid.core.pack.cli validate` performs strict-v2 static
validation. It checks identity, schema shape, declared content roots,
documentation, resource confinement, and database declaration shape without
importing or executing pack code. Runtime behavior remains the responsibility
of the typed capability/database conformance checks.


## References

- [SECURITY.md](../../SECURITY.md) — user-facing security posture
- [docs/sdk.md](../reference/sdk.md) — SDK walkthrough and examples
- [docs/packs/creating-packs.md](../packs/creating-packs.md) — pack authoring reference
- `astrid/__init__.py` — top-level public export list
- `astrid/sdk/` — public SDK DTOs and function entrypoints
- `astrid/core/contracts/schema.py` — shared DTO field types
- `astrid/core/pack/schemas/v2/pack.json` — strict-v2 pack grammar
- `astrid/core/pack/validate.py` — trust summary extraction and trust block source
- `astrid/core/pack/install.py` — trust acknowledgement/install behavior
