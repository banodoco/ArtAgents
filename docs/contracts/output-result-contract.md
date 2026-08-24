# Output / Result Contract — M1

Every **M1-adopter executor** writes a single universal **result manifest** at a
well-known path relative to its output directory. This manifest is the canonical
cross-executor contract: it says what inputs were used, what outputs were produced,
and how to verify them.

> **Note**: This is the implementation-level reference. For the SDK-facing
> `manifest_path` pointer contract, see [SDK docs](../reference/sdk.md). For the normative
> platform stability tiers, see [platform-contract.md](platform-contract.md).

## Universal manifest: `{out}/manifest.json`

Every M1 executor writes **one** file named `manifest.json` into its output
location, determined by the executor's established `--out` behaviour:

| `--out` shape | Manifest path |
|---|---|
| Names a directory (most executors) | `{out}/manifest.json` |
| Names a file (understanding trio) | Sibling file: `{out_dir}/manifest.json` beside the named output file |

The manifest file is written **atomically** through the shared
`write_manifest()` helper (`astrid.core._shared.result_manifest`) and is valid
JSON with a flat top-level object.

## Required core fields

Every universal result manifest carries these six fields:

| Field | Type | Description |
|---|---|---|
| `schema_version` | `integer` | Manifest schema version (currently `1` for most families; `2` for generation executors). |
| `kind` | `string` | Slug-like executor identifier (see [Kind vocabulary](#kind-vocabulary) below). |
| `inputs` | `object` | Arbitrary key/value map recording the executor's resolved inputs. |
| `outputs` | `array<OutputEntry>` | List of produced artifacts with file/directory metadata (see [Output entries](#output-entries) below). |
| `created` | `string` | ISO-8601 UTC timestamp of manifest creation. |
| `warnings` | `array` | Non-fatal issues encountered; empty list when none. |

The shared `write_manifest()` validator rejects any manifest missing these
six fields. Executors may include **extra top-level fields** beyond this core
set — the validator passes them through unchanged.

The SDK's `InvocationResult.executor_version` is the SHA-256 identity of the
executor definition admitted into the immutable kernel task. It is not a
late lookup of whichever definition happens to be installed when a terminal
result is replayed. A queued task is fenced before execution if that definition
has changed; a new public invocation under the new definition receives a new
idempotency identity. A retry of a historical executor task admitted before
this identity was recorded fails closed before executor invocation and directs
the caller to submit a new invocation.

## Kind vocabulary

The `kind` field is an **open vocabulary** — no central registry gates it.
M1 adopters use executor-scoped identifiers following the convention
`{family}.{executor_name}` or a short lowercase slug. The `kind` value must
match `^[a-z0-9][a-z0-9._-]*$`.

| `kind` | Executor | Family |
|---|---|---|
| `generation.generate_image` | `generation.generate_image` | Generation |
| `generation.generate_video` | `generation.generate_video` | Generation |
| `generation.generate_image_openai` | `generation.generate_image_openai` | Generation |
| `understanding.audio_understand` | `understanding.audio_understand` | Understanding |
| `understanding.video_understand` | `understanding.video_understand` | Understanding |
| `understanding.visual_understand` | `understanding.visual_understand` | Understanding |
| `understanding.scene_describe` | `understanding.scene_describe` | Understanding |
| `transcript` | `editorial.transcribe` | Editorial |
| `scenes` | `editorial.scenes` | Editorial |
| `shots` | `editorial.shots` | Editorial |
| `quotes` | `editorial.quote_scout` | Editorial |
| `pool` | `training.pool_build` | Training |
| `render` | `iteration.assemble` | Iteration |
| `reigh.spatial_audio_page` | `reigh.spatial_audio_page` | Reigh |

The `kind` field is **additive-only** within a given executor — once an
executor ships a `kind` at its declared output path, downstream consumers
can depend on that value not changing within a major version.

## Output entries

Each entry in the `outputs` array represents one produced artifact and
carries at minimum:

| Field | Type | Description |
|---|---|---|
| `path` | `string` | Relative path from the manifest's parent directory. |
| `content_hash` | `string` | SHA-256 digest prefixed `sha256:`. |
| `bytes` | `integer` | Size of the artifact in bytes. |
| `type` | `string` | `"file"` or `"directory"`. |

### File outputs

For plain files, `complete_output_metadata()` hashes the file bytes with
SHA-256, records the file size, and sets `type: "file"`.

```json
{
  "path": "transcript.json",
  "content_hash": "sha256:abc123...",
  "bytes": 12345,
  "type": "file"
}
```

### Directory outputs (tree hashing)

When an output entry represents a directory (e.g., `reigh.spatial_audio_page`'s
output directory or a generation executor's `images/` directory), the entry
uses `type: "directory"` and carries an `entries` array listing every
file recursively:

```json
{
  "path": ".",
  "content_hash": "sha256:def456...",
  "bytes": 1048576,
  "type": "directory",
  "entries": [
    {
      "path": "index.html",
      "bytes": 12345,
      "content_hash": "sha256:aaa111..."
    },
    {
      "path": "assets/style.css",
      "bytes": 4567,
      "content_hash": "sha256:bbb222..."
    }
  ]
}
```

The **tree-level `content_hash`** is `sha256(sorted(JSON(entries)))` — the
SHA-256 digest of the canonical JSON serialization of the sorted `entries`
array. This makes the directory hash deterministic and stable across
platforms.

### Optional (partial) outputs

Output entries may set `"optional": true`. When an optional output file does
not exist on disk, `complete_output_metadata()` marks it as `"missing": true`
instead of raising an error:

```json
{
  "path": "fallback_thumbnail.png",
  "optional": true,
  "missing": true
}
```

This supports **partial-output failure behaviour** in generation executors:
when a batch loop fails partway through, the manifest records the outputs
that *were* produced and marks unproduced optional outputs as missing.

Required outputs (the default) raise `FileNotFoundError` if missing.

## Domain-manifest coexistence

M1 executors may write **domain-specific manifests** in addition to the
universal `manifest.json`. The universal manifest coexists with these
without conflict:

- **`iteration.assemble`**: Writes both `manifest.json` (universal, `kind: render`) and
  `iteration.manifest.json` (domain-specific, iteration dialect). They are sibling
  files in the same output directory.
- **`reigh.spatial_audio_page`**: Writes both `manifest.json` (universal, `kind: reigh.spatial_audio_page`)
  and embeds a `<script id="manifest">` block in the generated HTML page. The
  embedded manifest is the domain dialect; the universal manifest is the
  cross-executor contract.

The universal manifest is **always** named `manifest.json` at the root of
the output location. Domain manifests use their own naming conventions and
do not change.

## File and directory hashing

All content hashing uses SHA-256 with a `sha256:` prefix:

- **Files**: `sha256:(raw file bytes)` via `sha256_file()`.
- **Directories**: `sha256(sorted-canonical-JSON(entries))` via `_tree_hash()`.
  Children are sorted by `path` before hashing, making the tree digest stable
  regardless of filesystem enumeration order.

Hash preservation rules:

- If an entry already carries a `content_hash` field (e.g., from a generation
  v2 manifest), `complete_output_metadata()` preserves it unchanged.
- If an entry carries a bare `sha256` field (without the prefix), the shared
  contract normalises it to `sha256:...` in `content_hash` and preserves the
  original `sha256` key.
- Otherwise the file is re-hashed on disk.

## `metadata.output_result_manifest` flag

Each M1-adopter executor declares `metadata.output_result_manifest: true` in
its `executor.yaml`. This flag serves as a **registry conformance signal**:

- The registry conformance gate (`tests/test_result_manifest.py`) enumerates
  every live default-registry executor.
- Executors with `output_result_manifest: true` must write a `manifest.json`
  at their output location.
- Executors without the flag must appear in the committed exemption list
  (`astrid/core/contracts/output_result_exemptions.json`) with a specific
  exemption reason (paid, GPU, heavy, unstable-artifact, external-escape-hatch).

This makes the M1 adoption boundary machine-verifiable.

## SDK / CLI `manifest_path` pointer

After invocation, the SDK returns an `InvocationResult` with an optional
`manifest_path` field — an absolute path to the universal `manifest.json`
produced by the invocation. Kernel-managed execution may publish this file to
managed CAS and remove private attempt staging; in that case `manifest_path`
remains durable while `run_root` is `None`. A CAS hash-fanout parent is not a
logical output directory.

```python
import astrid

result = astrid.invoke("editorial.transcribe", kind="executor", out="/tmp/out")
print(result.manifest_path)  # "/tmp/out/manifest.json" or None
```

The `manifest_path` is discovered through a two-step fallback:

1. **Payload preference**: If the executor's stdout payload includes a
   `manifest_path` or `manifest` key pointing to a file named `manifest.json`,
   that path is used.
2. **Output-directory fallback**: Otherwise, the SDK checks whether
   `{out}/manifest.json` exists on disk.

The SDK `invoke` result and the `--json` product CLI mirror this behaviour and
serialise the same `InvocationResult` envelope.

## Writing a result manifest (implementation reference)

Executors use the shared `write_manifest()` helper from
`astrid.core._shared.result_manifest`:

```python
from astrid.core._shared.result_manifest import write_manifest
from datetime import datetime, timezone

manifest = {
    "schema_version": 1,
    "kind": "transcript",
    "inputs": {"audio": str(audio_path), "model": "whisper-1", "language": "en"},
    "outputs": [
        {"path": "transcript.json"},
        {"path": "transcript.srt"},
        {"path": "transcript.txt"},
    ],
    "created": datetime.now(timezone.utc).isoformat(),
    "warnings": [],
}
write_manifest(out_dir / "manifest.json", manifest)
```

`write_manifest()` validates the required fields, enriches outputs with
`complete_output_metadata()` (hashing each file on disk), and writes the
result atomically via `write_json_atomic()`.

## Registry conformance and exemption list

The committed exemption list at `astrid/core/contracts/output_result_exemptions.json`
enumerates all 57 default-registry executors. As of the M1 cut:

- **14 M1 adopters**: Non-exempt, confirmed `output_result_manifest: true`.
- **43 exempted**: Assigned specific M2/long-tail reasons (paid, GPU, heavy,
  unstable-artifact, external-escape-hatch).

The exemption list is the authoritative source for which executors are
expected to produce a universal result manifest. It is consumed by the
registry conformance gate in `tests/test_result_manifest.py`.

## Schema evolution

- **Schema version 1**: Universal result manifest with `kind`, `inputs`,
  `outputs`, `created`, `warnings`, and optional domain-manifest coexistence.
- **Schema version 2**: Generation executors extend this with modality-specific
  fields (`modality`, `model`, `mode_used`, `model_actual`, `execution`,
  `request`, `seed`, plus optional v2 fields like `applied_features`,
  `dropped_features`, `duration_ms`, `cost_usd`, `request_id`). See
  [docs/generation/20-manifest-schema.md](../generation/20-manifest-schema.md).

New fields are **additive-only** — existing fields will not be removed or
change type within a major version.
