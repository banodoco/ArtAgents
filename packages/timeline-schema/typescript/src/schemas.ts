import { z } from "zod";

export const TextAlignment = z.enum(["left", "center", "right"]);
export const TrackKind = z.enum(["visual", "audio"]);
export const TrackFit = z.enum(["cover", "contain", "manual"]);
export const TrackBlendMode = z.enum([
  "normal", "multiply", "screen", "overlay",
  "darken", "lighten", "soft-light", "hard-light",
]);

export const TimelineEffect = z.object({
  fade_in: z.number().optional(),
  fade_out: z.number().optional(),
}).partial();

export const ClipEntrance = z.object({
  type: z.string().optional(),
  duration: z.number().optional(),
  intensity: z.number().optional(),
  params: z.record(z.any()).optional(),
}).partial();

export const ClipExit = ClipEntrance;
export const ClipContinuous = z.object({
  type: z.string().optional(),
  intensity: z.number().optional(),
  params: z.record(z.any()).optional(),
}).partial();

export const ClipTransition = z.object({
  type: z.string(),
  duration: z.number(),
});

export const ClipTransitionReference = z.object({
  id: z.string().optional(),
  type: z.string().optional(),
  duration: z.number().optional(),
  durationFrames: z.number().optional(),
  params: z.record(z.any()).optional(),
}).partial();

export const TextClipData = z.object({
  content: z.string().optional(),
  fontFamily: z.string().optional(),
  fontSize: z.number().optional(),
  color: z.string().optional(),
  align: TextAlignment.optional(),
  bold: z.boolean().optional(),
  italic: z.boolean().optional(),
}).partial();

// SD-024: clipType is an open string at the schema level; effect-id validation
// happens against a registry, not in the schema.
export const TimelineClip = z.object({
  id: z.string(),
  at: z.number(),
  track: z.string(),
  source_uuid: z.string().optional(),
  clipType: z.string().optional(),
  asset: z.string().optional(),
  from: z.number().optional(),
  to: z.number().optional(),
  speed: z.number().optional(),
  hold: z.number().optional(),
  volume: z.number().optional(),
  x: z.number().optional(),
  y: z.number().optional(),
  width: z.number().optional(),
  height: z.number().optional(),
  cropTop: z.number().optional(),
  cropBottom: z.number().optional(),
  cropLeft: z.number().optional(),
  cropRight: z.number().optional(),
  opacity: z.number().optional(),
  text: TextClipData.optional(),
  entrance: ClipEntrance.optional(),
  exit: ClipExit.optional(),
  continuous: ClipContinuous.optional(),
  transition: z.union([ClipTransition, ClipTransitionReference, z.string()]).optional(),
  effects: z.union([z.array(TimelineEffect), z.record(z.number())]).optional(),
  params: z.record(z.any()).optional(),
  generation: z.record(z.any()).optional(),
  // Editor-extension metadata (e.g. scale-bake markers, clip-local shader
  // refs) round-trips through providers; keep the shared schema a superset
  // of Reigh's own TimelineClip type (types/index.ts:384).
  app: z.record(z.any()).optional(),
  // Human-readable clip label (extension-authored "Shot N" names) round-trips
  // through providers; Reigh's patch compiler writes it via clip.update.
  label: z.string().optional(),
  pool_id: z.string().optional(),
  clip_order: z.number().int().positive().optional(),
});

export const TrackDefinition = z.object({
  id: z.string(),
  kind: TrackKind,
  label: z.string(),
  scale: z.number().optional(),
  fit: TrackFit.optional(),
  opacity: z.number().optional(),
  volume: z.number().optional(),
  muted: z.boolean().optional(),
  blendMode: TrackBlendMode.optional(),
  // Editor-extension metadata (e.g. TRACK_SCALE_BAKE_MARKER) round-trips
  // through providers; keep the shared schema a superset of Reigh's own
  // TrackDefinition type (types/index.ts:86).
  app: z.record(z.any()).optional(),
});

export const PinnedShotGroup = z.object({
  shotId: z.string().optional(),
  trackId: z.string().optional(),
  clipIds: z.array(z.string()).optional(),
  mode: z.enum(["images", "video"]).optional(),
  videoAssetKey: z.string().optional(),
  imageClipSnapshot: z.array(z.record(z.any())).optional(),
}).partial();

export const ThemeOverrides = z.object({
  visual: z.record(z.any()).optional(),
  generation: z.record(z.any()).optional(),
  voice: z.record(z.any()).optional(),
  audio: z.record(z.any()).optional(),
  pacing: z.record(z.any()).optional(),
}).partial();

// SD-009: TimelineOutput shape adopted verbatim from Reigh
// (reigh-app/src/tools/video-editor/types/index.ts:128-134).
export const TimelineOutput = z.object({
  resolution: z.string(),
  fps: z.number(),
  file: z.string(),
  background: z.string().nullable().optional(),
  background_scale: z.number().nullable().optional(),
});

export const AssetEntry = z.object({
  file: z.string().optional(),
  url: z.string().optional(),
  etag: z.string().optional(),
  content_sha256: z.string().optional(),
  url_expires_at: z.string().optional(),
  type: z.string().optional(),
  duration: z.number().optional(),
  resolution: z.string().optional(),
  fps: z.number().optional(),
  generationId: z.string().optional(),
  variantId: z.string().optional(),
  thumbnailUrl: z.string().optional(),
}).partial();

export const TimelineConfig = z.object({
  theme: z.string().optional(),
  clips: z.array(TimelineClip),
  tracks: z.array(TrackDefinition).optional(),
  pinnedShotGroups: z.array(PinnedShotGroup).optional(),
  theme_overrides: ThemeOverrides.optional(),
  generation_defaults: z.record(z.unknown()).optional(),
  // Extension-owned project data (project-data.write ops) keyed by extension
  // ID; the SDK contract homes it in TimelineConfig.app.
  app: z.record(z.any()).optional(),
  output: TimelineOutput.optional(),
});

export const Theme = z.object({
  id: z.string(),
  visual: z.record(z.any()).optional(),
  generation: z.record(z.any()).optional(),
  voice: z.record(z.any()).optional(),
  audio: z.record(z.any()).optional(),
  pacing: z.record(z.any()).optional(),
}).passthrough();

export type TimelineClipT = z.infer<typeof TimelineClip>;
export type TimelineConfigT = z.infer<typeof TimelineConfig>;
export type ThemeT = z.infer<typeof Theme>;
export type ThemeOverridesT = z.infer<typeof ThemeOverrides>;
export type TimelineOutputT = z.infer<typeof TimelineOutput>;
export type AssetEntryT = z.infer<typeof AssetEntry>;
