# Batch 2 oracle checkpoint

**Verdict:** PASS
**Commit:** 963060ee vs previous 99e6d24c
**Flash:** `.oracle/findings/oracle-b2-{diff,proof,critique}.txt`

```
PASS
- `git show 963060ee --stat`: 5 files, +533/−16. Production: `remotion/src/ThreeTimelineComposition.tsx` (new, +415), `remotion/src/Root.tsx` (+57/−16). Also `.oracle/briefs/batch-2.md`, `.oracle/findings/batch-2-exec.txt`, `.oracle/findings/threejs-composition-proof.txt`. No PNG/still/video/fixture/`node_modules`/build/out.
- `git diff --name-only 99e6d24c..963060ee -- astrid/core/` empty.
- Field set is the exact 11 (`ThreeTimelineComposition.tsx:215–234`). Local `x`/`yTop` are canvas draw coords from anchor/offset, not invented clip fields. No lights/shaders/Drei/useFrame/rAF/Date/random/network fonts. Fixed sans-serif stack (`:67`). MeshBasicMaterial unlit.
- Camera is R3F 8: `<ThreeCanvas orthographic came```
PASS
- Commit `963060ee` is 5 files, +533/−16: `remotion/src/ThreeTimelineComposition.tsx` (new, +415), `remotion/src/Root.tsx` (+57/−16), plus three `.oracle` texts. `git diff --name-only 99e6d24c..963060ee -- astrid/core/` empty. No PNG/still/video/fixture/`node_modules`/build committed.
- Exact 11 fields at `ThreeTimelineComposition.tsx:215–234`. Local `x`/`yTop` are canvas coords from anchor/offset, not invented clip fields. No lights/shaders/Drei/`useFrame`/rAF/Date/random/network fonts. Fixed sans-serif (`:67`). `MeshBasicMaterial` unlit.
- R3F 8 camera: `<ThreeCanvas orthographic camera={{left:-w/2,right:w/2,top:h/2,bottom:-h/2,near,far,position:[0,0,10]}}>` (`:395–407`). Centered frustum matches full-canvas plane at (0,0) + flipY. Flash confirmed `events-*.esm.js:1875` OrthographicCamera and `:1882–1885` frustum → `manual=true`.
- Background always on (`:409`, `resolveBackground` never null). Visibility `[at, at+hold)` from `frame/fps` (`:321–337`). Z: `z = -(N-1-trackIndex)` (`:362–363`) — later track nearer. Disposal in `useEffect` (`:373–378`).
- Root: id `ThreeTimelineComposition` (`Root.tsx:85–88`); `Math.max(1, getTimelineDurationInFrames(...))` (`:68–71`); shared `getMetadata` + `DEFAULT_PROPS`.
- Host proof (`threejs-composition-proof.txt`, 160×90@24, `#1a2e3f`): bg-only 1/0; text 52/567; late-clip (at=0.5s) 1/0. Host typecheck+bundle 0; Flash re-ran `tsc --noEmit` clean.
- Flash (OMP `deepseek-v4-flash`): `.oracle/findings/oracle-b2-{diff,proof,critique}.txt` all PASS. No Batch 3+ leak.
```

Batch 3 may start.
