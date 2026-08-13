# Experiment Contract

**Status:** Normative
**Schema version:** 1
**Date:** 2026-07-28

## Summary

This contract defines the schema, validation rules, and lifecycle for
provider-independent generation experiments in Astrid.

Experiments aggregate existing project runs into structured comparisons. They
do not replace `run.json`, `manifest.json`, generation executors, task events,
or lineage. Provider-specific executors remain responsible for execution and
for recording the exact request and result.

Experiments are project-owned artifacts. The canonical layout is:

```text
projects/<project-slug>/
  experiments/<experiment-id>/experiment.json
  runs/<run-id>/
```

The `project_slug` in `experiment.json` must match the owning directory, and
all case `run_id` values resolve against that same project's `runs/` directory.
Project-scoped execution rejects experiment definitions or run roots outside
the selected project. Copies elsewhere are interchange or legacy evidence,
not managed experiments.

## Terminology

- **Experiment:** A question, hypotheses, factors, rubric, and set of cases.
- **Case:** One intended comparison unit, which may have multiple attempts.
- **Attempt:** One concrete Astrid run.
- **Replicate:** A case or attempt that changes only an explicitly controlled
  random factor such as seed.
- **Observation:** A directly recorded or mechanically derived fact.
- **Inference:** A claim supported by observations, with confidence and status.
- **Decision:** An action chosen because of observations or inferences.
- **Capture gap:** Missing or ambiguous provenance that prevents a reliable
  comparison.

## Artifacts

### `experiment.json` — Experiment definition

```json
{
  "schema_version": 1,
  "experiment_id": "desert-plant-motion-conditioning-20260727",
  "project_slug": "desert-plant-study",
  "title": "Desert plant motion conditioning",
  "question": "Which conditioning format best preserves continuous motion?",
  "hypotheses": [
    {
      "id": "h-mixed-media",
      "claim": "A composite video is accepted more reliably than mixed image and video attachments.",
      "status": "provisional"
    }
  ],
  "factors": [
    {
      "id": "conditioning",
      "values": ["four_images", "mixed_images_video", "video_only", "composite_video"]
    },
    {
      "id": "seed",
      "type": "integer"
    }
  ],
  "rubric": [
    {
      "id": "continuity",
      "label": "No visible breakpoint",
      "scale": {"min": 1, "max": 5}
    }
  ],
  "cases": [
    {
      "case_id": "four-images-seed-35635335",
      "label": "Four separate images",
      "run_id": "01EXAMPLE...",
      "attempt": 1,
      "factors": {
        "conditioning": "four_images",
        "seed": 35635335
      },
      "relationship": {
        "type": "baseline",
        "case_id": null
      },
      "expected_input_roles": ["appearance_reference"],
      "source_manifest": {
        "path": "manifest.json",
        "content_hash": "sha256:..."
      },
      "included": true
    }
  ],
  "created": "2026-07-27T00:00:00Z",
  "updated": "2026-07-27T00:00:00Z"
}
```

#### experiment_id

Required string. Must match `^[a-z0-9][a-z0-9._-]*$`. Unique within the
project.

#### project_slug

Required string. The owning project short name.

#### title

Required non-empty string. Human-readable experiment title.

#### question

Required non-empty string. The research question the experiment investigates.

#### hypotheses

Required array. Zero or more hypothesis objects, each with:
- `id` (required string, matches `^[a-z][a-z0-9._-]*$`)
- `claim` (required non-empty string)
- `status` (optional string: `provisional`, `confirmed`, `refuted`; default `provisional`)

#### factors

Required array. One or more factor objects:
- `id` (required string, matches `^[a-z][a-z0-9._-]*$`)
- `values` (optional array of strings — fixed levels)
- `type` (optional string when `values` not specified, e.g., `integer`, `float`, `string`)

At least one factor must have `values` (a controlled factor).

#### rubric

Required array. One or more rubric dimension objects:
- `id` (required string, matches `^[a-z][a-z0-9._-]*$`)
- `label` (required non-empty string)
- `scale` (required object with `min` and `max` integers, `min < max`)
- `description` (optional string)

#### cases

Required non-empty array. Each case:
- `case_id` (required string, matches `^[a-z0-9][a-z0-9._-]*$`)
- `label` (required non-empty string)
- `run_id` (required string — a valid Astrid ULID run identifier)
- `attempt` (required positive integer, default 1)
- `factors` (required object mapping factor `id` to value)
- `relationship` (required object with `type` and optional `case_id`)
  - `type`: `baseline`, `variant`, `replicate`, or `retry`
  - `case_id`: the parent case for variants/replicates/retries; null for baseline
- `expected_input_roles` (optional array of role strings from the ordered input role vocabulary)
- `source_manifest` (optional but recommended object pinning the run-relative
  manifest `path` and its expected `content_hash`; preparation fails that case
  closed if the bytes no longer match)
- `included` (optional boolean, default true — false excludes from review)
- Extra fields are preserved (additive).

#### created / updated

ISO-8601 UTC timestamps.

### `review.json` — Normalized review

