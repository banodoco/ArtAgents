import type { ReactElement, ReactNode } from 'react';
import type { TransitionReference } from '../effects-types';
import type { RuntimeTheme } from '../ThemeContext';
export type ResolvedTransition = {
    id: string;
    durationFrames: number;
    params: Record<string, unknown>;
};
export declare const resolveTransitionReference: (ref: TransitionReference | undefined, theme: RuntimeTheme, fps: number) => ResolvedTransition | null;
export declare const TransitionSeries: ({ children }: {
    children: ReactNode;
}) => ReactElement;
export declare const CrossFadeLayer: ({ children, role, durationFrames, transitionDurationFrames, }: {
    children: ReactNode;
    role: "from" | "to";
    durationFrames: number;
    transitionDurationFrames: number;
}) => ReactElement;
//# sourceMappingURL=transitions.d.ts.map