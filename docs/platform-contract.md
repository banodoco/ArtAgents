# Astrid Platform Contract — v1

This document is the normative v1 platform contract for the public Python SDK,
manifest schemas, and the disclosure-only trust model. If this document and any
other SDK or pack-system doc disagree, this file wins.

For user-facing safe-use guidance, see [SECURITY.md](../SECURITY.md). For a
friendlier SDK walkthrough, see [docs/sdk.md](sdk.md).

## Contract Scope

Astrid v1 has one public Python import boundary:

```python
import astrid
```

The v1 contract is defined by:

- The exact top-level names exported by `astrid.__all__`
- The documented signatures and DTO categories reachable from `import astrid`
- The v1 manifest schema files under `astrid/packs/schemas/v1/`
- The disclosure-only trust/install rules in this document

The v1 contract is **not** defined by internal module layout, lazy-loader
implementation details, registry internals, or CLI implementation modules.

## Public SDK Boundary

### Supported Top-Level Exports

`astrid.__all__` is the source of truth for the supported top-level Python SDK
surface in v1. It contains exactly 27 names:

- Functions: `discover`, `get_capability`, `invoke`, `read_events`,
  `subscribe_events`
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
- CLI implementation modules and verb routing modules (for example pipeline and
  command-entry internals)
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
  `read_events()`, and `subscribe_events()`
- The existence of these DTO types: `Capability`, `DiscoveryResult`,
  `InvocationResult`, `EventStreamRecord`, `CapabilityHandle`, `Port`,
  `Output`, `AliasRecord`, `Provenance`, `SafetyDeclaration`, `ExecError`
- `Capability` top-level fields: `id`, `capability_type`, `native_kind`,
  `handle`, `inputs`, `outputs`, `schema`, `defaults`, `definition`
- `DiscoveryResult` top-level fields: `executors`, `orchestrators`, `elements`,
  `capabilities`, `packs`, `generation_backends`, `element_kinds`,
  `generation_features`, `generation_modes`
- `InvocationResult` top-level fields: `capability_id`, `capability_type`,
  `native_kind`, `ok`, `error`, `raw_result`
- `EventStreamRecord` top-level fields: `source`, `line`, `timestamp`, `kind`,
  `hash`, `payload`
- The exported exception names and their place in the public exception family

### Tier 2 — Evolving/Additive Fields

These fields are part of the public contract, but may grow additional keys or
keyword parameters in minor releases:

- Fields on `CapabilityHandle`, `Port`, `Output`, `AliasRecord`, `Provenance`,
  `SafetyDeclaration`, and `ExecError`
- New keyword-only parameters on `discover()`, `get_capability()`, and
  `invoke()`
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

### Canonical v1 Manifest Files

Astrid v1 recognizes these manifest families:

- Pack manifests: `pack.yaml`, `pack.yml`, or `pack.json`
- Executor manifests: `executor.yaml`, `executor.yml`, or `executor.json`
- Orchestrator manifests: `orchestrator.yaml`, `orchestrator.yml`, or
  `orchestrator.json`
- Element manifests: `element.yaml`, `element.yml`, or `element.json`

The schema contract for those manifests is defined by the JSON Schema files
under `astrid/packs/schemas/v1/`.

### Normative v1 Schema Files

All v1 manifest schema files are part of the contract:

| File | Role |
|---|---|
| `astrid/packs/schemas/v1/pack.json` | Validates pack manifests and pack-level declarations |
| `astrid/packs/schemas/v1/executor.json` | Validates executor manifests |
| `astrid/packs/schemas/v1/orchestrator.json` | Validates orchestrator manifests |
| `astrid/packs/schemas/v1/element.json` | Validates element manifests |
| `astrid/packs/schemas/v1/_defs.json` | Shared schema definitions referenced by the manifest schemas above |

The v1 contract covers the existence and intended roles of these files. It does
not promise byte-for-byte immutability of schema internals; backward-compatible
validation additions may land in minor releases.

### Stable Vs Opaque Manifest Areas

Stable manifest contract areas include:

