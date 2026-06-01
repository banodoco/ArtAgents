# Astrid Python SDK

The `astrid` package exposes a public Python SDK for capability discovery,
schema inspection, and invocation. Import the top-level package — the SDK
surface is available directly from `import astrid`.

```python
import astrid

# Discovery
inventory = astrid.discover(include_installed=False)
for cap in inventory.capabilities:
    print(cap.id, cap.capability_type)

# Lookup
cap = astrid.get_capability("editorial.arrange", kind="executor", include_installed=False)
print(cap.schema, cap.inputs, cap.outputs)

# Invocation (dry-run)
result = astrid.invoke(
    "editorial.arrange",
    kind="executor",
    include_installed=False,
    out="/tmp/arrange-out",
    dry_run=True,
)
print(result.ok, result.raw_result)
```

## Quick Examples

### Discovery

```python
import astrid

inventory = astrid.discover(
    project_root="./my-project",
    include_installed=False,
)

# Typed grouped access
for executor in inventory.executors:
    print(executor.id)

for element in inventory.elements:
    print(element.id, element.native_kind)

# Flat all-capabilities view
print(len(inventory.capabilities))

# JSON-safe serialization
import json
json.dumps(inventory.to_dict())
```

`discover()` loads the executor, orchestrator, and element registries in
dependency order (executor first, then orchestrator, then elements). Element
loading is theme-aware: pass `active_theme` to include theme-specific element
overlays, and `include_missing_roots=True` to include element roots that have
not been locally installed yet.

### Schema Inspection

```python
import astrid

cap = astrid.get_capability(
    "editorial.arrange",
    kind="executor",
    include_installed=False,
)

# Stable DTO fields
print(cap.id)                # "editorial.arrange"
print(cap.capability_type)   # "executor"
print(cap.native_kind)       # "built_in" or "external"

# Inspect inputs and outputs
for port in cap.inputs:
    print(port.name, port.type, port.required)

for output in cap.outputs:
    print(output.name, output.type)

# Serialized schema mapping (keyed by field name)
print(cap.schema["runtime_kind"])
print(cap.schema["isolation"]["mode"])

# Full definition payload (same as schema for executors/orchestrators;
# separate from schema for elements)
print(cap.definition["inputs"])

# Identity handle with aliases and provenance
print(cap.handle.canonical_id)
for alias in cap.handle.aliases:
    print(alias.alias, "->", alias.canonical_id, "deprecated:", alias.deprecated)
```

### Dry-Run Invocation

Dry-run invocations validate request construction and registry routing without
executing side effects. The returned `InvocationResult` carries the normalized
command, environment, and dry-run metadata.

```python
import astrid
from pathlib import Path

result = astrid.invoke(
    "editorial.arrange",
    kind="executor",
    include_installed=False,
    out=Path("./out/arrange-test"),
    project="demo-project",
    inputs={"brief": "test"},
    dry_run=True,
    verbose=True,
)
print(result.ok)                    # True if no validation errors
print(result.raw_result["dry_run"])  # True
print(result.raw_result["command"])
```

### Regular Invocation

```python
import astrid

result = astrid.invoke(
    "editorial.arrange",
    kind="executor",
    include_installed=False,
    out="./out/arrange-real",
    project="demo-project",
    inputs={"brief": "resize and normalize"},
    python_exec="/usr/bin/python3",
)
print(result.ok)                      # True on success
print(result.raw_result["returncode"])  # 0 on success
print(result.error)                   # ExecError mapping if !ok
```

Orchestrator invocation omits the `out` requirement:

```python
result = astrid.invoke(
    "video_editing.hype",
    kind="orchestrator",
    include_installed=False,
    inputs={"video": "input.mp4"},
    brief="./brief.md",
    orchestrator_args=("--render",),
    dry_run=True,
)
print(result.raw_result["planned_commands"])
```

### Typed Error Handling

All SDK errors inherit from `AstridSDKError`. Catch the base class for general
handling or specific subclasses for precise recovery.

