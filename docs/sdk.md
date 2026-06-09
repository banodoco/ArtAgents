# Astrid Python SDK

The `astrid` package exposes a public Python SDK for capability discovery,
schema inspection, generation, and invocation. Import the top-level package —
the SDK surface is available directly from `import astrid`.

> **Compatibility policy**: This document is a user-facing walkthrough. The
> normative v1 compatibility contract lives in
> [docs/platform-contract.md](platform-contract.md). That file defines the
> supported export list, SemVer rules, deprecation window, DTO stability tiers,
> manifest schema contract, and disclosure-only trust block. When this doc and
> `platform-contract.md` differ, the platform contract wins.

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

# Generation
gen_result = astrid.generate(
    "editorial.arrange",
    include_installed=False,
    prompt="Generate a short video from these clips.",
    inputs={"clips": ["clip1.mp4", "clip2.mp4"]},
)
print(gen_result)
```

> **Tutorial**: For a step-by-step walkthrough building your first Astrid
> agentic UX, see [docs/build-your-first-agentic-ux.md](build-your-first-agentic-ux.md).

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

See [platform-contract.md](platform-contract.md).

### `manifest_path` Fallback Rules

`manifest_path` is an additive optional pointer to a universal
`manifest.json` emitted by the invoked capability. When present it is an
absolute path. The SDK derives it from the normalized payload when the payload
already exposes a universal manifest pointer, otherwise it falls back to
discovering `{out}/manifest.json`.

The discovery follows a two-step fallback:

1. **Payload preference**: If the executor's stdout `payload` includes a
   `manifest_path` or `manifest` key pointing to a file named `manifest.json`,
   that path is used directly.
2. **Output-directory fallback**: Otherwise, the SDK checks whether
   `{out}/manifest.json` exists on disk and returns its absolute path.

When neither source yields a `manifest.json` file, `manifest_path` is `None`.

Refer to the [output/result contract](output-result-contract.md) for the
universal manifest schema, the kind vocabulary, file and directory hashing
semantics, partial-output optionality, and domain-manifest coexistence rules.

```python
import astrid

result = astrid.invoke("editorial.transcribe", kind="executor", out="/tmp/transcribe-out")
if result.manifest_path:
    import json
    with open(result.manifest_path) as fh:
        manifest = json.load(fh)
    print(f"kind={manifest['kind']}, outputs={len(manifest['outputs'])}")
```

## Stability Tiers

See [platform-contract.md](platform-contract.md).

## Exception Hierarchy

```
RuntimeError
 └── AstridSDKError
      ├── CapabilityNotFoundError
      ├── CapabilityAmbiguousError
      ├── UnsupportedCapabilityError
      ├── CapabilityInvocationError
      ├── CapabilityValidationError
      │    └── CapabilityMissingInputError
      ├── CapabilityPreconditionError
      ├── CapabilityRuntimeError
      ├── CapabilityLeaseError
      └── CapabilityEventLogError
```

All 11 SDK exceptions are public and importable from `astrid`.
`CapabilityMissingInputError` is a subclass of `CapabilityValidationError` and
carries the names of missing required inputs. `CapabilityInvocationError`
preserves the original runner exception as `__cause__`.
`CapabilityEventLogError` is raised by `read_events()` when the hash chain is
broken; `CapabilityPreconditionError` is raised when a project slug or
prerequisite check fails. `CapabilityLeaseError` is raised when the writer
lease cannot be acquired. `CapabilityRuntimeError` signals an unexpected
failure during SDK operations.

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
