# Manifest Schema (schema_version: 2)

Every generation invocation emits a **manifest** — a JSON artifact that
records what was requested, what was produced, and any warnings or errors
encountered.  Manifests are the canonical record of a generation run.

Schema v2 is a **superset of the universal result manifest** contract
(`docs/output-result-contract.md`). It carries the universal core fields
(`kind`, `inputs`, `outputs`, `created`, `warnings`) plus
generation-specific fields. Schema v2 adds `mode_used`, `model_actual`,
`applied_features`, `dropped_features`, `duration_ms`, `cost_usd`, and
`request_id`.

## Top-level shape

```json
{
  "schema_version": 2,
  "kind": "generation.generate_image",
  "inputs": {
    "model": "flux-dev",
    "mode": "t2i",
    "execution": "cloud",
    "prompt": "a serene mountain lake at dawn",
    "seed": 42,
    "count": 1
  },
  "modality": "image",
  "model": "flux-dev",
  "mode_used": "t2i",
  "model_actual": "fal-ai/flux/dev",
  "execution": "cloud",
  "request": {
    "prompt": "a serene mountain lake at dawn",
    "negative_prompt": null,
    "seed": 42,
    "count": 1,
    "size": "1024x1024",
    "image_ref_resolved": null
  },
  "outputs": [
    {
      "path": "images/0-flux-dev.png",
      "content_hash": "sha256:abc123...",
      "source_url": "https://fal.media/files/...",
      "bytes": 1048576,
      "request_id": "req_abc123"
    }
  ],
  "seed": 42,
  "created": "2026-05-17T19:00:00Z",
  "warnings": [],
  "applied_features": ["prompt", "seed", "size"],
  "duration_ms": 3421,
  "cost_usd": 0.002,
  "request_id": "req_abc123",
  "source_urls": ["https://fal.media/files/..."]
}
```

## Field reference

