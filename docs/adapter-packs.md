# Adapter Packs

How adapter packs wrap separately-owned external substrates — VibeComfy, RunPod,
fal.ai, Moirae — and how they differ from builtin packs.

## What Makes a Pack an Adapter

An adapter pack owns capabilities that delegate to an **external substrate** —
a tool, service, or runtime that Astrid does not own or ship. The pack provides
the manifest, entrypoint, and integration glue; the substrate provides the
actual work.

The canonical example is the `external` pack at `astrid/packs/external/`.

## The `external` Pack

Shipped with Astrid. Contains adapters for four external substrates:

| Executor ID | Substrate | What it does |
|---|---|---|
| `external.moirae` | [Moirae](https://github.com/peteromallet/Moirae) | Terminal-as-cinema video renderer |
| `external.fal_foley` | fal.ai | AI sound effect generation |
| `external.vibecomfy.run` | VibeComfy/ComfyUI | Local image generation via ComfyUI workflows |
| `external.vibecomfy.validate` | VibeComfy/ComfyUI | Validate ComfyUI workflow JSON |
| `external.runpod.provision` | RunPod | Provision GPU pods |
| `external.runpod.exec` | RunPod | Execute commands on remote pods |
| `external.runpod.teardown` | RunPod | Tear down GPU pods |
| `external.runpod.session` | RunPod | Manage interactive pod sessions |

## Manifest Conventions

Adapter executor manifests declare `kind: external` in their component metadata:

```json
{
  "id": "external.moirae",
  "kind": "external",
  "isolation": {
    "mode": "subprocess",
    "network": false,
    "binaries": ["ffmpeg"],
    "requirements": ["moirae"]
  },
  "metadata": {
    "manifest_only": true,
    "binary_requirements_enforced": "explicit_check_only"
  }
}
```

The `kind: external` field signals to agents and tooling that this capability
wraps a third-party substrate. The `_capability` block in inspect output
preserves this:

```bash
python3 -m astrid executors inspect external.moirae --json
# → "_capability": { "kind": "external", ... }
```

Key manifest conventions for adapters:
- `isolation.mode` is typically `"subprocess"` — the adapter spawns the
  external tool as a child process
- `isolation.binaries` lists required system binaries
- `isolation.requirements` lists Python packages the substrate needs
- `metadata.manifest_only: true` indicates the adapter has no custom Python
  runtime beyond a thin `run.py` entrypoint
- `metadata.binary_requirements_enforced` describes how binary checks work
  (e.g., `"explicit_check_only"` means the adapter checks availability but
  doesn't auto-install)

## How Adapter Packs Differ from Builtin Packs

| Aspect | Builtin Pack | Adapter Pack |
|---|---|---|
| Ownership | Astrid owns the substrate | Third party owns the substrate |
| Trust | Fully trusted; runs in-process or subprocess | Trust limited to the adapter layer |
| Support | Astrid supports end-to-end | Astrid supports the adapter; substrate issues go upstream |
| Shipping | Runtime and dependencies bundled | Only the manifest and thin `run.py` are bundled |
| Versioning | Versioned with Astrid | Substrate versioned independently |
| Failure modes | Astrid can fix | Adapter reports substrate errors; Astrid can't fix the substrate |

## Creating an Adapter Pack

Same workflow as any pack, with these conventions:

```bash
# Scaffold
python3 -m astrid packs new my_adapter

# Add an executor
python3 -m astrid executors new my_adapter.tool_name
```

In the executor manifest, set `kind: external` and configure isolation
appropriately. The `run.py` entrypoint should be a thin wrapper that:
1. Checks binary/package requirements
2. Delegates to the substrate
3. Translates substrate errors into Astrid's error conventions

## Discovery

Adapter executors appear in normal search and list output alongside builtins.
Agents can identify them by the `kind: external` field in the `_capability`
block during inspect:

```bash
python3 -m astrid executors search runpod --json
python3 -m astrid executors list --json --pack external
```

The search surface treats adapter executors the same as builtins — they're
first-class capabilities.
