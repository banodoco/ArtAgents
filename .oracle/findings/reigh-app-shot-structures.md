# reigh-app video editor — shot/sequence/composition findings

## Key discovery
reigh-app does NOT have nested timelines. The closest building blocks are:

1. PinnedShotGroup: soft-tag overlay on TimelineConfig.pinnedShotGroups, groups clips by shotId
2. EffectLayerSequence: the ONLY "clip contains children" pattern — wraps lower-track content
3. Flat clips[] schema with no nesting

## Detailed findings
- PinnedShotGroup: { shotId, trackId, clipIds[], mode, videoAssetKey, imageClipSnapshot[] }
- No independent time base, no internal tracks, no own duration
- Sequence = a single procedural Remotion clip type (image-jump, title-card), not a composition
- EffectLayerSequence wraps all lower-track content as children, re-offsets via negative from
- Keyframes are clip-local only ({time, value, interpolation})
- Effects: per-clip entrance/exit/continuous/transitions + timeline-wide shader postprocess
- TimelineConfig: { output, clips[], tracks?, pinnedShotGroups?, theme?, theme_overrides? }
- TimelineClip: { at, track, geometry, effects, keyframes } — no children/nested timeline refs
- Render: Remotion Sequence per clip, from={clip.at*fps}, within TimelineRenderer.tsx
- Render routing: browser vs worker/external (render/renderPipeline.ts, lib/renderRouter.ts)

## Implication for our design
To add nested shot timelines, we need to either:
1. Extend PinnedShotGroup to carry an internal TimelineConfig (not just a snapshot)
2. Or add a "composition" clipType that references a sub-timeline
3. Or use the EffectLayerSequence children-wrapping pattern as the nesting mechanism
