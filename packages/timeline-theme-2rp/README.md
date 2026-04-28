# @banodoco/timeline-theme-2rp

First peer-dep theme package for `@banodoco/timeline-composition`. Sprint 5
deliverable. Ships:

- `theme.json` — theme metadata (color, type, motion, canvas).
- `src/effects/<clipType>/component.tsx` — Remotion components for
  `section-hook`, `art-card`, `cta-card`, `resource-card`.
- `src/effects/<clipType>/{schema,defaults,meta}.json` — per-effect
  schema/defaults/meta companions (mirror the Banodoco in-tree shape).

## Install

```sh
npm install @banodoco/timeline-theme-2rp
```

The package resolves to a `file:` link in this monorepo / convergence
workspace; no npm publishing happens this sprint.

## Discovery

`@banodoco/timeline-composition`'s `gen-registry.ts` codegen walks
`node_modules/@banodoco/timeline-theme-*` and emits one entry per
`src/effects/<clipType>/component.tsx`. After install, run
`npm run gen-registry` in the composition package (or rely on the CI
shim's pre-test hook).

## Notes

- The original `themes/2rp/` directory remains under banodoco-workspace
  for `tools/effects_catalog.py` discovery (which still scans the in-tree
  path during Banodoco CLI render). Sprint 5 intentionally duplicates
  the components into this peer-dep package; de-duplication is a
  follow-on (point `effects_catalog.py` at `packages/timeline-theme-*/`).
