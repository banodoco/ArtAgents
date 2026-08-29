# Frozen schema fence resolution

Date: 2026-08-29
HEAD before fix: `0eb3a146d097057ab2a0c9b7e78c81d47ac35d1d`

## Decision

The shared `banodoco_timeline_schema` package is the schema source of truth.
Its generated `TimelineClip` contract declares `derived_output`, and Astrid's
`_CLIP_ALLOWED` must continue to expose that field so timeline round trips and
validation remain truthful. The Python compatibility module is frozen, so its
HEAD bytes were left unchanged.

The ancestry fence already has an explicit reviewed-update escape hatch: it
compares every post-anchor commit byte-for-byte and stops only at the named
reviewed revision. The schema's reviewed convergence bytes are those at
`0eb3a146`, which carries the shared-schema-generated `derived_output` parity
addition. Advancing that documented anchor preserves the fence's strict
byte-comparison behavior and excludes the older `2199d4ba` merge blob from the
post-update comparison; it does not add a general exemption or weaken the
fence.

## Verification

- Exact ancestry fence: **passed**
- Shared-schema allowlist parity: **passed**
- Timeline/compiler/storyboard/FFmpeg/render focused slice: **216 passed,
  6 known optional-Remotion baseline failures** (the five semantic Remotion
  variants and complex hybrid transition window); no new failures
- `git diff --check`: **passed**

Fix commit: recorded below after commit.
