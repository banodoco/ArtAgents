/**
 * Stable public theme API (Sprint 4).
 *
 * Re-exports the theme-component-facing surface from the in-tree
 * `tools/remotion/src/` location so theme components can import from
 * `@banodoco/timeline-composition/theme-api` instead of the deep relative
 * `../../../../tools/remotion/src/...` paths.
 *
 * Sprint 5 will move the source itself into this package; until then the
 * re-export is a thin wrapper. The codemod at
 * `tools/scripts/codemod-theme-api-imports.ts` is what migrates theme
 * components onto this surface.
 *
 * The relative imports below intentionally reach outside the package
 * directory — that's the whole point of the wrapper. `rootDir` is left
 * unset in tsconfig.json so tsc accepts the cross-package imports.
 */

// effects.types — type surface for EffectProps, AnimationReferenceList,
// transition types, animation kinds, etc.
export type {
  EffectProps,
  EffectComponent,
  AnimationPhase,
  AnimationKind,
  AnimationEasing,
  AnimationReferenceObject,
  AnimationReference,
  AnimationReferenceList,
  AnimationSlots,
  AnimationMeta,
  BaseAnimationProps,
  WrapperAnimationProps,
  HookAnimationResult,
  HookAnimationProps,
  WrapperAnimationComponent,
  HookAnimationComponent,
  AnimationComponent,
  TransitionReferenceObject,
  TransitionReference,
  TransitionProps,
  TransitionComponentResult,
  TransitionComponent,
} from "../../../../tools/remotion/src/effects.types";

// lib/animations — runtime helpers that compose animation references for
// effect components. composeAnimations is the primary one used by
// themed-effect components.
export {
  composeAnimations,
  normalizeAnimationReferences,
  resolveAnimationReferences,
} from "../../../../tools/remotion/src/lib/animations";
export type {
  NormalizedAnimationReference,
  ResolvedAnimation,
  ComposeAnimationsInput,
} from "../../../../tools/remotion/src/lib/animations";

// ThemeContext — useTheme hook + types theme components use to read
// resolved theme values at render time.
export {
  ThemeProvider,
  useTheme,
  DEFAULT_THEME,
} from "../../../../tools/remotion/src/ThemeContext";
export type { Theme, RuntimeTheme } from "../../../../tools/remotion/src/ThemeContext";