Produced by `iteration.experiment_prepare`. One entry per case:

```json
{
  "schema_version": 1,
  "experiment_id": "desert-plant-motion-conditioning-20260727",
  "cases": [
    {
      "case_id": "composite-video-seed-35635345",
      "run_id": "01EXAMPLE...",
      "status": "completed",
      "provider": "discord_browser",
      "backend": "black_forest_app",
      "model": "requested-model",
      "model_actual": "reported-model-or-null",
      "mode": "video_to_video",
      "prompt": "Exact non-secret prompt",
      "prompt_capture": "exact",
      "request": {
        "prompt": "Exact non-secret prompt",
        "seed": 35635345,
        "duration": "20s"
      },
      "parameters": {
        "seed": 35635345,
        "duration": "20s",
        "resolution": "720p",
        "aspect_ratio": "16:9"
      },
      "inputs": [
        {
          "ordinal": 1,
          "role": "composite_appearance_and_motion_reference",
          "path": "inputs/reference-board.mp4",
          "content_hash": "sha256:...",
          "verified": true,
          "media_type": "video/mp4",
          "metadata": {
            "width": 1280,
            "height": 704,
            "duration_seconds": 20,
            "fps": 24
          }
        }
      ],
      "outputs": [
        {
          "path": "outputs/result.mp4",
          "content_hash": "sha256:...",
          "verified": true,
          "media_type": "video/mp4",
          "metadata": {
            "width": 1280,
            "height": 704,
            "duration_seconds": 20.04,
            "fps": 24
          }
        }
      ],
      "timing": {
        "submitted_at": "2026-07-27T00:00:00Z",
        "completed_at": "2026-07-27T00:05:00Z",
        "duration_ms": 300000
      },
      "cost_usd": null,
      "warnings": [],
      "error": null,
      "capture_gaps": [],
      "source_manifest": {
        "path": "manifest.json",
        "content_hash": "sha256:...",
        "expected_content_hash": "sha256:...",
        "verified": true
      },
      "run_record": {
        "path": "run.json",
        "verified": true
      },
      "included": true
    }
  ],
  "created": "2026-07-27T00:00:00Z"
}
```

`schema_version` is required and must be the non-boolean integer `1`.
`created` is required and must be an ISO-8601 timestamp with timezone
information.

#### status values

- `completed` — All outputs produced successfully.
- `partial` — Some outputs produced but not all.
- `provider_rejected` — Provider refused the request.
- `failed` — Execution failed.
- `timed_out` — Did not complete within expected time.
- `interrupted` — Terminated before completion.
- `draft` — Not yet executed.

#### provider values

Open vocabulary. Examples: `fal`, `openai`, `comfyui`, `vibecomfy`, `discord_browser`, `local`.

#### inputs

