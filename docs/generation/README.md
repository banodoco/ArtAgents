# Generation Subsystem

The generation subsystem handles multi-modal media generation (image, video,
audio) across local and cloud backends.  It is the largest subsystem in Astrid,
spanning a model registry, a taxonomy of features and modes, backend adapters,
a canonical manifest format, and per-modality executor contracts.

## Data flow

```
models.yaml          ← single source of truth for model capabilities
      │
      ▼
ModelRegistry        ← validated, typed dataclasses (astrid/core/model_catalog/)
      │
      ▼
BackendAdapter        ← FalBackend (cloud) | VibeComfyBackend (local) | CodexBackend
      │                  (astrid/core/generation/backends/)
      ▼
manifest.json         ← canonical record of every generation run (v2 schema)
      │
      ▼
Per-modality contracts ← image (wired) | video (wired) | audio (cloud music wired)
```

1. **Model registry** — `models.yaml` declares every model: its modality,
   canonical modes (`t2i`, `i2i`, `edit`, etc.), per-mode `supports`/`requires`
   feature lists, and per-mode backend specs (local `template` + cloud
   `endpoint`).  Validated by `astrid.core.model_catalog.schema`.

2. **Backend adapters** — a thin `BackendAdapter` interface.  The executor
   picks an adapter by `execution` (`local` → VibeComfyBackend, `cloud` →
   FalBackend) and calls `.generate()`.  No backend-specific branching in
   executor code (SD-004).

3. **Manifest** — every invocation emits a `manifest.json` recording inputs,
   outputs, `applied_features`, `dropped_features`, warnings, timing, and
   cost.  Schema v2 is a superset of the universal result manifest contract.

4. **Per-modality contracts** — each modality doc specifies canonical modes,
   CLI inputs (`--mode`, `--model`, `--execution`, etc.), output directories
   and manifest shape, request validation rules, and feature-dropping
   semantics.

Before either a dry-run or live generation invocation, the SDK applies the
shared read-only preflight in `astrid/core/generation/preflight.py`. It checks
the model → mode → execution matrix and mode-required inputs before project
resolution or kernel admission. Thus an FLF request missing `image_end_ref`
and a cloud-only model requested with `execution="local"` both fail with a
typed actionable error and leave the run ledger untouched. Local video/image
routes additionally require the VibeComfy/ComfyUI prerequisites; Astrid never
falls back to cloud when those are missing.

## Document index

| # | Document | Scope |
|---|----------|-------|
| 00 | [features](00-features.md) | Canonical feature set, per-mode applicability, SD-003 |
| 10 | [registry-schema](10-registry-schema.md) | `models.yaml` shape, validation rules, v2 taxonomy |
| 20 | [manifest-schema](20-manifest-schema.md) | `manifest.json` v2 shape, warnings, output entries |
| 30 | [image-contract](30-image-contract.md) | Image modes (t2i/i2i/edit wired), CLI, backends |
| 31 | [video-contract](31-video-contract.md) | Video modes (t2v/i2v/flf wired), wired-cells table |
| 32 | [audio-contract](32-audio-contract.md) | Cloud music generation; tts/sfx remain planned |

## Code map

| Concern | Location |
|---------|----------|
| Model registry dataclasses + validation | `astrid/core/model_catalog/schema.py` |
| Model registry loader | `astrid/core/model_catalog/registry.py` |
| Features, modes, taxonomy registry | `astrid/core/generation/features.py` |
| Backend adapter interface | `astrid/core/generation/backends/base.py` |
| Cloud backend (fal.ai) | `astrid/core/generation/backends/fal.py` |
| Local backend (vibecomfy) | `astrid/core/generation/backends/vibecomfy.py` |
| Codex backend | `astrid/core/generation/backends/codex.py` |
| Backend registry/discovery | `astrid/core/generation/backends/registry.py` |

## Related docs

- [Discovery for agents](../guides/discovery-for-agents.md)
- [Astrid CLI contract](../contracts/cli-contract.md)
- [Packs: contract](../packs/contract.md)
