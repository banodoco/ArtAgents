# @banodoco/timeline-ops

Pure surgical CRUD operations on `TimelineConfig` (from `@banodoco/timeline-schema`).
Shared between the Banodoco CLI and the Reigh editor's `ai-timeline-agent`.

Hard rules for ops in this package:

- **Pure.** Take a `TimelineConfig` (and op-specific args), return a new
  `TimelineConfig`. No I/O, no Supabase, no async, no globals.
- **No tool-name renames.** Reigh's `ai-timeline-agent/tools/registry.ts`
  re-exports each op under its existing tool name (`add_clip`, `move_clip`,
  etc.) — the LLM-visible tool schema is byte-equivalent across the
  extraction. Renames break chat.
- **Glue stays Reigh-side.** Anything that needs Supabase clients, file
  uploads, generation calls, or LoRA RPCs lives in
  `reigh-app/supabase/functions/ai-timeline-agent/tools/` and is not
  eligible for this package.

## First batch (Sprint 3)

- `addClip(timeline, clip, position?)`
- `removeClip(timeline, clipId)`
- `moveClip(timeline, clipId, newPosition)`
- `setClipProperty(timeline, clipId, propertyName, value)`
- `setClipTime(timeline, clipId, startTime, duration?)`
- `setTimelineProperty(timeline, propertyName, value)`

These are the surgical-CRUD subset of the existing
`ai-timeline-agent/tools/timeline.ts` ops. Future sprints may extract more
once they're confirmed pure.

## Build / test

```
cd packages/timeline-ops
npm install
npm run build
npm test
```
