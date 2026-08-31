# Build Your First Agentic UX

This tutorial walks you through the complete Astrid SDK loop —
**discover → inspect → invoke → read-events** — using only the public
`astrid` package. By the end you will have a runnable script that
discovers capabilities, inspects schemas, dry-runs an executor, and
observes a verified event stream.

The preview portion of this tutorial is mirrored by the checked-in example at
[`examples/agentic_ux/agentic_ux.py`](../../examples/agentic_ux/agentic_ux.py).
Every API call shown here uses the public SDK surface — no internal
imports, no private modules.

## Prerequisites

- Python 3.11+
- An editable install of Astrid from a local checkout:

```bash
cd /path/to/Astrid
pip install -e .
```

- The dry-run preview requires no API keys, network access, or hosted services.
  Live invocation and event observation require an explicitly configured
  Banodoco workspace runtime.

## Step 1 — Import the SDK

```python
import os
import astrid

# The SDK's invoke() path for built-in executors (e.g. editorial.arrange)
# may import pack runtime modules that carry a guard against direct
# invocation.  Setting this env var tells the guard "this is a legitimate
# programmatic SDK call" and prevents a spurious SystemExit(2).
os.environ.setdefault("ASTRID_INTERNAL_INVOCATION", "1")
```

`import astrid` is lazy — it does not eagerly load registry or runner
modules.  The SDK surface is available directly from the top-level
package.

## Step 2 — Discover Capabilities

```python
discovery = astrid.discover()

print(f"Found {len(discovery.capabilities)} total capabilities")
print(f"  Executors:     {len(discovery.executors)}")
print(f"  Orchestrators: {len(discovery.orchestrators)}")
print(f"  Elements:      {len(discovery.elements)}")
```

`discover()` returns a `DiscoveryResult` with typed groupings
(`executors`, `orchestrators`, `elements`) and a flat
`capabilities` tuple. Discovery reads repository packs and any explicitly
supplied extra roots — no user-wide installed-pack overlay.
packs are included.

## Step 3 — Inspect a Capability

Choose one capability to inspect.  This tutorial uses
`editorial.arrange`, a built-in executor with a well-defined schema:

```python
capability = astrid.get_capability(
    "editorial.arrange",
    kind="executor",
)

print(f"ID:              {capability.id}")
print(f"Capability type: {capability.capability_type}")
print(f"Native kind:     {capability.native_kind}")

print("\nInputs:")
for port in capability.inputs:
    required = " (required)" if port.required else ""
    print(f"  {port.name}: {port.type}{required}")

print("\nOutputs:")
for output in capability.outputs:
    print(f"  {output.name}: {output.type}")
```

`get_capability()` returns a `Capability` DTO with typed `Port`
inputs (name, type, required flag, description, default) and `Output`
definitions (name, type, mode, path_template).  The `schema` and
`definition` mappings are available for JSON-safe serialization.

### Error handling: not-found and ambiguous lookups

```python
from astrid import CapabilityNotFoundError, CapabilityAmbiguousError

try:
    cap = astrid.get_capability("missing.capability", kind="executor")
except CapabilityNotFoundError as e:
    print(f"Not found: {e}")

try:
    cap = astrid.get_capability("fade", kind="element")
except CapabilityAmbiguousError as e:
    print(f"Multiple matches — qualify with element_kind=: {e}")
```

All SDK exceptions inherit from `AstridSDKError`.  Catch the base
class for general handling or specific subclasses for precise recovery.

## Step 4 — Dry-Run Invocation

A dry-run validates the request and routes through the registry
without executing side effects.  It requires no API keys, no network,
and no project state — it is safe for CI.

```python
from pathlib import Path
import tempfile

with tempfile.TemporaryDirectory(prefix="astrid-tutorial-") as tmp_out:
    result = astrid.invoke(
        "editorial.arrange",
        kind="executor",
        out=Path(tmp_out),
        inputs={
            "brief": "example brief for the tutorial",
            "pool": "default",
            "theme": "default",
            "target_duration": 60,
        },
        dry_run=True,
        verbose=False,
    )

print(f"ok:       {result.ok}")
print(f"dry_run:  {result.raw_result.get('dry_run')}")
print(f"command:  {result.raw_result.get('command')}")
print(f"manifest: {result.manifest_path}")
```

