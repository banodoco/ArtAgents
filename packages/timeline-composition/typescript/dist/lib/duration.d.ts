import type { TimelineClip, TimelineConfig } from '../types';
export declare const secondsToFrames: (seconds: number, fps: number) => number;
export declare const getClipSourceDuration: (clip: TimelineClip) => number;
export declare const getClipTimelineDuration: (clip: TimelineClip) => number;
export declare const getSanitizedPlaybackRate: (speed: TimelineClip["speed"]) => number;
export declare const getSanitizedVolume: (volume: number | undefined, fallback?: number) => number;
export declare const getClipDurationInFrames: (clip: TimelineClip, fps: number) => number;
export declare const getTimelineDurationInFrames: (timeline: TimelineConfig, fps: number) => number;
//# sourceMappingURL=duration.d.ts.map