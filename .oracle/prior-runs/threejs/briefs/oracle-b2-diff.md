# Oracle Batch 2 — verify commit 963060ee (research only)

Repo: /Users/peteromalley/Documents/reigh-workspace/Astrid-threejs-oracle
Branch: oracle-run-threejs
Previous checkpoint: 99e6d24c
Batch 2 commit: 963060ee

Do not edit any files. Report verified facts only. Cite commands and file paths with line numbers.

## Tasks

1. Run `git show 963060ee --stat` and `git show 963060ee --name-only`. List every path and +/- line counts.

2. Run `git diff --name-only 99e6d24c..963060ee -- astrid/core/` — must be empty.

3. Run `git diff --name-only 99e6d24c..963060ee` and list every path. Flag any PNG, still, video, fixture, node_modules, chrome cache, remotion/build, remotion/out, or other generated artifact. Allowed production files: remotion/src/ThreeTimelineComposition.tsx (new), remotion/src/Root.tsx (modified). .oracle artifacts are allowed.

4. Read remotion/src/ThreeTimelineComposition.tsx in full. Extract EVERY text/params field the composition reads. Allowed exactly these 11:
   text.content, text.fontSize, text.color, text.align, text.bold,
   params.anchor, params.offsetX, params.offsetY, params.textShadow, params.maxWidth, params.weight
   Flag any invented x/y/width/height, custom fonts, models, lights, shaders, animation config, Drei, useFrame, requestAnimationFrame, Date.now/performance.now, Math.random, network fonts.

   NOTE: an orthographic camera config (frustum left/right/top/bottom/near/far + position) is REQUIRED by T2.1 and is NOT an invented "camera configuration" in the T2.2 forbidden sense. T2.2 forbids caller-selected / timeline-declared camera config, not the composition's own pixel-space camera.

5. Read remotion/src/Root.tsx. Confirm ThreeTimelineComposition is registered (id exactly "ThreeTimelineComposition"). Confirm durationInFrames is clamped >= 1. Confirm it reuses existing getMetadata + DEFAULT_PROPS / canvas-selection / timeline-duration authority (does not invent a second metadata path).

6. Run `git status --short`. Report whether working tree has leftover fixtures/PNGs/stills/bundles that look committed or tracked. Also: `git ls-files '*.png' 'remotion/out/**' 'remotion/build/**' '**/*fixture*three*' '**/ThreeProof*'`

## Output (<300 words)

```
VERDICT: PASS | FAIL
FILES: <list with +/- >
ASTRID_CORE: empty | <paths>
ARTIFACTS: none | <paths>
FIELDS: exact-11 | extra=<...> missing=<...>
FORBIDDEN: none | <list with file:line>
ROOT: registered + clamp>=1 + reused metadata | <gap>
WORKING_TREE: clean-enough | <paths>
ISSUES: none | numbered list
```
