# Milestone 1 — Agent Navigation Spine

## Outcome

Implement the durable `rendering.timeline_visualize` executor and
`astrid timelines visualize` façade through a complete agent journey:

```text
project → timeline → authored shot or explicit range
        → clip context → verified original media
```

The output must include legible time-scaled and linear PNG/SVG pages, shared
semantic and geometry models, a frozen root snapshot, stable qualified ids, and
executable parent/child/sibling/source actions. This milestone establishes the
contract; it does not complete transcript mapping or the final multi-pass VLM
release gate.

Read and follow the overall brief and locked architecture decision:

- `.megaplan/initiatives/timeline-visualization/briefs/timeline-visualization.md`
- `.megaplan/initiatives/timeline-visualization/decisions/timeline-visualization-plan.md`

Do not redesign decisions already locked there.

## Required scope

1. Add `rendering.timeline_visualize` with declared pack metadata, executor
   documentation, universal result behavior, and a thin SDK-backed timeline
   CLI command.
2. Normalize project/timeline/track/shot/range/group/clip/asset/transition/
   effect/animation/warning data without mutating source state.
3. Implement project, timeline, shot, range, clip, asset, and timestamp focus.
4. Implement time-scaled and linear layouts from one geometry model, plus
   deterministic PNG, SVG, overview, filmstrip, and active-stack outputs.
5. Emit the mandatory core bundle:
   `manifest.json`, `ground-truth.json`, `view-map.json`,
   `action-index.json`, `asset-index.json`, an initially valid
   `transcript-index.json`, `diagnostics.json`, and `reading-guide.md`.
6. Make one post-root operation authoritative:
   `--from-view <manifest> --focus <qualified-ref>`, with
   `TL01@00:12.000` for arbitrary frozen timestamps and optional `--context`
   and `--neighbors` where valid.
7. Lock event head/version/hash, projection and registry hashes, transcript
   hashes when present, local media hashes, and the root stable-id map.
   Children read the frozen normalized snapshot and never renumber.
8. Expose verified original local media as the primary resource. Label derived
   source cards, thumbnails, source approximations, and rendered samples
   explicitly. Never fetch remote media or leak credential-bearing URL query
   strings.
9. Implement explicit unavailable states and exactly one recovery action for
   invalid focus, invalid hashes, missing/changed media, and conflicting scope.
10. Preserve current dirty/untracked baseline work and keep all project/timeline
    sources byte-identical.

## Agent UX invariants

- Images carry only compact qualified ids, breadcrumb, snapshot badge, and
  `FOCUS`/`SOURCE`/`TEXT` cues.
- `action-index.json` carries authoritative `argv` arrays and expected result
  scopes; long shell commands do not depend on image OCR.
- Every child has an exact parent and deterministic sibling/wider/narrower
  relations.
- Pinned shots are authored `SH` objects; ordinary windows are explicit `RG`
  objects.
- Asset roles are explicit:
  `timeline_media`, `generation_reference`, `generation_output`,
  `thumbnail_only`, and `rendered_sample`.
- Display ids are illegal without `--from-view`; project actions always use
  timeline-qualified ids.
- A `refresh_root` action is the only path from a frozen lineage to current
  project state.

## Fixtures and proof

At minimum cover:

- the 16-second `desert-plant-growth/plant-growth-storyboard`;
- multi-track captions/effects/audio and real overlaps;
- pinned shot with contextual layers;
- tiny clips, long gaps, and 500-clip pagination;
- multiple timelines with colliding local ids;
- verified full-resolution, changed, missing, remote, and thumbnail-only
  sources;
- a version-7 root after current state advances to version 8;
- empty/tombstoned timelines.

Tests must prove model, geometry, schema, deterministic output, direct
executor/managed CLI equivalence, source immutability, frozen lineage, exact
original-media selection, and reversible root-to-source traversal.

## Handoff artifact

Before completion, write
`docs/architecture/timeline-visualization-agent-navigation.md` describing the
implemented schemas, display-id grammar, snapshot fields, action relations,
CLI examples, source-integrity states, and fixture ids. It is the binding
input to milestone two. Update the locked plan only if implementation evidence
requires a narrow, documented correction.

## Done

This milestone is done only when a fresh agent can start from CLI stdout,
discover the root manifest, traverse to a segment, clip, and exact original
image using generated actions, and return to the same frozen parent; all
focused automated tests pass; and the handoff contract matches the code.