`invoke(dry_run=True)` returns an `InvocationResult` with `ok`,
`error`, `capability_id`, `capability_type`, `native_kind`,
optional `manifest_path`, and `raw_result`.  The `raw_result`
mapping carries the normalized command, working directory,
environment, and dry-run metadata.

### Error handling: missing inputs and invocation failures

```python
from astrid import (
    CapabilityInvocationError,
    CapabilityMissingInputError,
    UnsupportedCapabilityError,
)

# Missing a required input
try:
    astrid.invoke("editorial.arrange", kind="executor", out=Path("/tmp/out"))
except CapabilityMissingInputError as e:
    print(f"Missing input: {e}")

# Elements cannot be invoked
try:
    astrid.invoke("effects/text-card", kind="element")
except UnsupportedCapabilityError as e:
    print(f"Cannot invoke element: {e}")

# Runner exceptions are preserved
try:
    astrid.invoke("some.executor", kind="executor", out=Path("/tmp/out"))
except CapabilityInvocationError as e:
    print(f"Invocation error: {e}")
    original = e.__cause__  # The exception raised by the runner
```

## Step 5 — Observe runtime state

The workspace runtime owns event storage, ordering, integrity, and recovery.
Open an explicit runtime client and use its generated resources; Astrid does
not read event files or local databases.

```python
from astrid import AstridClient

PROJECT_SLUG = "demo-agentic-ux"
RUN_ID = "demo-run-001"
with AstridClient.open(endpoint=RUNTIME_ENDPOINT, credential=RUNTIME_CREDENTIAL) as client:
    events = client.runs.events(PROJECT_SLUG, RUN_ID)

for event in events.data:
    print(f"[{event['event_type']}] {event['occurred_at']}")
```

For in-progress runs, poll the same runtime resource (or use the runtime's
subscription facility). Runtime integrity and replay checks happen at the
service boundary; failures are returned as typed runtime errors. The endpoint
and credential must be supplied explicitly or through the documented
`BANODOCO_RUNTIME_*` configuration.

## Step 6 — Run the Complete Example

The checked-in preview example at
[`examples/agentic_ux/agentic_ux.py`](../../examples/agentic_ux/agentic_ux.py)
bundles Steps 1–4 into a single argparse-driven script. It runs the
no-side-effect **discover → inspect → dry-run invoke** loop against
`editorial.arrange` and prints a deterministic JSON summary with three keys
(`discovery`, `inspection`, `invocation`) to stdout. It does not fabricate a
local project or event file. For live execution and event observation, open
an explicit `AstridClient` against the workspace runtime and call
`client.invoke_result(...)` followed by `client.runs.events(project, run_id)`.

```bash
python3 examples/agentic_ux/agentic_ux.py \
    --capability-id editorial.arrange
```

## Dry-Run vs Live-Run

| Mode | `dry_run=True` | Live run (`dry_run=False`) |
|---|---|---|
| **Side effects** | None — validates only | Executes the capability |
| **API keys** | Not required | May be required (depends on capability) |
| **Network** | Not required | May be required (depends on capability) |
| **CI-safe** | Yes | No (requires environment) |
| **Returns** | `InvocationResult` with `command` metadata | `InvocationResult` with `returncode` and full output |

**When to dry-run**: schema exploration, CI validation, pre-flight
checks, capability documentation generation.

**When to live-run**: actual task execution, pipeline automation,
user-facing workflows.

## Security and Trust Disclosures

- **Subprocess execution**: `astrid.invoke()` launches subprocesses with your
  user permissions.  Only invoke capabilities from packs you trust.
  Check `capability.handle.safety` for the `SafetyDeclaration` (network,
  API keys, external binaries, project-file access).
- **Runtime event access**: `client.runs.events(...)` is a read-only generated
  client call to the workspace runtime; no local event file, database, or cache
  is consulted.
- **Capability provenance**: inspect `capability.handle.provenance`
  (`.source`, `.pack_id`, `.manifest_path`) before invoking in production.

## Next Steps

- Read [SDK Reference](../reference/sdk.md) for the full DTO and exception catalog.
- Explore [Creating Packs](../packs/creating-packs.md) to build your own
  executors and orchestrators.
  execution backends.
- Browse [Discovery for Agents](discovery-for-agents.md) to understand
  how AI agents consume the capability registry.
