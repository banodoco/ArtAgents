import { AbsoluteFill, interpolate, useCurrentFrame } from 'remotion';
import { TRANSITION_DEFAULTS, TRANSITION_REGISTRY, } from '../transitions.generated';
const transitionRegistry = TRANSITION_REGISTRY;
const transitionDefaults = TRANSITION_DEFAULTS;
const isObjectReference = (value) => {
    return typeof value === 'object' && value !== null && !Array.isArray(value);
};
export const resolveTransitionReference = (ref, theme, fps) => {
    if (ref === undefined) {
        return null;
    }
    const id = typeof ref === 'string' ? ref : isObjectReference(ref) ? (ref.id ?? ref.type ?? '') : '';
    if (!id || !transitionRegistry[id]) {
        throw new Error(`Unknown transition id '${id}'`);
    }
    const defaults = transitionDefaults[id] ?? {};
    const params = typeof ref === 'string'
        ? { ...defaults }
        : { ...defaults, ...(ref.params ?? {}) };
    const rawDurationFrames = typeof ref === 'string' ? undefined : ref.durationFrames;
    const durationSeconds = typeof ref === 'string' ? undefined : ref.duration;
    const durationFrames = rawDurationFrames
        ?? (typeof durationSeconds === 'number' ? Math.round(durationSeconds * fps) : undefined)
        ?? (typeof defaults.durationFrames === 'number' ? defaults.durationFrames : 12);
    const component = transitionRegistry[id];
    component({ transitionId: id, params, theme, fps, durationFrames });
    return { id, durationFrames, params };
};
export const TransitionSeries = ({ children }) => {
    return <AbsoluteFill>{children}</AbsoluteFill>;
};
export const CrossFadeLayer = ({ children, role, durationFrames, transitionDurationFrames, }) => {
    const frame = useCurrentFrame();
    const progress = role === 'from'
        ? interpolate(frame, [Math.max(0, durationFrames - transitionDurationFrames), durationFrames], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' })
        : interpolate(frame, [0, transitionDurationFrames], [0, 1], {
            extrapolateLeft: 'clamp',
            extrapolateRight: 'clamp',
        });
    return (<AbsoluteFill style={{ opacity: role === 'from' ? 1 - progress : progress }}>
      {children}
    </AbsoluteFill>);
};