```python
import astrid

# Not-found
try:
    astrid.get_capability("missing.capability", kind="executor")
except astrid.CapabilityNotFoundError as e:
    print(f"Not found: {e}")

# Ambiguous bare lookup
try:
    astrid.get_capability("fade", kind="element")
except astrid.CapabilityAmbiguousError as e:
    print(f"Multiple matches: {e}")
    # e carries candidate list in the message

# Element invocation is rejected
try:
    astrid.invoke("effects/text-card", kind="element")
except astrid.UnsupportedCapabilityError as e:
    print(f"Cannot invoke element: {e}")

# Missing required out path for executors
try:
    astrid.invoke("editorial.arrange", kind="executor")
except astrid.CapabilityInvocationError as e:
    print(f"Invocation error: {e}")

# Runner exceptions are preserved as __cause__
try:
    astrid.invoke("some.executor", kind="executor", out="/tmp/out")
except astrid.CapabilityInvocationError as e:
    original = e.__cause__  # The exception raised by the runner
```

### Event Observation

`read_events()` returns a verified, read-only snapshot of a completed run's
event stream. `subscribe_events()` yields events from an in-progress run as
they are appended.

```python
import astrid

# Offline inspection of a completed run
events = astrid.read_events(
    "my-project",
    "my-run-id",
    projects_root="/tmp/astrid-projects",
    verify=True,
)
for event in events:
    print(event.kind, event.timestamp)

# Live observation of an in-progress run
for event in astrid.subscribe_events(
    "my-project",
    "my-run-id",
    projects_root="/tmp/astrid-projects",
    follow=True,
    poll_interval=0.5,
):
    print(f"[{event.kind}] {event.payload.get('command', '')}")
```

Each event is an `EventStreamRecord` with fields:

| Field | Type | Description |
|---|---|---|
| `source` | `str` | `"task"` or `"audit"` |
| `line` | `int` | One-indexed line number in the event log |
| `timestamp` | `str \| None` | ISO-8601 timestamp from the event |
| `kind` | `str \| None` | Event kind (`"run_started"`, `"step_dispatched"`, `"run_completed"`, etc.) |
| `hash` | `str \| None` | SHA-256 hash for chain verification |
| `payload` | `dict[str, Any]` | The raw event dict from the JSONL file |

When `verify=True` (the default), both functions validate the hash chain
before returning or yielding. A broken chain raises `CapabilityEventLogError`.
An invalid project slug raises `CapabilityPreconditionError`.

`subscribe_events()` accepts two additional keyword arguments:

- `follow: bool = False` — when `True`, the generator polls for new events
  instead of exiting after consuming the current file.
- `poll_interval: float = 0.1` — seconds between polls when following.
- `idle_polls: int | None = None` — maximum consecutive empty polls before
  the generator exits. `None` means block indefinitely.

## DTO Reference

### `Capability` vs `CapabilityHandle`

| Concept | Purpose | Source |
|---|---|---|
| `Capability` | Public inspectable DTO with schema, definition, defaults, inputs, outputs | Built by the SDK from registry definitions |
| `CapabilityHandle` | Lightweight identity card shared across all three registry types | Adapted from executor/orchestrator/element schemas by `to_capability_handle()` |

`Capability` carries the full resolved view: `id`, `capability_type`,
`native_kind`, typed `Port`/`Output` tuples, JSON-safe `schema` and
`definition` mappings, `defaults` (populated for elements, empty for
executors/orchestrators), and an embedded `handle` of type `CapabilityHandle`.

`CapabilityHandle` is the lower-level identity object that the registry
adapters produce. It carries `canonical_id`, `local_id`, `pack_id`, `kind`,
`name`, `version`, `provenance`, `safety`, `aliases`, `deprecated` status,
`inputs`, `outputs`, and metadata fields (`description`, `keywords`,
`category`, `status`, `visibility`).

Rule of thumb: use `Capability` for capability-level operations (discovery,
inspection, invocation). Reach into `handle` only when you need alias records,
provenance detail, or the unqualified `local_id`.

### `capability_type` vs `native_kind`

