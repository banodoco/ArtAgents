# Provider-Independent Generation Experiments

**Status:** Proposed implementation plan  
**Date:** 2026-07-27  
**Scope:** Structured generation experiments, evidence-backed conclusions, and
input/output review across Astrid providers

## Summary

Astrid should support experiments that compare generations from Fal, OpenAI,
ComfyUI/VibeComfy, Discord/browser workflows, local generators, and future
providers without making the experiment system understand how any provider is
invoked.

The experiment layer will aggregate existing Astrid project runs and universal
result manifests. Provider-specific executors remain responsible for execution
and for recording the exact request and result. The experiment layer will:

1. Group runs into named cases with controlled factors and replicates.
2. Normalize their manifests into a provider-independent review model.
3. Detect capture gaps, duplicate outputs, input echoes, and failed cases.
4. Render a deterministic HTML comparison page.
5. Collect structured human evaluations through `editorial.human_review`.
6. Store observations, inferences, and decisions separately, with explicit
   evidence and confidence.

This is an aggregation and review layer, not a replacement for `run.json`,
`manifest.json`, generation executors, task events, or lineage.

## Why this works across generators

The experiment viewer does not call Fal, inspect ComfyUI nodes, control Discord,
or invoke OpenAI directly. It reads:

- A project run ID.
- The run's universal `manifest.json`.
- A small experiment case record describing factors and expected input roles.
- Optional structured evaluation state.

Astrid's generation manifest v2 already normalizes most Fal, OpenAI, Codex, and
local generation requests. Direct VibeComfy, Discord/browser automation, and
arbitrary local tools need manifest adoption or an importer, but they do not
require provider-specific branches in the viewer.

```text
Fal / OpenAI / Comfy / Discord / local generator
                       │
                       ▼
            provider executor or adapter
                       │
                       ▼
          run.json + universal manifest.json
                       │
                       ▼
              experiment case index
                       │
              ┌────────┴────────┐
              ▼                 ▼
       normalized review    evaluation state
           review.json       scores / notes
              │                 │
              └────────┬────────┘
                       ▼
                  review.html
                       │
                       ▼
       observations / inferences / decisions
```

## Terminology

Use **experiment** for the system and schema. Avoid using `inference` as the
primary schema term because it can mean either model execution or a conclusion
drawn from evidence.

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

## Goals

- Compare image, video, and audio generations across providers.
- Preserve exact non-secret requests, ordered input roles, outputs, failures,
  latency, cost, and provider identifiers.
- Make failed, rejected, timed-out, interrupted, and partial runs first-class.
- Display image, audio, and video inputs and outputs in one static HTML page.
- Support structured rubrics, notes, verdicts, and selections.
- Link every displayed artifact to a run, manifest, and SHA-256 digest.
- Separate execution evidence from mutable evaluation and conclusions.
- Detect duplicate outputs and cases where an uploaded input is mistaken for an
  output.
- Remain useful after temporary provider URLs expire.
- Import existing unmanaged runs conservatively without rewriting them.

## Non-goals

- Replacing Astrid's generation API or backend adapters.
- Defining one universal representation for every ComfyUI node.
- Automatically deciding subjective creative quality.
- Treating lineage completeness as aesthetic quality.
- Building a general statistical benchmarking platform in the first release.
- Making the static viewer execute providers.
- Copying all large media into every experiment by default.
- Promoting Discord user-account automation into a core provider assumption.

## Existing Astrid substrate

### Universal result manifests

`docs/contracts/output-result-contract.md` defines the cross-executor
`manifest.json` contract:

- `schema_version`
- `kind`
- `inputs`
- `outputs`
- `created`
- `warnings`

Outputs receive relative paths, SHA-256 hashes, byte sizes, and file/directory
metadata through `astrid.core._shared.result_manifest`.

### Generation manifest v2

`docs/generation/20-manifest-schema.md` already adds:

- Modality, model, actual model/endpoint, and execution mode.
- Exact request fields and effective seed.
- Applied and dropped features.
- Request ID, duration, cost, warnings, and errors.
- Hashed output entries and temporary source URLs.

This is the preferred source for generation cases.

### Project run ledger

Project `run.json` records identity, lifecycle, invocation, tool identity,
artifacts, timestamps, and the pointer to `manifest.json`. Exact prompts and
resolved generation parameters should remain in manifests or request files, not
be reconstructed from redacted CLI arguments.

### Lineage

Existing lineage can connect causal derivations and selected ancestors.
Current thread parent-edge kinds are only `causal` and `chosen`; the experiment
schema must not write an unsupported `variant` lineage kind.

