# Build Your First Agentic UX

This tutorial walks you through the complete Astrid SDK loop —
**discover → inspect → invoke → read-events** — using only the public
`astrid` package. By the end you will have a runnable script that
discovers capabilities, inspects schemas, dry-runs an executor, and
observes a verified event stream.

The code in this tutorial mirrors the checked-in example at
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

- No API keys, network access, or hosted services are required.
  Everything runs locally.

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

## Step 5 — Read Events from a Run

Astrid records every task run as a hash-chained event log
(`events.jsonl`).  The SDK provides `read_events()` for offline
inspection of completed runs and `subscribe_events()` for live
observation of in-progress runs.

This tutorial uses a committed golden fixture to demonstrate
`read_events()` without a live executor run (the fixture was recorded
from a known-good `editorial.arrange` execution):

```python
# Copy the golden fixture into a temporary project layout
import shutil

PROJECT_SLUG = "demo-agentic-ux"
RUN_ID = "demo-run-001"
projects_root = Path("/tmp/astrid-demo-projects")

run_dir = projects_root / PROJECT_SLUG / "runs" / RUN_ID
run_dir.mkdir(parents=True, exist_ok=True)
shutil.copy2("examples/agentic_ux/fixtures/golden_events.jsonl",
             run_dir / "events.jsonl")

# Read and verify the event stream
events = astrid.read_events(
    PROJECT_SLUG,
    RUN_ID,
    projects_root=projects_root,
    verify=True,
)

print(f"Event count: {len(events)}")
for event in events:
    print(f"  [{event.source}:{event.line}] {event.kind} @ {event.timestamp}")
```

Each event is an `EventStreamRecord` with fields:
- `source` — `"task"`, `"audit"`, or `"kernel"` when the canonical SQLite run stream is used because the optional filesystem projection is absent
- `line` — one-indexed line number in the event log
- `timestamp` — ISO-8601 timestamp string (or `None`)
- `kind` — event kind string (e.g. `"run_started"`, `"step_dispatched"`, `"run_completed"`)
- `hash` — SHA-256 hash for chain verification (or `None`)
- `payload` — the raw JSONL event, or canonical kernel fields including the event id, stream sequence, domain data, and integrity hashes

When `verify=True` (the default), `read_events()` validates the hash
chain before returning. For restored runs this verifies the canonical SQLite
stream head, sequence, previous-hash links, and recomputed event hashes. A
broken or mismatched chain raises `CapabilityEventLogError`.

### Live event observation

For in-progress runs, use `subscribe_events()` with `follow=True`:

```python
for event in astrid.subscribe_events(
    PROJECT_SLUG,
    RUN_ID,
    projects_root=projects_root,
    follow=True,
    poll_interval=0.5,
):
    print(f"[{event.kind}] {event.payload.get('command', '')}")
```

The generator yields events as they are appended.  It polls every
`poll_interval` seconds and stops after `idle_polls` consecutive empty
polls (default: no limit — the generator blocks until you break).

### Event stream errors

```python
from astrid import CapabilityPreconditionError, CapabilityEventLogError

# Invalid project slug
try:
    astrid.read_events("bad/slug", RUN_ID, projects_root=projects_root)
except CapabilityPreconditionError as e:
    print(f"Precondition: {e}")

# Corrupt event log
try:
    astrid.read_events(PROJECT_SLUG, RUN_ID, projects_root=projects_root,
                       verify=True)
except CapabilityEventLogError as e:
    print(f"Event log error: {e}")
```

## Step 6 — Run the Complete Example

The checked-in example at
[`examples/agentic_ux/agentic_ux.py`](../../examples/agentic_ux/agentic_ux.py)
bundles Steps 1–5 into a single argparse-driven script.  It runs
the full **discover → inspect → invoke → read-events** loop against
`editorial.arrange`, uses the golden events fixture, and prints a
deterministic JSON summary with four keys (`discovery`, `inspection`,
`invocation`, `events`) to stdout.

```bash
python3 examples/agentic_ux/agentic_ux.py \
    --projects-root /tmp/astrid-demo-projects \
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
- **Read-only event access**: `read_events()` and `subscribe_events()`
  never modify event logs or project state, but they traverse the
  `projects_root` you provide — only pass paths you control.
- **Golden fixture**: `examples/agentic_ux/fixtures/golden_events.jsonl`
  contains hash-chained records with fixed timestamps.  No API keys,
  machine-specific paths, or secrets — safe for CI.
- **Capability provenance**: inspect `capability.handle.provenance`
  (`.source`, `.pack_id`, `.manifest_path`) before invoking in production.

## Next Steps

- Read [SDK Reference](../reference/sdk.md) for the full DTO and exception catalog.
- Explore [Creating Packs](../packs/creating-packs.md) to build your own
  executors and orchestrators.
  execution backends.
- Browse [Discovery for Agents](discovery-for-agents.md) to understand
  how AI agents consume the capability registry.
