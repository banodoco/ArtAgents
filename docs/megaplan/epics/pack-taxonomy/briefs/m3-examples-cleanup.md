# M3: Examples And Demo-Pack Cleanup

## Outcome

Remove hidden scaffold noise from the runtime pack surface and preserve useful
teaching packs as examples.

## Scope

In:

- Delete `astrid/packs/clip_tools`.
- Delete `astrid/packs/video_tools`.
- Move `file_summarizer`, `text_digest`, and `text_review` out of runtime pack
  discovery into `examples/packs/` or an equivalent examples-only location.
- Remove irrelevant duplicate `clip_extract` executors from moved text example
  packs.
- Keep `media.clip_extract` as the canonical product clip extraction surface.
- Update docs and tests that mention these packs.
- Regenerate capability index if needed.

Out:

- Do not touch `builtin`/`external` physical migration.
- Do not redesign the text example workflows beyond removing accidental media
  noise.
- Do not delete golden fixtures if they still document useful authoring
  patterns.

## Locked Decisions

- `clip_tools` and `video_tools` are scaffold waste, not product packs.
- `file_summarizer`, `text_digest`, and `text_review` are examples or teaching
  artifacts, not Astrid runtime product packs.
- Duplicate `clip_extract` copies in text packs are accidental noise.

## Touchpoints

- `astrid/packs/clip_tools`
- `astrid/packs/video_tools`
- `astrid/packs/file_summarizer`
- `astrid/packs/text_digest`
- `astrid/packs/text_review`
- `examples/packs/`
- docs that mention hidden/example packs
- capability index if regenerated
- pack discovery/validation tests

## Done Criteria

- Runtime pack discovery no longer exposes the demo/text packs.
- Example packs remain available as examples if useful.
- No duplicate `clip_extract` product capability remains outside canonical
  `media`.
- Tests and docs pass after updates.
