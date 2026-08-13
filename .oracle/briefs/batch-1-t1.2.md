# Task T1.2 — Freeze language-neutral contracts and schemas [HARD]

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`.
You have `workspace-write` permissions. Python: `PYENV_VERSION=3.11.11`.

## Context

Batch 1 of "Pluggable Timeline Renderers". Read first, in this order:
- `.oracle/plan.md` (the stable plan; resolved decisions 1–12)
- `.megaplan/initiatives/pluggable-timeline-renderers/briefs/pluggable-timeline-renderers.md` (18 locked decisions — FINAL, do not reopen)
- `.oracle/baseline.md` (created by T1.1; may exist)
- `astrid/core/foundation/` for `write_json_atomic` and `sha256_file` helpers
- `astrid/sdk/generation.py` for repo DTO conventions (frozen dataclasses, `_json_safe`)

Your job: define the frozen, language-neutral wire contracts and schemas for
render backends. This is THE contract M2 must build on — be precise.

## Change

Create `astrid/core/rendering/` with:
- `__init__.py` — public names: `RenderRequest`, `SupportReport`,
  `RenderPlan`, `FrameWindow`, `RenderProfile`, `AudioOwnership`,
  `VideoArtifact`, `RenderResult`, `RendererError`, `BackendConfig`,
  `Attachment`.
- `contracts.py` — frozen dataclasses (mirror `sdk/generation.py` style,
  `_json_safe` serialization, `to_dict`), exactly matching the JSON schemas
  below:
  - `FrameWindow`: `start_frame:int >=0`, `end_frame:int > start_frame`
    (half-open `[start,end)`), `fps_rational:(num,den)`, optional
    `source_range` and `speed`.
  - `AudioOwnership`: enum `rendered|passthrough|none`.
  - `RenderProfile`: dimensions (w,h >0), `fps_rational`, time base,
    video codec/profile/level, pixel format, audio codec/sample rate/channel
    layout (optional — visual-only profiles omit audio), `duration_tolerance`.
  - `VideoArtifact`: `path` (contained in workspace), `profile: RenderProfile`,
    `sha256`, `duration_frames`, `audio: AudioOwnership | None`,
    `attachments: dict[str, Attachment]` (named, optional, preserved but not
    interpreted by default finalizers).
  - `Attachment`: `name`, `path`, `kind` (e.g. `alpha|depth|frames|audio-stem|project`), `sha256`.
  - `RenderRequest`: `schema_version` (int, required, unknown → error),
    `timeline_path`, `assets_registry_path | None`, `output_name` (neutral,
    no backend names), `window: FrameWindow | None` (None = full timeline),
    `audio: AudioOwnership | None` (None = backend default),
    `profile: RenderProfile | None` (None = host resolves canonical profile),
    `backend_config: dict[str, dict]` (keyed by QUALIFIED backend id; core
    request carries NO backend-specific top-level fields),
    `metadata: dict[str,str]` (free-form, e.g. project/session ids).
  - `SupportReport`: `supported: bool`, `reasons: list[str]`, `features:
    dict[str, bool|str]` (request-sensitive capability evidence),
    `alternatives: list[str]` (qualified backend ids),
    `backend: str` (qualified id), `backend_version: str|None`.
  - `RenderPlan`: `segments: list[RenderSegment]`, `finalizer: str` (qualified
    id), `profile: RenderProfile`, `reasons: dict[str,str]` (selection reason
    per segment).
  - `RenderSegment`: `window: FrameWindow`, `backend: str` (qualified id),
    `backend_config`, `support: SupportReport | None`, `input_hashes: dict[str,str]`.
  - `RenderResult`: `schema_version`, `video: VideoArtifact`,
    `attachments: dict[str, Attachment]`, `backend_fragments: dict[str, dict]`
    (namespaced, cannot overwrite core keys), `audio_ownership`,
    `normalization: list[str]`, `logs: list[str]` (redacted), `metadata`.
  - `RendererError`: `kind` enum
    (`protocol|unsupported|binary_missing|timeout|interrupted|invalid_artifact|internal`),
    `backend` (qualified id), `message`, `recovery_command: str|None`,
    `details: dict` (JSON-safe).
- `errors.py` — exception hierarchy wrapping `RendererError` plus helpers to
  raise structured failures; unknown/malformed request versions must fail
  with `kind="protocol"`.
- `provenance.py` — v2 provenance assembly: core-owned keys (`schema_version`,
  `engine` (legacy request projection), `output`, `timeline`,
  `assets_registry`, `requested_policy`, `resolved_backend`, `source_pack`,
  `alias_chain`, `override`, `trust_eligibility`, `manifest_digest`,
  `support_decision`, `input_hashes`, `segments`, `artifact_profiles`,
  `audio_ownership`, `normalization`, `finalizer`, `attachments`) PLUS
  backend-owned fragments under a `backend_fragments` namespace that is
  validated to NOT overwrite core keys (a fragment attempting to set a
  core-owned key must be rejected). Keep every current v1 key as a
  compatibility projection (see baseline for the v1 key list).
- `schemas/v1/` — JSON Schemas: `request.json`, `result.json`,
  `support.json`, `plan.json`, `finalize.json`, `renderer-manifest.json`,
  `planner-manifest.json`, `finalizer-manifest.json`. These are the
  language-neutral source of truth. DTO round-trip must match.
- `tests/core/rendering/test_contracts.py` — DTO ↔ JSON round-trip,
  unknown version rejected, invalid frame bounds rejected, duplicate
  attachment names rejected, path traversal in artifact paths rejected,
  backend fragment attempting to overwrite core provenance key rejected.
- `tests/core/rendering/test_schema_roundtrip.py` — every example in the
  schemas validates; DTO `to_dict` output validates against the JSON Schema;
  schema examples parse into DTOs.
- `docs/contracts/render-backend-v1.md` — the frozen contract reference:
  discovery/trust summary, manifest format, the four operations
  (`render|support|plan|finalize` with `--request <abs> --result <abs>`),
  wire schema, lifecycle, configuration namespacing, assets, media/audio
  ownership contract, attachments, support reporting, errors, planning,
  finalization, provenance ownership (core vs backend), cleanup, replay
  inputs, versioning. Preserve locked decisions 1–18 from the epic brief
  verbatim in a section.

Do NOT implement discovery, transport, the service, or backends — later
batches do that. Only contracts, schemas, provenance assembly, and docs.

## Acceptance

- `pytest -q tests/core/rendering/test_contracts.py tests/core/rendering/test_schema_roundtrip.py` passes.
- `pytest -q tests/core/rendering` (whole dir) has no failures.
- `docs/contracts/render-backend-v1.md` exists and is complete.

Run ONLY those commands. Do not run the full suite, formatters, or linters.
Do not modify files outside `astrid/core/rendering/`,
`docs/contracts/render-backend-v1.md`, and `tests/core/rendering/`. Preserve
all existing work; never reset. Report: what you created, test results, and
any contract decisions you made (with rationale).