### Common fields (all modalities)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `schema_version` | `integer` | yes | Always `2` for this schema version. |
| `kind` | `string` | yes | Universal executor kind identifier (e.g. `"generation.generate_image"`, `"generation.generate_image_openai"`). See [output-result-contract.md](../../../docs/output-result-contract.md#kind-vocabulary). Added in M1. |
| `inputs` | `object` | yes | Arbitrary key/value map recording the executor's resolved inputs. Added in M1. |
| `modality` | `string` | yes | `"image"`, `"video"`, or `"audio"`. |
| `model` | `string` | yes | The model ID used (from the registry). |
| `mode_used` | `string` | yes | Canonical mode name (e.g. `"t2i"`, `"i2i"`, `"edit"`). Added in v2. |
| `model_actual` | `string` | yes | The literal template or endpoint that executed (e.g. `"fal-ai/flux/dev"`, `"image/z_image"`). Added in v2. |
| `execution` | `string` | yes | `"local"` or `"cloud"`. |
| `request` | `object` | yes | Echo of the caller's request parameters (see per-modality extensions). |
| `outputs` | `array<OutputEntry>` | yes | List of generated artifacts (may be empty on full failure). |
| `seed` | `integer` | yes | The effective seed used (caller-supplied or randomly generated). |
| `created` | `string` | yes | ISO-8601 UTC timestamp of manifest creation. |
| `warnings` | `array<Warning>` | yes | Non-fatal issues encountered (empty if none). |
| `applied_features` | `array<string>` | no | Canonical features that were applied in this generation. Added in v2. |
| `dropped_features` | `array<string>` | no | Features the caller requested but were dropped-with-warning. Added in v2. |
| `duration_ms` | `integer` | no | Wall-clock generation time in milliseconds. Added in v2. |
| `cost_usd` | `float` | no | Estimated cost in USD (cloud backends only). Added in v2. |
| `request_id` | `string` | no | Backend-assigned request ID (for support/debugging). Added in v2. |
| `source_urls` | `array<string>` | no | Debug-only source URLs returned by the backend (temporary — may expire). Added in v2. |
| `error` | `string` | no | Fatal error message; present only when the run failed completely. |

### OutputEntry

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `path` | `string` | yes | On-disk path to the generated artifact (relative to executor `--out`). |
| `content_hash` | `string` | yes | SHA-256 hash of the artifact bytes (prefixed `"sha256:"`). |
| `source_url` | `string` | no | Debug-only URL returned by the cloud backend (temporary — may expire). |
| `bytes` | `integer` | no | Size of the artifact in bytes. |
| `request_id` | `string` | no | Backend-assigned request ID (for support/debugging). |

> **Important:** `content_hash` and `path` are the canonical identifiers.
> `source_url` is temporary (fal URLs expire) and exists only for debugging.

### Warning

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `feature` | `string` | yes | The canonical feature name that was dropped (e.g. `"negative_prompt"`). |
| `reason` | `string` | yes | Human-readable explanation (e.g. `"not supported by model 'flux-dev' mode 't2i'"`). |

### Image-modality extension fields

The `request` object for image modality includes:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `prompt` | `string` | yes | The text prompt used. |
| `negative_prompt` | `string` | no | Negative prompt, if provided and supported. |
| `seed` | `integer` | yes | Seed value. |
| `count` | `integer` | yes | Number of images requested. |
| `size` | `string` | no | Requested output dimensions (e.g. `"1024x1024"`). |
| `image_ref_resolved` | `string` | no | Resolved path or URL of the reference image (singular per SD-005). |

## Schema evolution

- **schema_version 2** is the current version (Sprint 02). Adds `mode_used`,
  `model_actual`, `applied_features`, `dropped_features`, `duration_ms`,
  `cost_usd`, `request_id`, and `source_urls`.
- **schema_version 1** was the initial version (Sprint 01). No longer
  supported — no compat shim (SD-006).
- Pre-launch, the schema may change freely.
- Post-launch, changes are **additive-only** — new fields may be added, but
  existing fields must not be removed or change type.

## Example: successful image generation (v2)

```json
{
  "schema_version": 2,
  "kind": "generation.generate_image",
  "inputs": {
    "model": "flux-dev",
    "mode": "t2i",
    "execution": "cloud",
    "prompt": "a cat wearing a spacesuit",
    "seed": 1678901234,
    "count": 1
  },
  "modality": "image",
  "model": "flux-dev",
  "mode_used": "t2i",
  "model_actual": "fal-ai/flux/dev",
  "execution": "cloud",
  "request": {
    "prompt": "a cat wearing a spacesuit",
    "negative_prompt": null,
    "seed": 1678901234,
    "count": 1,
    "size": "landscape_4_3",
    "image_ref_resolved": null
  },
  "outputs": [
    {
      "path": "images/0-flux-dev.png",
      "content_hash": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "source_url": "https://fal.media/files/tmp/abc123.png",
      "bytes": 245760,
      "request_id": "req_abc123"
    }
  ],
  "seed": 1678901234,
  "created": "2026-05-17T19:23:45Z",
  "warnings": [],
  "applied_features": ["prompt", "seed", "count", "size"],
  "duration_ms": 2841,
  "cost_usd": 0.002,
  "request_id": "req_abc123"
}
```

## Example: feature dropped with warning (v2)

```json
{
  "schema_version": 2,
  "kind": "generation.generate_image",
  "inputs": {
    "model": "flux-dev",
    "mode": "t2i",
    "execution": "cloud",
    "prompt": "a serene mountain lake",
    "seed": 42,
    "count": 1
  },
  "modality": "image",
  "model": "flux-dev",
  "mode_used": "t2i",
  "model_actual": "fal-ai/flux/dev",
  "execution": "cloud",
  "request": {
    "prompt": "a serene mountain lake",
    "negative_prompt": null,
    "seed": 42,
    "count": 1,
    "size": "1024x1024",
    "image_ref_resolved": null
  },
  "outputs": [
    {
      "path": "images/0-flux-dev.png",
      "content_hash": "sha256:...",
      "bytes": 204800,
      "request_id": "req_def456"
    }
  ],
  "seed": 42,
  "created": "2026-05-17T19:24:00Z",
  "warnings": [
    {
      "feature": "negative_prompt",
      "reason": "not supported by model 'flux-dev' mode 't2i'"
    }
  ],
  "dropped_features": ["negative_prompt"],
  "duration_ms": 1523,
  "cost_usd": 0.002,
  "request_id": "req_def456"
}
```
