# Oracle Batch 6 — docs accuracy (research only)

Repo: /Users/peteromalley/Documents/reigh-workspace/Astrid-threejs-oracle
Commit: fc0c3cee. Do not edit any files.

Verify T6.1/T6.2: `docs/reference/threejs-renderer.md` is accurate against shipped code and matches the style of `docs/reference/render-adapter.md`.

## Read these files

- `docs/reference/threejs-renderer.md` (the new doc — 196 lines)
- `docs/reference/render-adapter.md` (style reference; first ~80 lines + headings)
- `astrid/packs/rendering/backends/threejs/renderer.yaml`
- `astrid/packs/rendering/planners/threejs_hybrid/planner.yaml`
- `astrid/packs/rendering/backends/threejs/run.py` (eligibility / accepted text fields / rejections / identity)
- `astrid/packs/rendering/planners/threejs_hybrid/run.py` (routing + pinned finalizer)
- `remotion/package.json` (exact four deps)
- `remotion/src/ThreeTimelineComposition.tsx` (the 11 text fields it actually maps)
- `tests/packs/rendering/test_production_callers.py` only if the doc mentions callers

## Must be present and accurate

1. Exact 11 text fields: `text.content`, `text.fontSize`, `text.color`, `text.align`, `text.bold`, `params.anchor`, `params.offsetX`, `params.offsetY`, `params.textShadow`, `params.maxWidth`, `params.weight`.
2. Rejection matrix: media/hold/effect/unknown/custom clips, audio tracks or audible clips, effects, transitions, animation declarations, opacity other than `1`, unsupported text/parameter fields, passthrough/none ownership, non-None renderer windows.
3. v1 exclusions: media textures, GLTF/custom meshes/shaders/lights/cameras/fonts, scene/animation DSL, alpha compositing, arbitrary composition IDs, second browser/lock/Node project.
4. Install: `@remotion/three@4.0.455`, `@react-three/fiber@8.18.0`, `three@0.185.1`, `@types/three@0.185.4` + lockfile + ANGLE + Remotion capture host + shared lock.
5. Direct `rendering.threejs` vs opt-in `rendering.threejs-hybrid`; pinned `rendering.ffmpeg-finalizer`; temporal concat only.
6. Provenance: engine `threejs`, fragment `rendering.threejs`, capture_host `remotion`, composition `ThreeTimelineComposition`.
7. Style: headings, tone, length similar to `render-adapter.md` — not a novel, not a changelog dump.

T6.2: report whether any broader skill/README/changelog/STAGE.md/CLI-test was edited in `git diff --name-only 8723ca05..fc0c3cee`. If yes, say whether a gate proved the omission.

## Output (<250 words)

```
DOCS: PASS | FAIL
STYLE: match | mismatch <why>
FIELDS_11: present+accurate | missing/wrong <cite>
REJECTION_MATRIX: complete | missing <what>
V1_EXCLUSIONS: complete | missing <what>
IDENTITY: accurate | wrong <cite>
HYBRID: accurate | wrong <cite>
T6.2_SCOPE: clean | leaked <paths>
ISSUES: none | numbered checkpoint-failing problems only
NOTES: non-blocking
```

Take a position. Cite file:line. Do not hedge.