- Which manifest families exist
- Which top-level schema files validate them
- Pack-level permissions being declared in the pack manifest
- Executor/orchestrator secrets being declared in their component manifests
- The existence of alias/deprecation metadata in pack manifests

Opaque or evolving manifest areas include:

- Undocumented nested schema keys
- Generator-facing metadata used only by internal discovery/build tooling
- Exact serialized ordering of manifest keys
- Any internal registry-only normalization details not surfaced through the
  public SDK

## Element Extension APIs

Element extension support exists in v1, but the extension API itself is
**provisional**.

This includes:

- `pack.extensions.elements.kinds`
- External element pack discovery through `ASTRID_PACKS_PATH`
- Related registry/typegen behavior that makes external element kinds visible

Astrid supports these workflows in v1, but does not yet treat their detailed
programmatic contract as Tier 1. Callers and pack authors should expect
additive or structural refinement in minor releases.

## Disclosure-Only Trust And Security

This section preserves the existing v1 trust/security contract as a first-class
part of the platform boundary.

### V1 Trust Block Invariants

Every pack trust summary carries this fixed v1 trust block:

```python
V1_TRUST_BLOCK = {
    "sandbox": "none",
    "runs_with_user_process_permissions": True,
    "permission_enforcement": "disclosure_only",
}
```

These values are v1 invariants. They will not change within the v1 major
version.

### Permissions Are Pack-Level Disclosure Metadata

Permissions are declared at the pack level only in v1. There is no separate
per-executor or per-orchestrator permission contract.

The `permissions` field in the pack manifest:

- Requires `id` and `reason`
- Allows optional `access` and `services`
- Rejects unknown keys
- Is validated by `astrid/packs/schemas/v1/pack.json`

Permissions are disclosure metadata. They do **not**:

- Create sandbox rules
- Configure `IsolationMetadata`
- Enforce runtime allow/deny checks
- Restrict filesystem, subprocess, network, or environment access

The canonical statement of that boundary is
`permission_enforcement: disclosure_only`.

### Secrets Are Separate From Permissions

This distinction is part of the v1 contract:

| Concept | Declared In | Meaning |
|---|---|---|
| Permissions | Pack manifest | Capability domains such as network, files, subprocess, environment |
| Secrets | Executor/orchestrator manifests | Specific environment variable names |

Permissions answer "what kind of access does this pack claim to use?" Secrets
answer "which variable names does this component claim to read?"

### Trust-On-Install Contract

Astrid requires explicit trust acknowledgement before installing or updating a
pack.

- Interactive installs require exact `trust <pack_id>` input
- `--yes` is not enough by itself
- `--trust` is the non-interactive trust acknowledgement
- Git installs follow the same trust rules
- Updates require renewed trust, even if declared permissions did not change

Trust decisions are persisted in `.astrid/install.json`, including accepted
permissions and acknowledgement metadata.

### Trust Summary Contract

`extract_trust_summary()` is the canonical source for trust summary data used by
install, update, inspect, agent-facing views, and SDK discovery.

The trust summary includes:

- Pack identity and version
- Component counts and entrypoints
- Declared secrets and dependencies
- Structured permissions and compact `permission_ids`
- The v1 trust block
- Advisory warnings

Consumers must not reconstruct this data independently.

## Validation Boundary

`python3 -m astrid packs validate` performs static manifest validation. In v1 it
checks schema/shape validity, not runtime behavior. Validation does not promise
that a pack behaves safely or only does what its declarations describe.

## References

- [SECURITY.md](../SECURITY.md) — user-facing security posture
- [docs/sdk.md](sdk.md) — SDK walkthrough and examples
- [docs/creating-packs.md](creating-packs.md) — pack authoring reference
- `astrid/__init__.py` — top-level public export list
- `astrid/sdk.py` — public SDK DTOs and function entrypoints
- `astrid/contracts/schema.py` — shared DTO field types
- `astrid/packs/schemas/v1/` — normative v1 manifest schema files
- `astrid/packs/validate.py` — trust summary extraction and trust block source
- `astrid/packs/install.py` — trust acknowledgement/install behavior
