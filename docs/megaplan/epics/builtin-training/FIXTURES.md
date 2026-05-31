# FIXTURES: Offline Test Strategy

> **Status:** ARCHIVED — the checked-in offline fixture tree has been retired.
> This document records the original strategy only; active commands should use
> project-local fixture paths.

## Strategy

The built-in training pipeline MUST be testable without network access, OpenAI/Gemini API keys, RunPod credentials, or GPU access. Fixtures provide:

1. **Tiny local media files** — short (2-10 second) synthetic or blank video clips committed to the repo
2. **Fixture configs** — dataset configs pointing at local media, with budgets set to zero
3. **Fixture review decisions** — pre-baked accept/reject decisions for deterministic manifest output
4. **Expected manifests** — both canonical and ai-toolkit adapter format, for round-trip validation
5. **Parser-policy vectors** — configs exercising missing/future schema_version paths
6. **Caption sidecars** — pre-baked caption JSON files matching the ai-toolkit preflight format

## Fixture Media Paths

> **M1 Task:** Create these media files. They must be tiny (a few KB each), valid video files that ffmpeg can read without error.

| Path | Description | Expected Content |
|---|---|---|
| `path/to/local-fixtures/media/test_clip_01.mp4` | 5-second test clip | Minimal valid MP4, e.g., black frame with silent audio |
| `path/to/local-fixtures/media/test_clip_02.mp4` | 3-second test clip (too short for default filter) | Minimal valid MP4 |
| `path/to/local-fixtures/media/test_clip_03.mp4` | 7.5-second test clip | Minimal valid MP4 |
| `path/to/local-fixtures/media/test_clip_04.mp4` | 2-second test clip (barely at min boundary) | Minimal valid MP4 |

All media files must:
- Be valid video files (MP4 container, H.264 or similar)
- Parse correctly with ffmpeg/ffprobe
- Have deterministic content hashes (committed as-is, not generated during test)
- Be small enough to commit (< 100 KB each)

## Fixture Config

File: `contracts/fixtures/dataset-config.valid.json`

A complete v1 dataset config pointing at local fixture media. Key properties:
- `schema_version: 1`, `media_type: video`
- `source.provider: local_folder` pointing at `path/to/local-fixtures/media/`
- Single bucket with `target_count: 2`
- Budgets set to zero (`max_api_calls: 10`, `max_estimated_cost_usd: 0.50`)
- All filters enabled with wide thresholds (accept test clips)

## Parser-Policy Fixture Vectors

| File | Expected Behavior |
|---|---|
| `contracts/fixtures/dataset-config.valid.json` | Passes strict schema validation |
| `contracts/fixtures/dataset-config.missing-schema-version.json` | Passes with deprecation warning ("treating as v1") |
| `contracts/fixtures/dataset-config.future-version.json` | Fails with `"unsupported schema_version 99"` |

## Fixture Review Decisions

File: `contracts/fixtures/review-decisions.valid.json`

Pre-baked review decisions for fixture items:
- `fixture_vid-s01`: accepted
- `fixture_vid-s02`: rejected (low_quality)
- `fixture_vid-s03`: accepted, with user-edited caption

The fixture pipeline applies these decisions to produce deterministic manifests.

## Expected Canonical Manifest

File: `contracts/fixtures/expected-manifest.json`

The expected output of `builtin.dataset_build` after applying fixture review decisions. Contains:
- 2 accepted items (fixture_vid-s01, fixture_vid-s03)
- 1 rejected item (fixture_vid-s02, not in manifest)
- Full `ReviewItem` shapes with provenance, captions, filter results, review decisions
- Stats: `total_accepted: 2`, `total_rejected: 1`

## Expected AI-Toolkit Adapter Manifest

File: `contracts/fixtures/expected-ai-toolkit-manifest.json`

The expected output of the `ai-toolkit-ltx` manifest adapter. Contains:
- Flat `clips` array with 2 entries
- Each clip has `clip_id`, `clip_file`, `path`, `caption_file`, `bucket`, `source_url`, `duration_s`, `content_hash`
- `caption_file` points to sibling `fixtures/captions/<clip_id>.caption.json`

## Caption Sidecars

File: `contracts/fixtures/captions/fixture_clip_001.caption.json`

Example caption sidecar matching the ai-toolkit preflight expectation. Format:
```json
{
  "text": "...",
  "schema_version": 1,
  "confidence": 0.95,
  "model": "fixture",
  "generated_at": "..."
}
```

## No-Network / No-GPU Validation Behavior

When running with fixture configs:
1. Source provider reads from `path/to/local-fixtures/media/` (local files only, no YouTube/network)
2. Caption provider uses pre-baked caption sidecars (no API calls)
3. Filter stages use deterministic logic (no VLM/API calls)
4. Human review uses pre-baked decisions (no browser/server launch)
5. Manifest adapter writes to local filesystem (no GPU/RunPod)

### Validation Commands (M1+)

```bash
# Validate all fixtures parse as JSON
python3 -m json.tool contracts/fixtures/dataset-config.valid.json > /dev/null
python3 -m json.tool contracts/fixtures/dataset-config.missing-schema-version.json > /dev/null
python3 -m json.tool contracts/fixtures/dataset-config.future-version.json > /dev/null
python3 -m json.tool contracts/fixtures/review-decisions.valid.json > /dev/null
python3 -m json.tool contracts/fixtures/run-state.valid.json > /dev/null
python3 -m json.tool contracts/fixtures/expected-manifest.json > /dev/null
python3 -m json.tool contracts/fixtures/expected-ai-toolkit-manifest.json > /dev/null
python3 -m json.tool contracts/fixtures/captions/fixture_clip_001.caption.json > /dev/null

# M1: Run fixture smoke test (no network, no GPU)
python3 -m pytest tests/builtin-training/test_fixture_smoke.py -v

# M1: Validate ai-toolkit adapter manifest passes preflight shape check
python3 -c "
import json
m = json.load(open('contracts/fixtures/expected-ai-toolkit-manifest.json'))
clips = m['clips']
assert len(clips) == 2
for c in clips:
    assert c.get('clip_file') or c.get('path'), f'missing clip_file/path in {c[\"clip_id\"]}'
    assert c.get('clip_id'), f'missing clip_id'
print('OK: ai-toolkit manifest passes preflight shape check')
"
```

## Fixture Schema Conformance (M1 Validation)

> **Note:** M0 validates that all fixture and schema files are syntactically valid JSON. M1 is responsible for validating fixtures against their schemas using `jsonschema` as part of implementation. This is M1's natural handoff validation.

M1 should add a test that validates:
- `dataset-config.valid.json` → validates against `dataset-config.schema.json`
- `dataset-config.future-version.json` → fails schema validation (expected)
- `review-decisions.valid.json` → validates against `review-decision.schema.json`
- `run-state.valid.json` → validates against `run-state.schema.json`
- `expected-manifest.json` → validates against `manifest.schema.json`
- `expected-ai-toolkit-manifest.json` → validates against `ai-toolkit-adapter-manifest.schema.json`