Experiment-level relationships such as `baseline`, `variant`, `replicate`, and
`retry` live in `experiment.json`. When a concrete run derives from another
artifact, the underlying Astrid run may also use a `causal` parent edge.

### Human review

`editorial.human_review` already provides:

- A local authenticated review server.
- Static mounts with MP4 range support.
- Read-only `/data.json`.
- Versioned draft state.
- Schema-validated final submissions.

The experiment system should reuse it rather than creating another review
server or state protocol.

### Existing HTML precedents

- `rendering.timeline_storyboard` demonstrates deterministic static JSON, PNG,
  HTML, and universal-manifest output.
- `foley.foley_review` demonstrates playable input/output cards and review
  controls.
- `iteration.report.html` is not sufficient: it currently summarizes
  provenance quality and renderer fallbacks, not inference cases.

## Current gaps

- Discord POC runs do not consistently record full prompts, typed parameters,
  ordered inputs, terminal failures, media metadata, or hashes.
- Direct `vibecomfy.run` does not yet provide the same complete generation
  manifest as canonical generation executors.
- Arbitrary local generators may produce media without any Astrid manifest.
- There is no canonical experiment schema.
- There is no provider-independent normalizer.
- There is no generic input/output experiment gallery.
- There is no standard rubric/evaluation or evidence/claim schema.
- Existing iteration quality measures provenance completeness, not creative
  output quality.

## Architectural decisions

### AD-1: Experiments aggregate runs

An experiment references existing project run IDs and manifest paths. It does
not replace or duplicate their lifecycle records.

Managed provider outputs remain in their original run directories. Experiment
bundles use references and hashes by default. A later export operation may copy
or link assets into a portable bundle explicitly.

### AD-2: Core schemas, pack-level capabilities

Provider-independent validators and normalization live under:

```text
astrid/core/experiments/
  schema.py
  normalize.py
  evidence.py
  media.py
```

Initial user-facing capabilities live in the `iteration` pack because they
prepare and review a set of related generation runs:

```text
iteration.experiment_prepare
iteration.experiment_review
iteration.experiment_import
```

An optional orchestrator may later compose them:

```text
iteration.experiment_review_session
```

Do not add a batch-execution orchestrator until capture and review contracts are
stable.

### AD-3: Execution stays provider-specific

Existing generation executors and adapters continue to execute requests.
Experiment preparation consumes their manifests after completion.

Provider-specific execution logic must not enter:

- `experiment_prepare`
- `experiment_review`
- The HTML client
- Evaluation schemas

### AD-4: Evidence is immutable; evaluation is separate

Generation manifests are execution evidence and are never rewritten with
scores, opinions, or conclusions.

Mutable and derived data live in separate artifacts:

```text
experiment.json
review.json
review.state.json
review.final.json
analysis.json
conclusions.json
```

### AD-5: Failures produce records

Every managed attempt must terminate with a structured status:

- `completed`
- `partial`
- `provider_rejected`
- `failed`
- `timed_out`
- `interrupted`
- `draft`

A failure manifest may have an empty `outputs` array, but it must still record
the request, lifecycle, error phase, error message, and available evidence.

### AD-6: Local hashes are canonical

Canonical artifact identity is:

- Relative path within its owning run.
- SHA-256 content hash.
- Media metadata where relevant.

Provider URLs are diagnostic only because they expire. Secrets, tokens, signed
query strings, cookies, and raw authorization headers must never enter review
artifacts.

## Proposed experiment contract

Normative documentation should live at:

```text
docs/contracts/experiment-contract.md
```

