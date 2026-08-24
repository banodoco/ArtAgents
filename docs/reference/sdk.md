# Astrid Python SDK

The `astrid` package exposes a public Python SDK for capability discovery,
schema inspection, generation, and invocation. Import the top-level package —
the SDK surface is available directly from `import astrid`.

> **Compatibility policy**: This document is a user-facing walkthrough. The
> normative v1 compatibility contract lives in
> [docs/platform-contract.md](../contracts/platform-contract.md). That file defines the
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
    "iteration.experiment_review",
    kind="executor",
    include_installed=False,
    out="/tmp/review-out",
    project="demo",
    inputs={"review": "experiments/prompt-brevity/review.json"},
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
> agentic UX, see [docs/build-your-first-agentic-ux.md](../guides/build-your-first-agentic-ux.md).

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

`include_installed=False` scopes discovery to the in-tree packs. Externally
installed packs load with the registry by default. Installed/external pack
roots are fault-tolerant: a pack whose manifests fail validation is skipped
with a logged warning instead of failing the whole discovery call, so
scripted and agent workflows keep working when one external pack is broken.

`kind="executor"` (or `"orchestrator"` / `"element"`) filters the returned
inventory to that capability type — `capabilities` then carries only those
entries; an invalid kind raises `CapabilityValidationError`.

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
    "iteration.experiment_review",
    kind="executor",
    include_installed=False,
    out=Path("./out/review-test"),
    project="demo",
    inputs={"review": "experiments/prompt-brevity/review.json"},
    dry_run=True,
)
print(result.ok)                     # True if no validation errors
print(result.raw_result["dry_run"])  # True
print(result.raw_result["command"])
```

`kind` is required (`"executor"` or `"orchestrator"`), and every executor
run belongs to exactly one project: pass `project=<slug>` (the slug or id
of an existing project).

### Regular Invocation

A real executor run addressed with `project=` executes inside a private,
attempt-owned staging directory and publishes successful outputs to managed
content-addressed media. The staging directory is removed after completion;
durable locators are returned in `result.outputs`. Do **not** pass `out=`
together with `project=` (the two are mutually exclusive):

```python
import astrid

result = astrid.invoke(
    "iteration.experiment_review",
    kind="executor",
    include_installed=False,
    project="demo",
    inputs={"review": "experiments/prompt-brevity/review.json"},
)
print(result.ok)        # True on success
print(result.run_id)    # durable kernel run identity
print(result.run_root)  # None for kernel-managed invocations; staging is private
print(result.outputs)   # durable managed-media artifacts/locators
print(result.error)     # error mapping if not ok
```

Orchestrator invocations take the same arguments minus `out` (their outputs
also land in the project run tree); `brief` and `orchestrator_args` are
orchestrator-specific options.

For maker-facing loops that need one JSON-safe branch for both pre-admission
and runtime failures, use `invoke_result`. It preserves the typed exception
API of `invoke` while serializing a validation/precondition failure into the
same `InvocationResult` error mapping, without admitting a run:

```python
import astrid.sdk as sdk

result = sdk.invoke_result(
    "generation.generate_image",
    kind="executor",
    project="demo",
    inputs={
        "model": "not-a-real-model",
        "mode": "text-to-image",
        "execution": "cloud",
        "prompt": "a blue square",
    },
)
print(result.ok)                      # False
print(result.error["sdk_category"])  # validation
print(result.to_dict())               # JSON-safe structured result
```

`astrid.sdk.invoke` and the typed `astrid.generate.*` facades intentionally keep
raising `AstridSDKError` subclasses for code that wants precise recovery
branches. `invoke_result` is the canonical agent-loop boundary when catching
and serializing those typed failures is preferable.

### Typed Error Handling

All SDK errors inherit from `AstridSDKError`. Catch the base class for general
handling or specific subclasses for precise recovery.

```python
import astrid

# Not-found
try:
    astrid.get_capability("missing.capability", kind="executor", include_installed=False)
except astrid.CapabilityNotFoundError as e:
    print(f"Not found: {e}")

# Ambiguous bare lookup
try:
    astrid.get_capability("fade", kind="element", include_installed=False)
except astrid.CapabilityAmbiguousError as e:
    print(f"Multiple matches: {e}")
    # e carries candidate list in the message

# Element invocation is rejected
try:
    astrid.invoke("effects/text-card", kind="element", include_installed=False)
