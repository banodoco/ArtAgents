/**
 * @banodoco/timeline-composition (Sprint 4 scaffold)
 *
 * Real Remotion composition extraction lands in Sprint 5. For now this
 * file exports a tagged placeholder so consumers (and the package's own
 * smoke test) can confirm the package resolves.
 *
 * The functional surface this sprint adds is `@banodoco/timeline-composition/theme-api`.
 * See `./theme-api.ts` for the re-export shape.
 */

export const TIMELINE_COMPOSITION_SCAFFOLD = "sprint-4" as const;
export type TimelineCompositionScaffoldTag = typeof TIMELINE_COMPOSITION_SCAFFOLD;