Each input:
- `ordinal` (required positive integer — position in ordered input sequence)
- `role` (required string from the ordered input role vocabulary)
- `path` (required relative path from the run's review context)
- `content_hash` (required string, `sha256:` prefixed)
- `media_type` (optional MIME type)
- `metadata` (optional media probe metadata: width, height, duration_seconds, fps, etc.)
- `verified` (required boolean in normalized review data; inline playback is
  allowed only when the current local bytes match `content_hash`)

#### outputs

Each output:
- `path` (required relative path from the run's review context)
- `content_hash` (required string, `sha256:` prefixed)
- `media_type` (optional MIME type)
- `metadata` (optional media probe metadata)
- `source_url` (must NOT be present — secrets/signed URLs rejected)
- `verified` (required boolean in normalized review data)

#### capture_gaps

Array of objects describing missing or ambiguous provenance:
- `kind` (required string: `missing_prompt`, `missing_input_hash`, `missing_output_hash`,
  `missing_manifest`, `expired_only_reference`, `ambiguous_provenance`, `unknown`)
- `detail` (optional string)

#### source_manifest

Reference to the source manifest used for normalization:
- `path` (relative path)
- `content_hash` (SHA-256 of the manifest bytes actually read)
- `expected_content_hash` (optional digest pinned by `experiment.json`)
- `verified` (boolean; false is a first-class provenance failure)

The normalizer hashes the same byte buffer it parsed. It never reports a
digest from a later, different read. `run_record` separately reports whether a
same-run `run.json` validated and matched the case `run_id`.

#### request and prompt_capture

`request` preserves the complete captured non-secret provider request,
including additive provider knobs. Secret-bearing fields, authorization
headers, signed URLs, and absolute source paths are recursively redacted.
`prompt_capture` distinguishes `exact`, `partial`, `manual`, and unknown
capture. A truncated provider preview is never presented as an exact prompt.

#### path and media safety

Artifact and manifest paths must be relative, traversal-free filesystem paths
with no leading or trailing whitespace or control characters. Every URI scheme
form, backslashes, symlinks that escape the owning run, and string lookalikes
for booleans are rejected. Static review playback requires `--runs-dir`,
re-hashes every displayed artifact at render time, and emits only an escaped,
URL-quoted relative link into that verified run tree.

### `diagnostics.json`

Produced alongside `review.json`:

```json
{
  "schema_version": 1,
  "experiment_id": "...",
  "total_cases": 10,
  "included_cases": 8,
  "excluded_cases": 2,
  "status_counts": {
    "completed": 5,
    "failed": 2,
    "partial": 1,
    "provider_rejected": 1,
    "timed_out": 1
  },
  "duplicate_output_groups": [
    {
      "content_hash": "sha256:...",
      "case_ids": ["case-a", "case-b"]
    }
  ],
  "input_echo_cases": [
    {
      "case_id": "case-c",
      "input_hash": "sha256:...",
      "output_hash": "sha256:...",
      "detail": "Input video appears identical to output"
    }
  ],
  "capture_gap_counts": {
    "missing_prompt": 1,
    "missing_input_hash": 2
  },
  "source_manifest_mismatches": [],
  "warnings": []
}
```

## Ordered input role vocabulary

| Role | Description |
|------|-------------|
| `appearance_reference` | Static visual reference for appearance/style |
| `motion_reference` | Motion/video reference for dynamics |
| `composite_appearance_and_motion_reference` | Combined appearance and motion reference |
| `start_frame` | First frame conditioning image |
| `end_frame` | Last frame conditioning image |
| `style_reference` | Creative style reference |
| `mask` | Spatial mask for inpainting/editing |
| `source_video` | Video to transform/edit |
| `source_audio` | Audio to transform/edit |
| `workflow` | ComfyUI workflow definition |
| `control_signal` | ControlNet, depth, pose, etc. |
| `other` | Unclassified input |

Roles are additive. Unknown values are preserved under `other` with the
original provider slot name in provider-specific details.

## Evaluation and claims

### review.final.json

```json
{
  "schema_version": 1,
  "experiment_id": "...",
  "decisions": [
    {
      "case_id": "four-images-seed-35635335",
      "reviewer": {
        "type": "human",
        "id": "peter"
      },
      "scores": {
        "continuity": 2,
        "direction": 3,
        "camera": 3,
        "appearance": 4
      },
      "verdict": "iterate",
      "notes": "Visible breakpoint before ground growth.",
      "created": "2026-07-27T00:00:00Z"
    }
  ]
}
```

### Observation

```json
{
  "id": "obs-mixed-rejection-1",
  "type": "observation",
  "claim": "The mixed image and video request was rejected.",
  "evidence": [
    {
      "case_id": "mixed-input-1",
      "kind": "provider_response",
      "ref": "result.json#error"
    }
  ]
}
```

### Inference

```json
{
  "id": "inf-mixed-unsupported",
  "type": "inference",
  "claim": "This Discord route likely rejects mixed media types.",
  "evidence_ids": ["obs-mixed-rejection-1", "obs-mixed-rejection-2"],
  "confidence": "medium",
  "status": "provisional"
}
```

### Decision

```json
{
  "id": "dec-use-composite-video",
  "type": "decision",
  "claim": "Use one composite MP4 for the next attempt.",
  "based_on": ["inf-mixed-unsupported"]
}
```

## Validation rules

### ID validation

- `experiment_id`: `^[a-z0-9][a-z0-9._-]*$`
- `hypothesis.id`: `^[a-z][a-z0-9._-]*$`
- `factor.id`: `^[a-z][a-z0-9._-]*$`
- `rubric[].id`: `^[a-z][a-z0-9._-]*$`
- `case_id`: `^[a-z0-9][a-z0-9._-]*$`
- `run_id`: Must be a valid 26-character Crockford ULID

### Path safety

- All paths must be relative. Absolute paths and path-traversal sequences
  (`..`, `~`) are rejected.
- Paths must not contain NUL bytes.

### Evidence reference integrity

- Inferences must carry a non-empty list of string `evidence_ids`, each naming
  a valid observation.
- Decisions must carry a non-empty list of string `based_on` references, each
  naming a valid inference or observation.
- References to malformed, missing, self, or unsupported claim kinds are
  rejected; inference-to-inference/decision and decision-to-decision links are
  not accepted.

### Secret redaction

The following must never appear in any experiment artifact:
- `source_url` on normalized output entries
- Raw authorization headers
- API keys, tokens, or secrets
- Signed query strings
- Live provider URLs

### Lifecycle validation

Every case must have a valid `status` from the terminal status vocabulary.
Failure states (`failed`, `provider_rejected`, `timed_out`, `interrupted`)
must record an `error` message.

## Schema evolution

- **Schema version 1**: Experiment definition, normalized review, diagnostics,
  evaluation records as defined above.
- New fields are **additive-only** within a major version.
- Unknown fields in any object are preserved (passthrough).
- Breaking changes require a major version bump and a migration path.

## Provider independence

The experiment system reads only:
1. A project run ID.
2. The run's universal `manifest.json` (schema version 1 or 2).
3. An experiment case record describing factors and expected input roles.

Provider-specific execution logic must not enter:
- Schema validation
- Normalization
- The HTML viewer
- Evaluation schemas
