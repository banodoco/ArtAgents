# Build Your First Agentic UX

This tutorial walks you through the complete Astrid SDK loop —
**discover → inspect → invoke → read-events** — using only the public
`astrid` package. By the end you will have a runnable script that
discovers capabilities, inspects schemas, dry-runs an executor, and
observes a verified event stream.

The code in this tutorial mirrors the checked-in example at
[`examples/agentic_ux/agentic_ux.py`](../examples/agentic_ux/agentic_ux.py).
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
discovery = astrid.discover(include_installed=False)

print(f"Found {len(discovery.capabilities)} total capabilities")
print(f"  Executors:     {len(discovery.executors)}")
print(f"  Orchestrators: {len(discovery.orchestrators)}")
print(f"  Elements:      {len(discovery.elements)}")
```

`discover()` returns a `DiscoveryResult` with typed groupings
(`executors`, `orchestrators`, `elements`) and a flat
`capabilities` tuple.  Set `include_installed=False` to limit
discovery to the repository packs — no system-wide or pip-installed
packs are included.

## Step 3 — Inspect a Capability

Choose one capability to inspect.  This tutorial uses
`editorial.arrange`, a built-in executor with a well-defined schema:

```python
capability = astrid.get_capability(
    "editorial.arrange",
    kind="executor",
    include_installed=False,
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
        include_installed=False,
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
```

`invoke(dry_run=True)` returns an `InvocationResult` with `ok`,
`error`, `capability_id`, `capability_type`, `native_kind`, and
`raw_result`.  The `raw_result` mapping carries the normalized
command, working directory, environment, and dry-run metadata.

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
- `source` — `"task"` or `"audit"`
- `line` — one-indexed line number in the event log
- `timestamp` — ISO-8601 timestamp string (or `None`)
- `kind` — event kind string (e.g. `"run_started"`, `"step_dispatched"`, `"run_completed"`)
- `hash` — SHA-256 hash for chain verification (or `None`)
- `payload` — the raw event dict from the JSONL file

When `verify=True` (the default), `read_events()` validates the hash
chain before returning.  A broken chain raises `CapabilityEventLogError`.

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

## Step 6 — Assemble the Complete Script

Putting it all together — this is the full script matching the
checked-in example:

```python
#!/usr/bin/env python3
"""External example: full Astrid SDK loop (discover → inspect → invoke → read-events)."""

import argparse, json, os, shutil, sys, tempfile
from pathlib import Path

os.environ.setdefault("ASTRID_INTERNAL_INVOCATION", "1")
import astrid

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
PROJECT_SLUG = "demo-agentic-ux"
RUN_ID = "demo-run-001"

def main():
    parser = argparse.ArgumentParser(
        description="Astrid SDK external example"
    )
    parser.add_argument("--projects-root", required=True, type=Path,
                        help="Base directory for temporary project structure")
    parser.add_argument("--capability-id", default="editorial.arrange",
                        help="Qualified capability ID (default: %(default)s)")
    args = parser.parse_args()

    # 1. Discover
    discovery = astrid.discover(include_installed=False)

    # 2. Inspect
    capability = astrid.get_capability(
        args.capability_id, kind="executor", include_installed=False,
    )

    # 3. Dry-run invoke
    with tempfile.TemporaryDirectory(prefix="astrid-agentic-ux-") as tmp_out:
        invocation = astrid.invoke(
            args.capability_id,
            kind="executor",
            include_installed=False,
            out=Path(tmp_out),
            inputs={
                "brief": "example brief for agentic UX demo",
                "pool": "default",
                "theme": "default",
                "target_duration": 60,
            },
            dry_run=True,
            verbose=False,
        )

    # 4. Read events from the committed golden fixture
    run_dir = args.projects_root / PROJECT_SLUG / "runs" / RUN_ID
    run_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(FIXTURE_DIR / "golden_events.jsonl", run_dir / "events.jsonl")

    events = astrid.read_events(
        PROJECT_SLUG, RUN_ID,
        projects_root=args.projects_root,
        verify=True,
    )

    # 5. Print deterministic JSON summary
    summary = {
        "discovery": {
            "executor_count": len(discovery.executors),
            "orchestrator_count": len(discovery.orchestrators),
            "element_count": len(discovery.elements),
            "total_capabilities": len(discovery.capabilities),
        },
        "inspection": {
            "id": capability.id,
            "capability_type": capability.capability_type,
            "native_kind": capability.native_kind,
            "inputs": [{"name": p.name, "type": p.type, "required": p.required}
                       for p in capability.inputs],
            "outputs": [{"name": o.name, "type": o.type}
                        for o in capability.outputs],
        },
        "invocation": {
            "capability_id": invocation.capability_id,
            "capability_type": invocation.capability_type,
            "native_kind": invocation.native_kind,
            "ok": invocation.ok,
            "dry_run": invocation.raw_result.get("dry_run", False),
        },
        "events": {
            "count": len(events),
            "kinds": [e.kind for e in events],
        },
    }
    json.dump(summary, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")

if __name__ == "__main__":
    main()
```

Save this as `my_agentic_ux.py` (or copy the example from
[`examples/agentic_ux/agentic_ux.py`](../examples/agentic_ux/agentic_ux.py))
and run it:

```bash
python my_agentic_ux.py \
    --projects-root /tmp/astrid-demo-projects \
    --capability-id editorial.arrange
```

The output is a deterministic JSON object with four top-level keys:
`discovery`, `inspection`, `invocation`, and `events`.

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

## Error Handling Quick Reference

| When … | Catch … |
|---|---|
| Capability ID not found | `CapabilityNotFoundError` |
| Bare ID matches multiple capabilities | `CapabilityAmbiguousError` |
| Required input is missing | `CapabilityMissingInputError` |
| Execution mode not supported | `CapabilityPreconditionError` |
| Invocation fails at runtime | `CapabilityInvocationError` |
| Event log is corrupt or unreadable | `CapabilityEventLogError` |
| Element is passed to `invoke()` | `UnsupportedCapabilityError` |
| Unknown SDK failure | `AstridSDKError` (base class) |

All exceptions are importable from `astrid`.  `CapabilityInvocationError`
preserves the original runner exception as `__cause__`.

## Security and Trust Disclosures

### Local subprocess execution

`astrid.invoke()` may launch subprocesses on your machine.  By
default, executors run with the same user and permissions as the
calling process.  **Only invoke capabilities from packs you trust.**
The `SafetyDeclaration` attached to every capability (accessible via
`capability.handle.safety`) declares whether the capability touches
the network, uses external binaries outside the project tree, requires
API keys, or accesses project files.

### Project-file access

`astrid.read_events()` and `astrid.subscribe_events()` read from the
local filesystem under the `projects_root` directory you provide.
These functions are **read-only** — they never modify event logs or
project state.  However, they traverse the filesystem structure you
point them at.  Only pass `projects_root` paths you control.

### Deterministic fixtures in examples

The golden events fixture (`examples/agentic_ux/fixtures/golden_events.jsonl`)
contains three pre-computed, hash-chained records with fixed
timestamps.  It is safe to commit and use in CI — it does not contain
API keys, machine-specific paths, or secrets.  The hashes are
deterministic and structurally valid; they pass `verify_chain` but
are not cryptographically bound to any real run.

### Capability provenance

Every capability carries a `Provenance` record (accessible via
`capability.handle.provenance`) that identifies the pack and manifest
the capability was loaded from.  Before invoking a capability in
production, inspect its provenance to confirm it originates from a
source you trust:

```python
cap = astrid.get_capability("editorial.arrange", kind="executor")
print(cap.handle.provenance.source)       # e.g. "builtin"
print(cap.handle.provenance.pack_id)      # e.g. "editorial"
print(cap.handle.provenance.manifest_path) # absolute path to executor.yaml
```

## Next Steps

- Read [SDK Reference](sdk.md) for the full DTO and exception catalog.
- Explore [Creating Packs](creating-packs.md) to build your own
  executors and orchestrators.
- See [Adapter Packs](adapter-packs.md) for local, remote, and manual
  execution backends.
- Browse [Discovery for Agents](discovery-for-agents.md) to understand
  how AI agents consume the capability registry.
