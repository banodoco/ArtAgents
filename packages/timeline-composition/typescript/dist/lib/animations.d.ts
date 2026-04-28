import type { ReactNode } from 'react';
import type { AnimationComponent, AnimationPhase, AnimationReferenceList } from '../effects-types';
import type { RuntimeTheme } from '../ThemeContext';
import type { TimelineClip } from '../types';
export type NormalizedAnimationReference = {
    id: string;
    durationFrames?: number;
    easing?: string;
    params: Record<string, unknown>;
};
export type ResolvedAnimation = NormalizedAnimationReference & {
    component: AnimationComponent;
    kind: 'wrapper' | 'hook';
    phase: AnimationPhase;
    durationFrames: number;
};
export type ComposeAnimationsInput = {
    clip: TimelineClip;
    refs: AnimationReferenceList | undefined;
    phase: AnimationPhase;
    content: ReactNode;
    text?: string;
    theme: RuntimeTheme;
    fps: number;
    elapsedFrames: number;
};
export declare const normalizeAnimationReferences: (refs: AnimationReferenceList | undefined) => NormalizedAnimationReference[];
export declare const resolveAnimationReferences: (refs: AnimationReferenceList | undefined, phase: AnimationPhase) => ResolvedAnimation[];
export declare const composeAnimations: ({ clip, refs, phase, content, text, theme, fps, elapsedFrames, }: ComposeAnimationsInput) => ReactNode;
//# sourceMappingURL=animations.d.ts.map