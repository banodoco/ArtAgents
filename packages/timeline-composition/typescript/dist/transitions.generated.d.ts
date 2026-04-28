import type { TransitionComponent } from './effects-types';
export declare const ACTIVE_THEME_ID: null;
export declare const TRANSITION_IDS: readonly ["cross-fade", "fade"];
export type TransitionId = typeof TRANSITION_IDS[number];
export declare const TRANSITION_REGISTRY: Record<TransitionId, TransitionComponent>;
export declare const TRANSITION_DEFAULTS: Record<TransitionId, Record<string, unknown>>;
export declare const TRANSITION_META: Record<TransitionId, Record<string, unknown>>;
//# sourceMappingURL=transitions.generated.d.ts.map