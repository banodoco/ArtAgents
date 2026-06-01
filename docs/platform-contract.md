# Platform Contract — v1 Permissions and Trust

This document defines the v1 platform contract for pack permissions, trust
acknowledgement, and SDK discovery. It is a normative reference for
implementors and pack authors. For the user-facing security guidance, see
[SECURITY.md](../SECURITY.md).

## V1 Trust Block Invariants

Every pack trust summary carries a fixed trust block. These values are v1
invariants — they will not change within the v1 major version:

```python
V1_TRUST_BLOCK = {
    "sandbox": "none",
    "runs_with_user_process_permissions": True,
    "permission_enforcement": "disclosure_only",
}
```

These invariants are defined once in `astrid/packs/validate.py` and
consumed by every surface that displays trust metadata: install, update,
inspect, agent view, and SDK discovery.

When a future version adds sandboxing, the trust block will be the first
thing to change. All current consumers source these values through
`extract_trust_summary()` or through direct import of `V1_TRUST_BLOCK`
— there is no second copy.

## Pack-Level Permissions (v1 Scope)

Permissions are declared at the **pack level only** in v1. Every executor
and orchestrator in a pack shares the same declared permission set. There
is no per-executor or per-orchestrator permission declaration in the v1
schema.

### Schema

The `permissions` field in `pack.yaml` is an array of permission objects
validated against `astrid/packs/schemas/v1/pack.json`. Each object:

- Requires `id` (one of six approved enum values) and `reason` (non-blank
  string)
- Accepts optional `access` (non-blank string) and `services` (array of
  non-blank strings)
- Rejects unknown keys (`additionalProperties: false`)

### Normalization

`astrid/core/pack.py` normalizes all permission declarations through
`_normalize_pack_permissions()`. Both construction paths — normal
`load_pack_manifest()` and discovery-validation
`Validator._pack_definition_for_discovery()` — use the same helper.

Normalized permissions become immutable `PackPermission` tuples on
`PackDefinition.permissions`. `PackDefinition.to_dict()` includes the
full structured permission objects.

### Disclosure-Only

Permission declarations are **disclosure metadata**. They do not:

- Configure `IsolationMetadata` or executor isolation behavior
- Derive sandbox profiles or seccomp filters
- Gate runtime capability access
- Restrict filesystem, network, subprocess, or environment access

The `permission_enforcement: disclosure_only` trust block field is the
canonical statement of this boundary. Any code that reads permissions to
make an access-control decision is violating the v1 contract.

## Secrets Are Not Permissions

This is a platform-level distinction:

| Concept | Scope | Declares | Enforcement |
|---|---|---|---|
| Permissions | Pack-level (`pack.yaml`) | Capability domains (network, files, subprocess, etc.) | Disclosure-only |
| Secrets | Executor/orchestrator-level (`executor.yaml`, `orchestrator.yaml`) | Specific environment variable names | Disclosure-only |

A permission says *what kind of thing* the pack does. A secret says
*which specific variable* an executor reads. Both are disclosure-only in
v1. Neither is enforced.

A pack that reads `OPENAI_API_KEY` should declare both:

1. `permissions: [{id: environment, reason: "Reads API keys from environment"}]`
   in `pack.yaml`
2. `secrets: [{name: OPENAI_API_KEY, required: true}]` in the relevant
   executor's manifest

The `environment` permission does not name the variable. The `secrets`
block does not describe the capability domain. They are complementary.

## Trust-on-Install Contract

Installing a pack requires explicit trust acknowledgement. This is a
platform-level contract enforced by `astrid/packs/install.py`.

### Interactive Trust

The interactive flow displays the trust summary (permissions, entrypoints,
secrets, dependencies, v1 trust block, disclosure notice) and requires the
user to type `trust <pack_id>` exactly. The prompt is case-sensitive and
exact-match. Any other input, EOF, or interrupt cancels the install.

### Non-Interactive Trust

The `--trust` CLI flag records non-interactive trust acknowledgement.
`--yes` alone is **not** sufficient — it only skips the ordinary
confirmation prompt (`[y/N]`). An install or update with `--yes` but
without `--trust` fails with an explicit error message.

Both `--yes --trust` together skip both prompts.

### Git Install Trust

Git-backed installs follow the same contract. The trust summary shows the
durable Git URL (not the temp checkout path), the pinned commit SHA (first
8 chars), and the trust tier (`git`). Trust is acknowledged through the
same interactive or `--trust` paths.

### Persistence

Trust decisions are persisted in `InstallRecord` fields written to
`.astrid/install.json`:

```
trust_acknowledged_at: ISO-8601 UTC timestamp
trust_method:           "interactive", "cli_flag", "api", or "test"
trust_actor:            "cli", "api", "test", or another caller label
no_sandbox_warning_version: 1
permissions_accepted:   list of structured permission dicts at accept time
```

The `trust_summary` field on `InstallRecord` preserves the full trust
summary as it was displayed when the user accepted it.

### Update Trust

Updating a pack requires **renewed** trust. The update flow:

1. Extracts trust summaries for both old and new pack versions
2. Formats a diff showing permission additions, removals, and changes
3. Displays the full new trust summary
4. Requires interactive `trust <pack_id>` or `--trust` acknowledgement
5. Persists new trust metadata in the updated install record

Even if permissions have not changed between versions, the update still
requires fresh trust acknowledgement. This is intentional — a new
version may have changed code without changing declared permissions.

### Test Seam

`install_pack()` and `update_pack()` accept `trust_method` and
`trust_actor` keyword parameters for test/internal callers:

```python
install_pack(
    source_path,
    trust_acknowledged=True,
    trust_method="test",
    trust_actor="test",
)
```

