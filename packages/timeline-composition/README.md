# @banodoco/timeline-composition

Scaffold (Sprint 4). The eventual home of:

- `HypeComposition.tsx` and the rest of the Remotion composition.
- `EFFECT_REGISTRY` / `TRANSITION_REGISTRY` dispatch.
- The stable theme public API.

Sprint 4 ships **only the scaffold** plus the `./theme-api` sub-path —
re-exports of `effects.types`, `lib/animations`, and `ThemeContext` from
the in-tree `tools/remotion/src/` location. Theme components migrate off
the deep relative imports onto `@banodoco/timeline-composition/theme-api`
via the codemod at `tools/scripts/codemod-theme-api-imports.ts`.

The actual composition extraction lands in Sprint 5 (Phase 4d).

## Build / test

```
cd packages/timeline-composition
npm install
npm run build
npm test
```