except astrid.UnsupportedCapabilityError as e:
    print(f"Cannot invoke element: {e}")

# Executor runs require a project (validation happens before any side effect)
try:
    astrid.invoke("iteration.experiment_review", kind="executor", include_installed=False)
except astrid.CapabilityValidationError as e:
    print(f"Project required: {e}")

# Runner exceptions are preserved as __cause__
try:
    astrid.invoke("some.executor", kind="executor", out="/tmp/out", project="demo")
except astrid.CapabilityInvocationError as e:
    original = e.__cause__  # The exception raised by the runner
```

### Event Observation

`read_events()` returns a verified, read-only snapshot of a completed run's
event stream. A filesystem `events.jsonl` projection is preferred when it is
present. If that optional local-process projection is absent — for example
after a portable backup/restore — the SDK reads the canonical SQLite
`core.run` stream instead, so restored runs remain observable. The fallback
does not create or repair a projection. `subscribe_events()` yields the
filesystem stream for an in-progress run as it is appended.

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
| `source` | `str` | `"task"`, `"audit"`, or `"kernel"` for the canonical restored-run fallback |
| `line` | `int` | One-indexed line number in the event log |
| `timestamp` | `str \| None` | ISO-8601 timestamp from the event |
| `kind` | `str \| None` | Event kind (`"run_started"`, `"step_dispatched"`, `"run_completed"`, etc.) |
| `hash` | `str \| None` | SHA-256 hash for chain verification |
| `payload` | `dict[str, Any]` | The raw JSONL event, or the canonical kernel event fields (including `event_id`, `seq`, `data`, and integrity hashes) |

When `verify=True` (the default), the selected source is verified before
returning or yielding. Filesystem streams validate their JSONL chain; kernel
fallback streams validate the SQLite stream head, contiguous sequence, every
previous-hash link, and every recomputed event hash. A broken or mismatched
chain raises `CapabilityEventLogError`.
An invalid project slug raises `CapabilityPreconditionError`.

`subscribe_events()` accepts two additional keyword arguments:

- `follow: bool = False` — when `True`, the generator polls for new events
  instead of exiting after consuming the current file.
- `poll_interval: float = 0.1` — seconds between polls when following.
- `idle_polls: int | None = None` — maximum consecutive empty polls before
  the generator exits. `None` means block indefinitely.

## DTO Reference

See [platform-contract.md](../contracts/platform-contract.md).

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

Refer to the [output/result contract](../contracts/output-result-contract.md) for the
universal manifest schema, the kind vocabulary, file and directory hashing
semantics, partial-output optionality, and domain-manifest coexistence rules.

```python
import astrid

result = astrid.invoke(
    "iteration.experiment_review",
    kind="executor",
    include_installed=False,
    project="demo",
    inputs={"review": "experiments/prompt-brevity/review.json"},
)
if result.manifest_path:
    import json
    with open(result.manifest_path) as fh:
        manifest = json.load(fh)
    print(f"kind={manifest['kind']}, outputs={len(manifest['outputs'])}")
```

## Rendering SDK

The public rendering surface (`astrid.render`, `astrid.support`,
`astrid.renderer_main`, `astrid.RenderContext`) wraps the frozen
protocol-v1 rendering boundary described in
[render-backend-v1.md](../contracts/render-backend-v1.md). Every JSON payload
it writes is the `to_dict()` of a frozen core DTO — there are no SDK-only wire
fields and no semantics drift from the raw command/JSON backend path.

### `render(timeline_path, ...) -> Path`

Builds a `RenderRequest` from friendly arguments and dispatches through the
shared `RenderService`, returning the published output path (and writing the
provenance sidecar next to it):

```python
import astrid

out = astrid.render(
    "out/hype.timeline.json",
    assets_registry_path="out/hype.assets.json",
    backend="rendering.remotion",        # strict qualified selector
    backend_config={"rendering.remotion": {"quality": "preview"}},
    out_path="out/hype.mp4",
)
print(out)          # out/hype.mp4
# sidecar: out/hype.mp4.provenance.json
```

`selector`/`engine`/`backend` are the service's three spellings of the same
renderer selector and must not disagree. `window` accepts a `FrameWindow` or a
wire mapping, `audio` accepts `AudioOwnership` or its string value, and
`profile` accepts a `RenderProfile` or a wire mapping. `out_path` selects the
published destination; when `output_name` is omitted its basename is used.

### `support(backend, ...) -> SupportReport`

Resolves the qualified backend and returns its request-sensitive
`SupportReport` — exactly what the public backend path produces. Pass a frozen
`RenderRequest`/wire mapping or friendly path/audio/profile arguments:

```python
import astrid

