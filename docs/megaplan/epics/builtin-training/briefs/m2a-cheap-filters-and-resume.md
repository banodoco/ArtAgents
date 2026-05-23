# Milestone 2a: Cheap Filters, State, and Resume Modes

## Outcome

Make `builtin.dataset_build` operable and predictable before adding expensive semantic quality loops. Add deterministic filters, canonical state handling, review control modes, and offline test coverage.

## Scope

In scope:

- Implement the `FilterStage` interface defined in M0 for deterministic filters.
- Add cheap filters:
  - duration
  - resolution
  - black/blank frames
  - exact duplicate content hash
  - per-source clip cap
  - rights/provenance warning or rejection stage using the M0 rights fields
- Add canonical run-state handling so agents know which state file is authoritative.
- Add state versioning/stale-write detection for human review saves.
- Rename review controls to user-facing intent:
  - `--skip-review`
  - `--review-only`
  - resume behavior for interrupted runs
- Add batch review ergonomics that operate through the state contract:
  - accept/reject visible page
  - accept/reject filtered set
  - optional review sampling mode for large candidate sets
- Add a cost/work preview before any expensive or network-backed stages.
- Add offline fixture tests for filter ordering, state persistence, review-only, skip-review, and exact duplicate rejection.
- Preserve M1 config and manifest compatibility.

Out of scope:

- VLM/video-understand/transcript semantic filters.
- Top-up rounds after human rejects.
- Prompt/schema/media invalidation for semantic artifacts.
- GPU training orchestration.

## Locked Decisions

- All tests in this milestone must pass without network access.
- Expensive stages must be disabled or mocked by default in tests.
- `--no-review` should not be introduced; use `--skip-review`.

## Open Questions

- Exact default thresholds for blank-frame detection.
- Whether per-source cap defaults to warning-only or hard rejection.
- Exact default sampling behavior for large review queues.

## Constraints

- Do not delete user media or prior run artifacts automatically.
- Keep file-based state; do not introduce a database.
- Do not change public contracts from M0 without updating downstream briefs.

## Done Criteria

- A config can request deterministic filters in order.
- Filter decisions are recorded in review/provenance data.
- `--review-only` reopens the reviewer on existing `review_data.json` and `review_state.json`.
- `--skip-review` stops after review-data/manifest preparation without opening a browser.
- Batch decisions and review sampling update the same canonical review state as manual per-item decisions.
- Stale review saves fail clearly instead of silently overwriting newer state.
- Resume behavior is documented and tested against a fixture interrupted state.
- Tests cover filter order, source cap, exact duplicate rejection, state persistence, and review modes.

## Touchpoints

- `builtin.dataset_build` from M1.
- Generic review UI and `builtin.human_review`.
- `builtin.clip_extract`
- `tests/`

## Anti-Scope

- Do not add semantic filters here.
- Do not implement top-up recursion here.