Example:

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
      "values": [
        "four_images",
        "mixed_images_video",
        "video_only",
        "composite_video"
      ]
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
    },
    {
      "id": "direction",
      "label": "Continuous leftward growth",
      "scale": {"min": 1, "max": 5}
    },
    {
      "id": "camera",
      "label": "Orbit blends into tip-following",
      "scale": {"min": 1, "max": 5}
    },
    {
      "id": "appearance",
      "label": "Matches appearance references",
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
      "expected_input_roles": [
        "appearance_reference"
      ],
      "included": true
    }
  ],
  "created": "2026-07-27T00:00:00Z",
  "updated": "2026-07-27T00:00:00Z"
}
```

## Normalized review contract

`iteration.experiment_prepare` produces `review.json`. One normalized case
contains:

```json
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
    "path": "../runs/01EXAMPLE/manifest.json",
    "content_hash": "sha256:..."
  }
}
```

## Ordered input roles

Provider field names must be normalized into ordered semantic roles:

```json
{
  "ordinal": 2,
  "role": "motion_reference",
  "path": "references/motion.mp4",
  "content_hash": "sha256:...",
  "media_type": "video/mp4"
}
```

Initial role vocabulary:

- `appearance_reference`
- `motion_reference`
- `composite_appearance_and_motion_reference`
- `start_frame`
- `end_frame`
- `style_reference`
- `mask`
- `source_video`
- `source_audio`
- `workflow`
- `control_signal`
- `other`

Roles are additive. Original provider slot names remain available under
provider-specific details for debugging.

## Evaluation and claims

### Review decision

```json
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
  "evidence_ids": [
    "obs-mixed-rejection-1",
    "obs-mixed-rejection-2"
  ],
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
  "based_on": [
    "inf-mixed-unsupported"
  ]
}
```

The UI must render observations, inferences, and decisions in separate
sections. It must never present an inference as an observed fact.

## Provider mappings

| Provider path | Existing source | Required additions |
|---|---|---|
| Fal through canonical generation executors | Generation manifest v2 | Verify requested/applied features, request ID, endpoint, cost, and failure fixtures |
| OpenAI through canonical generation executors | Generation manifest v2 | Verify reference ordering, quality/size fields, request ID, and redaction |
| Local generation backend | Generation manifest v2 | Record binary/model version and deterministic local identifiers |
| ComfyUI through canonical generation adapter | Generation manifest where available | Preserve workflow hash, template ID, declared bindings, checkpoint/LoRA metadata, and output mapping |
| Direct `vibecomfy.run` | Executor-specific artifacts | Adopt universal manifest; record workflow path/hash and declared parameter bindings |
| Discord/browser POC | `result.json`, screenshots, downloads | Wrap as an executor; always write prompt, parsed request, input roles/hashes, terminal status, response IDs, output hashes, and manifest |
| Arbitrary local tool | Unmanaged files | Require M1 manifest adoption or import through `iteration.experiment_import` |

### ComfyUI-specific rule

Do not pretend every workflow node maps cleanly to canonical generation
parameters. Preserve:

- The complete workflow file and SHA-256 hash.
- Template or workflow identifier.
- Declared user-facing bindings.
- Resolved checkpoint, LoRA, sampler, scheduler, seed, dimensions, and relevant
  node IDs where available.
- Raw non-secret workflow metadata under a provider-specific extension.

The provider-independent review model exposes common fields and keeps the
workflow available for detailed inspection.

### Requested versus applied features

Provider comparisons must display both:

- What the experiment requested.
- What the provider actually applied or dropped.

Two cases are not equivalent merely because their prompt text matches.

## Capabilities

### `iteration.experiment_prepare`

Inputs:

- `experiment`: path to `experiment.json`

Outputs:

- `review.json`
- `diagnostics.json`
- `manifest.json`

Responsibilities:

- Resolve project run IDs and manifest pointers.
- Validate source manifest hashes.
- Normalize provider manifests.
- Probe local media metadata.
- Preserve ordered input roles.
- Detect missing data, duplicates, input echoes, and expired-only references.
- Never modify source runs.

### `iteration.experiment_review`

Inputs:

- `review`: path to normalized `review.json`
- Optional evaluation state

Outputs:

- `review.html`
- Optional deterministic `review.png` in a later milestone.
- `manifest.json`

Responsibilities:

- Render deterministic static HTML using relative or mounted media paths.
- Display playable image, audio, and video inputs and outputs.
- Display exact escaped prompts, parameters, warnings, errors, and timing.
- Show capture gaps and duplicate/input-echo warnings prominently.
- Contain no provider execution logic.

### `iteration.experiment_import`

Inputs:

- Unmanaged run root.
- Optional mapping file.

Outputs:

- Imported `experiment.json`.
- `import.report.json`.
- `manifest.json`.

Responsibilities:

- Import conservatively and idempotently.
- Hash every resolvable artifact.
- Preserve original files and directories.
- Flag ambiguous prompt/run associations instead of guessing.
- Deduplicate recovery fetches by message ID and content hash.

### `iteration.experiment_review_session`

Optional orchestrator:

```text
experiment_prepare
    → experiment_review
    → editorial.human_review
    → finalize evaluation artifacts
