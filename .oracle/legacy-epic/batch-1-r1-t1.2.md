# Rework T1.2R — Fix contract/schema issues (oracle issues 3–7) [HARD]

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`.
You have `workspace-write` permissions. Python: `PYENV_VERSION=3.11.11`.

## Context

The Batch 1 oracle review found five issues in your T1.2 contracts/schemas
work. The full review is at `.oracle/checkins/batch-1.md`. Fix ONLY these
five issues. Your files: `astrid/core/rendering/{contracts,errors,provenance}.py`,
`astrid/core/rendering/schemas/v1/*.json`, `tests/core/rendering/`,
`docs/contracts/render-backend-v1.md`. Another agent is reworking baseline
characterization in parallel and must NOT touch these paths; a third agent
will fix pack validation + registry afterwards (do not touch
`astrid/core/pack/`).

## Issue 3 — Result-level attachments cannot cross the finalizer wire

`RenderResult` has attachments separate from `VideoArtifact.attachments`,
but `FinalizeRequest` carries only `list[VideoArtifact]` — a standalone
finalizer cannot preserve result-level attachments, and collisions across
segment artifacts are unchecked.

Rework: establish ONE authoritative attachment surface. Cleanest: make
`FinalizeRequest` carry complete per-segment result envelopes (segment
video artifact + its attachments + namespaced fragments) OR move all
attachments onto `VideoArtifact`. Enforce GLOBAL attachment name uniqueness
across segments and preservation through finalization, with round-trip
tests. Update `finalize.json` schema and `docs/contracts/render-backend-v1.md`
accordingly.

## Issue 4 — Provenance cannot represent routing/replay lineage

Current provenance has only singular `resolved_backend`, `source_pack`,
`manifest_digest` keys — a hybrid plan with MULTIPLE renderer invocations
cannot represent resolved identity per segment without collapsing evidence.

Rework: freeze explicit records in provenance v2 (in `provenance.py` and the
result/plan contracts):
- `planner`: `{id, source_pack, manifest_digest, trust_eligibility}`;
- `segments[]`: each with `{window, renderer: {id, source_pack,
  manifest_digest, alias_chain, override, support_decision},
  input_hashes}`;
- `finalizer`: `{id, source_pack, manifest_digest}`;
- top-level `request_digest` and `requested_policy`.
Derive all legacy v1 segment projections from validated frame windows (no
separate inconsistent segment representation). Keep every current v1
top-level projection. Update schemas + docs.

## Issue 5 — Unversioned wire responses + invalid plan topology

`SupportReport`, `RenderPlan`, and `RendererError` lack `schema_version` in
DTOs and schemas — contradicts the contract rule that V1 readers reject
unknown versions. And `RenderPlan` accepts invalid temporal topology.

Rework:
- Add `schema_version` to `SupportReport`, `RenderPlan`, `RendererError`
  (DTOs + schemas + the error branch of `result.json`). Readers must reject
  missing/unknown versions (tests: missing, boolean, malformed, unknown for
  EVERY operation: request, support, plan, finalize, result).
- `RenderPlan` validation: define total-frame/empty-plan semantics; validate
  segment ordering, coverage (segments tile the window/full timeline without
  gaps or overlaps), non-overlap, and canonical FPS consistency. Add tests.

## Issue 6 — JSON Schemas do not match DTOs

`plan.json`, `result.json`, `finalize.json` populated-audio profile branches
omit `required` — all three accept a profile with only `audio_codec: "aac"`
while `RenderProfile` rejects it. `result.json` also accepts contradictory
`video.audio` and top-level audio fields.

Rework:
- Align EVERY duplicated profile definition across schemas (extract a shared
  `profile` definition per schema file, or a `$ref` chain) so schema
  validation matches DTO validation exactly.
- Encode the expressible audio-ownership relationship (audio present in
  profile ⟺ audio ownership consistent; visual-only profile has no audio).
- Reject Windows drive-letter paths (`^[A-Za-z]:`) in artifact paths.
- Add canonical raw fixture JSONs (committed, minimal) for request/result/
  support/plan/finalize.
- Add adversarial schema-vs-DTO parity tests: for each schema, generate a
  battery of valid/invalid JSON cases and assert DTO parse/validation agrees.

## Issue 7 — FFmpeg finalizer ID contradicted and invalid

The plan/tasklist require `rendering.ffmpeg-finalizer`; the contract,
fixtures, and tests freeze `rendering.ffmpeg_finalizer`; the qualified-ID
regex in `contracts.py` forbids the planned spelling.

Rework: resolve ONE canonical spelling. Under the frozen tasklist, the
canonical spelling is `rendering.ffmpeg-finalizer` — make the qualified-ID
validation accept it (id segments: `[a-z0-9][a-z0-9-]*` — hyphens allowed,
no underscores), and align EVERY DTO, schema, document, fixture, and test to
that spelling. Update `docs/contracts/render-backend-v1.md`.

## Acceptance

- `pytest -q tests/core/rendering/test_contracts.py tests/core/rendering/test_schema_roundtrip.py tests/core/rendering` passes (whole dir, all tests green, including your new versioning/topology/parity/attachment/provenance tests).
- `docs/contracts/render-backend-v1.md` reflects issues 3–7 fixes.

Run ONLY those commands. Do not run the full suite, formatters, or linters.
Do NOT modify `astrid/core/pack/`, `astrid/packs/`, production render code,
or files outside `astrid/core/rendering/`, `tests/core/rendering/`,
`docs/contracts/render-backend-v1.md`. Preserve all existing work. Report:
changes made, test results, the canonical finalizer ID you locked.
