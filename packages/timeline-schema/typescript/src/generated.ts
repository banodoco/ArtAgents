/* eslint-disable */
/**
 * Generated from timeline.schema.json by scripts/emit-ts-types.mjs.
 * Do not edit by hand — regenerate with `npm run gen:types`.
 */

export interface TimelineConfig {
  theme?: string;
  clips: TimelineClip[];
  tracks?: {
    id: string;
    kind: "visual" | "audio";
    label: string;
    scale?: number;
    fit?: "cover" | "contain" | "manual";
    opacity?: number;
    volume?: number;
    muted?: boolean;
    blendMode?: "normal" | "multiply" | "screen" | "overlay" | "darken" | "lighten" | "soft-light" | "hard-light";
    app?: {
      [k: string]: unknown;
    };
  }[];
  pinnedShotGroups?: {
    shotId?: string;
    trackId?: string;
    clipIds?: string[];
    mode?: "images" | "video";
    videoAssetKey?: string;
    imageClipSnapshot?: {
      [k: string]: unknown;
    }[];
  }[];
  theme_overrides?: ThemeOverrides;
  generation_defaults?: {
    [k: string]: unknown;
  };
  app?: {
    [k: string]: unknown;
  };
  output?: TimelineOutput;
}
/**
 * This interface was referenced by `TimelineConfig`'s JSON-Schema
 * via the `definition` "TimelineClip".
 */
export interface TimelineClip {
  id: string;
  at: number;
  track: string;
  source_uuid?: string;
  clipType?: string;
  asset?: string;
  from?: number;
  to?: number;
  speed?: number;
  hold?: number;
  volume?: number;
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  cropTop?: number;
  cropBottom?: number;
  cropLeft?: number;
  cropRight?: number;
  opacity?: number;
  text?: {
    content?: string;
    fontFamily?: string;
    fontSize?: number;
    color?: string;
    align?: "left" | "center" | "right";
    bold?: boolean;
    italic?: boolean;
  };
  entrance?: {
    type?: string;
    duration?: number;
    intensity?: number;
    params?: {
      [k: string]: unknown;
    };
  };
  exit?: {
    type?: string;
    duration?: number;
    intensity?: number;
    params?: {
      [k: string]: unknown;
    };
  };
  continuous?: {
    type?: string;
    intensity?: number;
    params?: {
      [k: string]: unknown;
    };
  };
  transition?:
    | {
        type: string;
        duration: number;
      }
    | {
        id?: string;
        type?: string;
        duration?: number;
        durationFrames?: number;
        params?: {
          [k: string]: unknown;
        };
      }
    | string;
  effects?:
    | {
        fade_in?: number;
        fade_out?: number;
      }[]
    | {
        [k: string]: number;
      };
  params?: {
    [k: string]: unknown;
  };
  generation?: {
    [k: string]: unknown;
  };
  app?: {
    [k: string]: unknown;
  };
  label?: string;
  pool_id?: string;
  clip_order?: number;
}
/**
 * This interface was referenced by `TimelineConfig`'s JSON-Schema
 * via the `definition` "ThemeOverrides".
 */
export interface ThemeOverrides {
  visual?: {
    [k: string]: unknown;
  };
  generation?: {
    [k: string]: unknown;
  };
  voice?: {
    [k: string]: unknown;
  };
  audio?: {
    [k: string]: unknown;
  };
  pacing?: {
    [k: string]: unknown;
  };
}
/**
 * This interface was referenced by `TimelineConfig`'s JSON-Schema
 * via the `definition` "TimelineOutput".
 */
export interface TimelineOutput {
  resolution: string;
  fps: number;
  file: string;
  background?: string | null;
  background_scale?: number | null;
}
/**
 * This interface was referenced by `TimelineConfig`'s JSON-Schema
 * via the `definition` "Theme".
 */
export interface Theme {
  id: string;
  visual?: {
    [k: string]: unknown;
  };
  generation?: {
    [k: string]: unknown;
  };
  voice?: {
    [k: string]: unknown;
  };
  audio?: {
    [k: string]: unknown;
  };
  pacing?: {
    [k: string]: unknown;
  };
  [k: string]: unknown;
}
/**
 * This interface was referenced by `TimelineConfig`'s JSON-Schema
 * via the `definition` "AssetEntry".
 */
export interface AssetEntry {
  file?: string;
  url?: string;
  etag?: string;
  content_sha256?: string;
  url_expires_at?: string;
  type?: string;
  duration?: number;
  resolution?: string;
  fps?: number;
  generationId?: string;
  variantId?: string;
  thumbnailUrl?: string;
}

export type TimelineClipT = TimelineClip;
export type TimelineConfigT = TimelineConfig;
export type ThemeT = Theme;
export type ThemeOverridesT = ThemeOverrides;
export type TimelineOutputT = TimelineOutput;
export type AssetEntryT = AssetEntry;