```

Reuse `editorial.human_review` for authentication, media range requests,
versioned draft state, and response-schema validation.

## Review-page layout

### Header

- Experiment title and question.
- Hypotheses and current status.
- Case counts by lifecycle status.
- Acceptance rate, median latency, and known capture gaps.
- Provisional conclusions with evidence counts.

### Filters

- Provider/backend.
- Model and mode.
- Factor values.
- Seed.
- Success/failure status.
- Reviewed/unreviewed.
- Included/excluded.
- Duplicate or input-echo warning.

### Case card

```text
┌──────────────────┬────────────────────┬──────────────────┐
│ Ordered inputs   │ Request            │ Outputs          │
│ images / video   │ prompt / params    │ playable media   │
│ semantic roles   │ timing / provider  │ or failure       │
└──────────────────┴────────────────────┴──────────────────┘
│ rubric scores · verdict · notes · provenance · warnings │
└─────────────────────────────────────────────────────────┘
```

### Summary

- Derived acceptance and latency statistics.
- Duplicate-output groups by SHA-256.
- Input-output equality warnings.
- Missing provenance and ambiguous legacy associations.
- Observations, inferences, and decisions rendered distinctly.

## Project layout

New managed experiments should live inside the existing project-run system.
An experiment is represented by an orchestrator or preparation run that
references sibling case runs:

```text
projects/<project>/
  runs/
    <case-run-a>/
      run.json
      manifest.json
      ...
    <case-run-b>/
      run.json
      manifest.json
      ...
    <experiment-run>/
      run.json
      experiment.json
      review.json
      diagnostics.json
      review.html
      review.state.json
      review.final.json
      analysis.json
      conclusions.json
      manifest.json
