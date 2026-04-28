/**
 * @banodoco/timeline-composition
 *
 * Sprint 5: real composition + theme-api + plugin registry. The Banodoco
 * CLI render path imports `TimelineComposition` from here; Reigh's
 * TimelineRenderer imports the EFFECT_REGISTRY-style dispatch entries
 * via the codegenned `registry.generated.ts`.
 */
export declare const TIMELINE_COMPOSITION_SCAFFOLD: "sprint-5";
export type TimelineCompositionScaffoldTag = typeof TIMELINE_COMPOSITION_SCAFFOLD;
export { TimelineComposition, HypeComposition } from "./TimelineComposition";
export type { TimelineCompositionProps, HypeCompositionProps } from "./types";
export { composeAnimations, normalizeAnimationReferences, resolveAnimationReferences, } from "./lib/animations";
export { ThemeProvider, useTheme, DEFAULT_THEME, } from "./ThemeContext";
export type { EffectProps, EffectComponent, AnimationReference, AnimationReferenceList, AnimationSlots, AnimationMeta, AnimationPhase, AnimationKind, WrapperAnimationProps, HookAnimationProps, HookAnimationResult, TransitionProps, TransitionReference, TransitionReferenceObject, TransitionComponent, } from "./effects-types";
export type { Theme, RuntimeTheme } from "./ThemeContext";
export { getTimelineDurationInFrames } from "./lib/duration";
export { THEME_PACKAGE_REGISTRY, THEME_PACKAGE_CLIP_TYPES, } from "./registry.generated";
export type { ThemePackageRegistryEntry, ThemePackageClipType, } from "./registry.generated";
//# sourceMappingURL=index.d.ts.map