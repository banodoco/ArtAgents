# Adapter Packs

How adapter packs wrap separately-owned external substrates — VibeComfy, RunPod,
fal.ai, Moirae — and how they differ from core capability packs.

## What Makes a Pack an Adapter

An adapter pack owns capabilities that delegate to an **external substrate** —
a tool, service, or runtime that Astrid does not own or ship. The pack provides
the manifest, entrypoint, and integration glue; the substrate provides the
actual work.

Each external substrate now lives in its own direct-child pack (e.g., `fal`,
`vibecomfy`, `runpod`, `moirae`). The legacy `external` pack definition was
removed; backward compatibility comes from deprecated pack-level aliases
declared in those canonical packs (`external.moirae` → `moirae.moirae`, etc.).

## Adapter Packs

Shipped with Astrid. Each pack adapts one external substrate:

| Pack | Executor IDs | Substrate | What it does |
|---|---|---|---|
| `fal` | `fal.fal_foley` | fal.ai | AI sound effect generation |
| `vibecomfy` | `vibecomfy.run`, `vibecomfy.validate` | VibeComfy/ComfyUI | Local image generation via ComfyUI workflows |
| `runpod` | `runpod.provision`, `runpod.exec`, `runpod.teardown`, `runpod.session`, `runpod.pull` | RunPod | GPU pod provisioning and execution |
| `moirae` | `moirae.moirae` | [Moirae](https://github.com/peteromallet/Moirae) | Terminal-as-cinema video renderer |
| `youtube` | `youtube.youtube_audio`, `youtube.upload` | YouTube | Video/audio download and upload |
| `reigh` | `reigh.open_in_reigh`, `reigh.publish`, `reigh.reigh_data`, `reigh.spatial_audio_page` | Reigh | Project handoff and publishing |

Legacy ids under `external.*` (e.g., `external.runpod.session`,
`external.vibecomfy.run`, `external.moirae`) remain functional only where a
canonical adapter pack declares the deprecated pack-level alias. See
[aliases-vs-forks-vs-overrides.md](aliases-vs-forks-vs-overrides.md) for
alias mechanics.

## Manifest Conventions

Adapter executor manifests declare `kind: external` in their component metadata:

```json
{
  "id": "moirae.moirae",
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
wraps a third-party substrate. The `_capability` block in the capability
inspection output preserves this:

```python
import astrid.sdk as sdk

cap = sdk.get_capability("moirae.moirae", kind="executor")
# → cap["_capability"] == {"kind": "external", ...}
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

## How Adapter Packs Differ from Core Capability Packs

| Aspect | Core Capability Pack | Adapter Pack |
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
# Scaffold (internal pack CLI — not a gateway family)
python3 -m astrid.core.pack.cli new my_adapter
```

In the executor manifest, set `kind: external` and configure isolation
appropriately. The `run.py` entrypoint should be a thin wrapper that:
1. Checks binary/package requirements
2. Delegates to the substrate
3. Translates substrate errors into Astrid's error conventions

## Discovery

Adapter executors appear in normal discovery alongside core capabilities.
Agents can identify them by the `kind: external` field in the
`_capability` block during inspect:

```python
import astrid.sdk as sdk

caps = sdk.discover(include_installed=False, kind="executor")
adapter = sdk.get_capability("runpod.provision", kind="executor")
```

The search surface treats adapter executors the same as core capabilities —
they're first-class capabilities.