These parameters exist so tests can exercise the full install path
without interactive prompts. They must not be exposed through the public
CLI help text.

## Anti-Scope Boundaries

The following are explicit **non-goals** of the v1 permission system.
These boundaries exist so that future versions can introduce enforcement
without breaking the disclosure contract:

### Not Per-Executor

Permissions are pack-level only. There is no `permissions` field on
`executor.yaml` or `orchestrator.yaml` in v1. Every capability in a pack
shares the same declared permission set.

### Not Isolation Configuration

Permissions are not consumed by `IsolationMetadata`. The executor
isolation system (`isolation.mode`, `isolation.binaries`,
`isolation.network`, etc.) is a separate concept. Permissions do not
derive isolation profiles, and isolation metadata does not read
permissions.

### Not Runtime Enforcement

No code path in Astrid v1 reads pack permissions to make an allow/deny
decision at runtime. A pack that declares `permissions: []` runs with
the same full user privileges as a pack that declares all six permissions.

### Not a Diff Against Baseline

Declaring a permission is a positive statement, not a diff. "This pack
needs network access" — not "this pack needs more network access than
before."

### Not Per-Capability

`SafetyDeclaration.permissions` mirrors pack permission IDs into
capability-level metadata, but this is a **mirror**, not a separate
declaration. Capabilities do not independently declare permissions.
The source of truth is the pack manifest.

## SDK Discovery Contract

The public SDK (`astrid.discover()`) exposes pack permissions through
two channels with different shapes:

### Pack-Level (Structured)

`discover().to_dict()["packs"]` includes for each pack:

- `permissions`: list of full structured permission dicts (`id`,
  `reason`, `access`, `services`)
- `permission_ids`: list of compact permission ID strings
- `trust`: the v1 trust block dict (`sandbox`, `runs_with_user_process_permissions`,
  `permission_enforcement`)

These fields are sourced exclusively through `extract_trust_summary()`.
No SDK code re-derives permissions from raw pack data.

### Capability-Level (String IDs Only)

`SafetyDeclaration.permissions` is `tuple[str, ...]`. It contains only
permission ID strings, not structured permission objects. The SDK mirrors
the owning pack's `permission_ids` into each capability's safety
declaration through `_apply_pack_permission_ids()`.

This type contract is stable:

```python
@dataclass(frozen=True)
class SafetyDeclaration:
    network: bool = False
    cost_estimate: str = ""
    secrets_required: tuple[str, ...] = ()
    permissions: tuple[str, ...] = ()  # String IDs only, never structured objects
```

Callers can safely iterate `safety.permissions` without type-narrowing
on individual permission fields. Every element is a plain `str`
matching one of the six approved permission IDs.

### Discovery Output Stability

The `permissions` and `trust` keys in pack records are Tier 2 (evolving)
— new fields may be added within permission objects, but the top-level
keys will not be removed. The `permission_ids` list is also Tier 2.

`SafetyDeclaration.permissions` is Tier 1 (stable) — its type
(`tuple[str, ...]`) will not change without a major version bump.

## Validation Contract

`python3 -m astrid packs validate` checks permission syntax:

- Permission `id` must be one of the six approved values
- `reason` must be present and non-blank
- `access` must be non-blank if present
- `services` must be an array of non-blank strings if present
- Unknown keys on permission objects are rejected
- The `permissions` field must be an array or absent

Validation is **static** — it checks the manifest shape, not runtime
behavior. It does not import or execute pack code.

## Trust Summary Contract

`extract_trust_summary()` in `astrid/packs/validate.py` is the single
canonical source for trust summary data. Every consumer — install, update,
inspect, agent view, SDK discovery — sources trust metadata through this
function or through the `V1_TRUST_BLOCK` constant it defines.

The trust summary dict always contains:

| Key | Type | Description |
|---|---|---|
| `pack_id` | string | Canonical pack id |
| `name` | string | Human-readable name |
| `version` | string | Semver version |
| `schema_version` | int or string | Pack schema version |
| `source_path` | string | Absolute path to pack root |
| `component_counts` | dict | Counts of executors, orchestrators, elements |
| `entrypoints` | list of strings | Normal entrypoints for agent discovery |
| `declared_secrets` | list of strings | Formatted secret declarations |
| `dependencies` | list of strings | Formatted dependency declarations |
| `permissions` | list of dicts | Full structured permission objects |
| `permission_ids` | list of strings | Compact permission ID strings |
| `trust` | dict | V1_TRUST_BLOCK copy (sandbox, runs_with_user_process_permissions, permission_enforcement) |
| `warnings` | list of strings | Advisory warnings (missing docs, missing content roots) |

Consumers must not construct trust metadata independently. If a new
consumer needs trust data, it must call `extract_trust_summary()` or
accept its output from a caller that did.

## References

- [SECURITY.md](../SECURITY.md) — User-facing security model and safe-use guidance
- [docs/creating-packs.md](creating-packs.md) — Pack authoring guide with permission examples
- `astrid/packs/schemas/v1/pack.json` — JSON Schema for the `permissions` field
- `astrid/packs/validate.py` — `V1_TRUST_BLOCK`, `extract_trust_summary()`
- `astrid/packs/install.py` — `_confirm_trust()`, trust persistence, update diff
- `astrid/core/pack.py` — `PackPermission`, `_normalize_pack_permissions()`
- `astrid/contracts/schema.py` — `SafetyDeclaration` with `permissions: tuple[str, ...]`
- `astrid/sdk.py` — `discover()`, `_apply_pack_permission_ids()`

---

*Last updated: v1 permission system (disclosure-only trust model)*