```

Do not introduce a second lifecycle database beside project runs.

## Rollout plan

### Phase 0: Contract and fixtures

Deliverables:

- `docs/contracts/experiment-contract.md`
- JSON Schema or equivalent Python validation for experiment, review, and
  evaluation records.
- Ordered media-role vocabulary.
- Lifecycle and error vocabulary.
- Redaction rules.
- Representative provider fixtures.

Fixture matrix:

- Fal success and provider failure.
- OpenAI success with image references.
- Local generation success.
- ComfyUI workflow success with declared bindings.
- Discord success, rejection, timeout, interruption, and partial capture.
- Mixed image/video rejection.
- Input video mistakenly returned as output.

Exit criteria:

- Schemas validate every fixture.
- Unknown additive fields round-trip.
- Invalid IDs, unsafe paths, and malformed evidence references fail clearly.
- No fixture contains credentials or live signed URLs.

### Phase 1: Read-only preparation and static review MVP

Deliverables:

- `astrid/core/experiments/`
- `iteration.experiment_prepare`
- `iteration.experiment_review`
- Deterministic `review.json` and `review.html`
- Universal result manifests for both executors.

Exit criteria:

- One page compares Fal, Comfy/local, Discord, and failed cases without
  provider-specific branches in the viewer.
- Every displayed artifact resolves to a run, manifest, and SHA-256 hash.
- Images, audio, and videos render inline.
- Failures and capture gaps appear as first-class cards.
- Duplicate-output and input-echo warnings are correct.

### Phase 2: Structured review and claims

Deliverables:

- Rubric response schema generation.
- `editorial.human_review` integration.
- Versioned draft state and final evaluation output.
- Observation, inference, and decision records with evidence links.

Exit criteria:

- Scores and notes survive reload.
- Final submission validates against the experiment rubric.
- Reviewer identity/type and timestamps are recorded.
- Inferences cannot reference nonexistent observations or cases.
- Facts and inferences are visually distinct.

### Phase 3: Provider capture adoption

Deliverables:

- Discord/browser executor wrapper with complete terminal capture.
- Universal manifest adoption for direct `vibecomfy.run`.
- Verification of canonical Fal, OpenAI, and local generation manifests.
- Provider mapping and requested-versus-applied feature diagnostics.

Exit criteria:

- Success, rejection, timeout, interruption, and partial output all create
  terminal records.
- Exact non-secret requests and ordered inputs are visible.
- Provider request IDs and model_actual values are captured when available.
- Temporary URLs are never the only artifact reference.
- Uploaded inputs cannot be mistaken for generated outputs.

### Phase 4: Legacy import

Deliverables:

- `iteration.experiment_import`
- Import report with confidence and capture gaps.
- Initial importer for `runs/discord-command-poc`.

Migration rules:

1. Never rewrite historical directories.
2. Associate prompts using exact run evidence first.
3. Use seed and chronology only when the association is unique.
4. Mark ambiguous associations instead of selecting one.
5. Classify screenshot-only submissions as unknown unless a terminal provider
   response can be recovered.
6. Deduplicate recovery fetches by response ID and SHA-256.
7. Preserve manual mappings separately from derived mappings.

Exit criteria:

- Import is idempotent and byte-stable.
- Rerunning does not create duplicate cases.
- Ambiguous cases remain visibly ambiguous.
- Existing failures and duplicate outputs are discoverable in HTML.

### Phase 5: Optional orchestration and exports

Possible deliverables after the contracts stabilize:

- Case-matrix expansion and controlled replicate execution.
- Experiment templates.
- Portable review bundles with copied or linked media.
- CSV/JSON export for external analysis.
- AI-assisted evaluation through understanding executors.
- Iteration recap video generated from selected cases.

These are intentionally deferred so execution orchestration does not define the
review contract prematurely.

## Testing strategy

### Contract tests

- Required and additive fields.
- ID validation.
- Ordered media roles.
- Evidence-reference integrity.
- Path traversal and unsafe absolute-path handling.
- Secret and signed-URL redaction.
- Terminal lifecycle validation.

### Normalization tests

- Generation manifest v2.
- Universal manifest with minimal metadata.
- Fal, OpenAI, local, ComfyUI, and Discord fixtures.
- Requested versus applied/dropped features.
- Partial and failed cases.
- Unknown provider extensions.

### Artifact tests

- Input-output SHA equality.
- Duplicate outputs across cases.
- Source-manifest tampering.
- Missing local artifact with expired URL.
- ffprobe metadata extraction.
- Large-file behavior without unnecessary copying.

### HTML tests

- Deterministic JSON and HTML output.
- Image, audio, and MP4 rendering.
- HTTP Range playback through `editorial.human_review`.
- Prompt and provider-text escaping.
- XSS regression fixtures.
- Visible placeholders for unresolved media.
- Responsive case layout.

### Importer tests

- Idempotent reruns.
- Ambiguous prompt association.
- Duplicate recovery fetches.
- Screenshot-only and empty runs.
- Provider rejection, timeout, and interruption.
- Manual mapping precedence.

### Registry and integration tests

- Executor discovery and inspection.
- Universal result-manifest conformance.
- Output exemption-list updates.
- Pack validation.
- Focused end-to-end review session without paid/network calls.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Schema overlap between project runs, thread runs, generation manifests, and experiment records | Make experiment an index over canonical runs; do not duplicate lifecycle fields unnecessarily |
| ComfyUI graph semantics do not normalize cleanly | Preserve workflow file/hash and declared bindings; expose provider details without forcing false equivalence |
| Providers silently drop requested features | Display requested, applied, and dropped features separately |
| Browser/Discord instability and policy constraints | Keep it as an edge adapter with explicit network/policy safety metadata |
| Temporary provider URLs expire | Store local artifacts and hashes; treat URLs as debug-only |
| Input mistaken for output | Exclude uploaded input identities and warn on input-output hash equality |
| Retries create duplicate cases | Model attempts explicitly and group duplicate hashes |
| Human or AI reviewer bias | Record reviewer identity/type, rubric, evidence, and confidence |
| Conclusions overstate weak evidence | Require evidence references and provisional/confirmed/refuted status |
| Large media duplication | Reference content by run and hash; materialize portable copies only on explicit export |
| HTML exposes prompt or provider content | Escape all text, validate paths, and mount only non-sensitive media |

## Acceptance criteria

The first complete release is done when:

1. A single experiment page compares at least one Fal case, one
   ComfyUI/local case, one Discord/browser case, and one failed case.
2. The review renderer contains no provider-specific execution branches.
3. Every displayed input and output traces to a project run, manifest, and
   SHA-256 digest.
4. Ordered input roles and the exact non-secret request are visible.
5. Images, audio, and video play inline.
6. Provider rejection, timeout, interruption, and partial output appear as
   explicit case states.
7. Rubric scores and notes persist through `editorial.human_review`.
8. Observations, inferences, and decisions render separately with evidence and
   confidence.
9. Duplicate-output and input-echo warnings work, including the motion-reference
   video regression from the Discord POC.
10. Legacy Discord runs can be imported without rewriting them or silently
    guessing ambiguous prompts.
11. Static outputs are deterministic and remain usable after provider URLs
    expire.
12. Focused tests, pack validation, executor discovery, and result-manifest
    conformance all pass.

## Recommended first implementation slice

Do not begin with batch execution. Build the read path first:

1. Freeze `experiment.json`, normalized `review.json`, and evaluation schemas.
2. Create representative offline fixtures for Fal, OpenAI, ComfyUI, Discord,
   local generation, and failure cases.
3. Implement `iteration.experiment_prepare`.
4. Implement deterministic `iteration.experiment_review`.
5. Dogfood the page on the current desert-plant runs.
6. Add `editorial.human_review` scoring.
7. Only then adapt provider capture and add execution conveniences.

This order proves the provider-independent boundary before investing in new
execution orchestration.