report = astrid.support("acme_wave.wave", timeline_path="out/hype.timeline.json")
print(report.supported, report.features, report.alternatives)
```

### `renderer_main([...]) -> int`

The protocol-v1 command entrypoint, mirroring the raw-command backend's file
protocol exactly — this is what a manifest `command` can point at instead of a
hand-written `render.py`:

```
python -m astrid.sdk.rendering render|support --request <abs.json> --result <abs.json>
```

It reads the request JSON, dispatches through the rendering registries and the
command transport, validates the result with the core artifact validator, and
writes the frozen result shape to `--result`. Failures are written as the
frozen `RendererError` JSON shape (exit 0); `KeyboardInterrupt` and
`SystemExit` are re-raised. The selected backend is resolved from
`ASTRID_RENDER_BACKEND` (set by the transport when this runs as a manifest
command), then from the request's `backend_config` namespace — exactly one,
never from timeline shape.

### `replay` — re-run a captured failure bundle

The internal rendering CLI verb
`python3 -m astrid.core.rendering.cli replay <bundle-dir>` re-runs a captured
replay bundle's pinned command with its localized `request.json` and `inputs/`
copies in a fresh temporary workspace. It verifies the pinned
`request_digest` against the on-disk localized request, refuses manifest or
localized-input drift unless `--acknowledge-drift` is passed, refuses an
unresolvable pinned renderer, and persists the reproduced output plus its
provenance sidecar under `<bundle-dir>.replay-output/`. Bundles are produced
by `RenderService` on any failed `render`/`finalize`/`plan`/`support`
invocation (and on success when capture is explicitly enabled); they carry
the localized request, hashed inputs, redacted logs and partial result,
`support_report`, `backend_config`, source-pack/trust identity, and the
pinned digests. See the worked example in
[render-backend-v1.md](../contracts/render-backend-v1.md#the-replay-verb).

V1 is synchronous local execution only; asynchronous job scheduling, remote
render infrastructure, and layer compositing are explicitly deferred beyond
V1 and are NOT part of the V1 renderer contract.

### `RenderContext`

`RenderContext` is the per-invocation facade a third-party `render.py` author
gets for the duration of one render: workspace-validated path allocation
(`output_path`, `workspace_path`, `temp_dir`), asset descriptor resolution
(`asset_path`, `asset_url`, `resolved_registry`), a sanitized subprocess
runner (`run` with scrubbed env, bounded redacted output, hard timeout,
process-group teardown), redacted logs (`log`, `progress`), a cooperative
interruption flag (`interrupt_requested`, `raise_if_interrupted`), media
probing and hashing (`probe_media`, `sha256`), audio completion
(`complete_audio`), and named attachments (`add_attachment`, `attachments`).
It is not an OS sandbox — it enforces workspace conventions, not process
isolation — and it cleans up its temp artifacts on exit.

```python
from astrid import RenderContext
from astrid.core.rendering.contracts import RenderRequest, RenderResult

def render(workspace, request: RenderRequest) -> RenderResult:
    with RenderContext(workspace, backend="acme_wave.wave") as ctx:
        ctx.log("rendering %s" % request.output_name)
        out = ctx.output_path(request.output_name)          # workspace/outputs/<name>
        ctx.run(["vendor-tool", "--input", ctx.asset_path("hero"), "--out", out])
        media = out.read_bytes()
        ctx.add_attachment("project", media, kind="project")
        return RenderResult(
            schema_version=1,
            video={"path": "outputs/%s" % request.output_name,
                   "profile": _probe(ctx, out),
                   "sha256": ctx.sha256(out),
                   "duration_frames": 240,
                   "audio": "rendered",
                   "attachments": {a.name: a for a in ctx.attachments.values()}},
            backend_fragments={"acme_wave.wave": {"vendor_version": "7.2"}},
            audio_ownership="rendered",
            normalization=[],
            logs=list(ctx.logs),
            metadata={},
        )
```

## Stability Tiers

See [platform-contract.md](../contracts/platform-contract.md).

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