| Field | Meaning | Values |
|---|---|---|
| `capability_type` | Which registry and runtime class | `"executor"`, `"orchestrator"`, `"element"` |
| `native_kind` | The kind within that registry | Executors: `"built_in"`, `"external"`; Elements: `"effects"`, `"animations"`, `"transitions"`; Orchestrators: supply-side kind |

`capability_type` drives routing (`invoke()` dispatches to executor or
orchestrator runners based on it; elements are rejected). `native_kind` is
informational — it reflects the underlying manifest field and is surfaced
unchanged on `InvocationResult`.

### Elements: Discoverability and Non-Invokability

Elements are first-class in `discover()` and `get_capability()`. They expose
full schema inspection through `Capability` — including `schema`, `defaults`,
and `definition` mappings.

Element discovery honors theme overlays. When `active_theme` is provided
during `discover()` or `get_capability()`, the element registry includes
theme-specific element definitions. Pass `include_missing_roots=True` to
include element roots not yet installed locally.

Element lookup accepts three forms:
- Canonical `<kind>/<id>`: `"effects/text-card"`
- Explicit kind with bare id: `get_capability("text-card", kind="element", element_kind="effects")`
- Kindless canonical: `get_capability("effects/text-card")` (no `kind` argument)

Elements are **not invokable**. Calling `invoke()` with `kind="element"` raises
`UnsupportedCapabilityError`. Use invocation only for executors and
orchestrators.

### `DiscoveryResult`

```python
@dataclass(frozen=True)
class DiscoveryResult:
    executors: tuple[Capability, ...]    # All discovered executor capabilities
    orchestrators: tuple[Capability, ...]  # All discovered orchestrator capabilities
    elements: tuple[Capability, ...]     # All discovered element capabilities
    capabilities: tuple[Capability, ...] # Flat concatenation of all three
```

The `capabilities` tuple is deterministic: all executors, then all
orchestrators, then all elements, each in registry order.

### `InvocationResult`

```python
@dataclass(frozen=True)
class InvocationResult:
    capability_id: str
    capability_type: Literal["executor", "orchestrator", "element"]
    native_kind: str
    ok: bool
    error: Mapping[str, Any] | None
    raw_result: Mapping[str, Any]
```

`raw_result` is a JSON-safe normalization of the runner's return value. For
executors it carries `command`, `cwd`, `env`, `payload`, `returncode`,
`dry_run`, `skipped`, `skipped_reason`, `missing_binaries`. For orchestrators
it is the `to_dict()` serialization of the orchestrator result. Path objects
(`Path`) and `ExecError` instances are recursively converted to strings and
dicts. Dataclasses are converted via their `to_dict()` method.

`error` is a JSON-safe mapping derived from the result's `ExecError`, or
`None` on success. `ok` is `True` when `error` is `None`.

## Stability Tiers

The SDK follows a three-tier stability model.

### Tier 1 — Stable (semver-guarded)

These names and their function signatures will not break without a major
version bump. Breaking changes require a deprecation cycle.

| Surface | Details |
|---|---|
| `discover()` | Signature and return type (`DiscoveryResult`) |
| `get_capability()` | Signature and return type (`Capability`) |
| `invoke()` | Signature and return type (`InvocationResult`) |
| Exception classes | `AstridSDKError`, `CapabilityNotFoundError`, `CapabilityAmbiguousError`, `UnsupportedCapabilityError`, `CapabilityInvocationError` — all names and their position in the hierarchy |
| `Capability` | Top-level fields: `id`, `capability_type`, `native_kind`, `handle`, `inputs`, `outputs`, `schema`, `defaults`, `definition` |
| `CapabilityHandle` | Existence as a field of `Capability` and its own exported name |
| `DiscoveryResult` | Top-level fields: `executors`, `orchestrators`, `elements`, `capabilities` |
| `InvocationResult` | Top-level fields: `capability_id`, `capability_type`, `native_kind`, `ok`, `error`, `raw_result` |
| `read_events()` | Signature and return type (`tuple[EventStreamRecord, ...]`) |
| `subscribe_events()` | Signature as a generator function |
| `EventStreamRecord` | Top-level fields: `source`, `line`, `timestamp`, `kind`, `hash`, `payload` |
| `Port`, `Output`, `AliasRecord`, `Provenance`, `SafetyDeclaration`, `ExecError` | Exported names and existence as types |

