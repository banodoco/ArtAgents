import type { TimelineClip } from '../types';
export declare const computeMediaTrim: (clip: Partial<Pick<TimelineClip, "from" | "to">>, fps: number) => {
    trimBefore: number;
    trimAfter?: number;
};
//# sourceMappingURL=trim.d.ts.map