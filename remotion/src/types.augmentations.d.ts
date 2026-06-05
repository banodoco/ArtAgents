// Narrow upstream `@banodoco/timeline-composition` types whose canonical
// declarations use `unknown` for `theme_overrides` / `output`. We replace
// the relevant `type` aliases with richer interfaces sourced from our
// locally-generated schema so first-party code (e.g. Root.tsx) can read
// `theme_overrides.visual.canvas` without structural casts.
//
// NOTE: Upstream `TimelineConfig` and `TimelineCompositionProps` are
// declared with `type` (not `interface`), so they cannot be merged via
// `declare module`. Instead we ship this file as the augmentation surface
// only — the actual narrowing in Root.tsx imports `SharedThemeOverrides`
// from `./types.generated` directly. Keeping this file (and adding it to
// tsconfig include via the default `src` glob) documents the contract.

import type {
  SharedThemeOverrides,
  SharedTimelineOutput,
} from './types.generated';

// Type-only helpers that consumers can use to narrow upstream `unknown`
// fields into our richer locally-generated shapes.
export type TimelineThemeOverrides = SharedThemeOverrides;
export type TimelineOutput = SharedTimelineOutput;

// Narrow `theme_overrides.visual.canvas` (which is `Record<string, unknown>`
// on `SharedThemeOverrides.visual`) into the concrete canvas shape used by
// Remotion's `calculateMetadata`.
export interface CanvasOverride {
  fps?: number;
  height?: number;
  width?: number;
}

export interface VisualOverrides {
  canvas?: CanvasOverride;
  [key: string]: unknown;
}