### Tier 2 — Evolving (backward-compatible additions only)

New fields may be added to these surfaces in a minor version. Existing fields
will not be removed or renamed without a deprecation cycle.

| Surface | Details |
|---|---|
| `CapabilityHandle` fields | `canonical_id`, `local_id`, `pack_id`, `kind`, `name`, `version`, `provenance`, `safety`, `aliases`, `deprecated`, `description`, `keywords`, `status`, `visibility`, and others — individual fields may be added without notice but not removed |
| `Port` fields | `name`, `type`, `required`, `description`, `default`, `placeholder` |
| `Output` fields | `name`, `type`, `mode`, `description`, `placeholder`, `path_template`, `extension` |
| `AliasRecord` fields | `alias`, `canonical_id`, `deprecated`, `deprecation_message`, `source_pack_id` |
| `ExecError` fields | `code`, `type`, `message`, `recovery` |
| `Provenance` fields | `source`, `pack_id`, `manifest_path`, `content_root`, `resolved_alias`, `forked_from`, `upstream_version`, `compatibility_token` |
| Function keyword parameters | New keyword-only parameters may be added to `discover()`, `get_capability()`, and `invoke()` |
| `to_dict()` on all DTOs | The method exists and returns a JSON-safe `dict`; specific keys may grow |

### Tier 3 — Fluid (no stability guarantee)

These are serialized representations whose shape may change in any release
without notice. External code should treat them as opaque payloads and not
depend on specific key names, nesting, or value types.

| Surface | Details |
|---|---|
| `Capability.schema` | The schema mapping's internal key names, nesting structure, and value types reflect the executor/orchestrator/element definition schema and may evolve |
| `Capability.definition` | Same as `schema` for executors/orchestrators; for elements it is the serialized `to_dict()` of the element definition — subject to change |
| `Capability.defaults` | The defaults mapping; populated for elements, empty for executors/orchestrators. Key names and types evolve with the element schema |
| `InvocationResult.raw_result` | The normalized runner result mapping. Specific keys (`command`, `cwd`, `env`, `payload`, etc.) are added or reshaped as runner output models evolve |
| `InvocationResult.error` | The JSON-safe `ExecError` mapping; keys follow `ExecError` fields (currently `code`, `type`, `message`, `recovery`). Key set may grow but not shrink in tier-2 fashion |
| `DiscoveryResult.to_dict()` output | The serialized shape of nested capability DTOs — stable only to the extent that `json.dumps(result.to_dict())` does not raise |

## Exception Hierarchy

```
RuntimeError
 └── AstridSDKError
      ├── CapabilityNotFoundError
      ├── CapabilityAmbiguousError
      ├── UnsupportedCapabilityError
      └── CapabilityInvocationError
```

All SDK exceptions are public and importable from `astrid`. `CapabilityInvocationError`
preserves the original runner exception as `__cause__`.

## Lazy Loading

`import astrid` does not eagerly load internal registry or runner modules.
The SDK module (`astrid.sdk`) is loaded on first attribute access. Registry
and runner imports happen inside the `discover()`, `get_capability()`, and
`invoke()` call sites. This keeps the import boundary lightweight and allows
tooling to inspect the public surface without pulling in execution machinery.

## Theme Overlay Behavior for Elements

When `active_theme` is provided to `discover()` or `get_capability()`, the
element registry includes theme-specific overrides. Elements defined in the
base registry may be shadowed or extended by theme-aware definitions. The
theme overlay is resolved at registry load time and reflected in the returned
`Capability` DTOs — the `schema`, `defaults`, and `definition` mappings carry
the resolved post-overlay values.

Pass `include_missing_roots=True` to include element roots that are declared
but not yet installed. This is useful for discovery in setup/install workflows
where the operator needs to see what elements are available before they are
locally fetched.
