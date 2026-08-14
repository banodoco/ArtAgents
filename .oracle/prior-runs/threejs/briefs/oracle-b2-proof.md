# Oracle Batch 2 — camera, layout, visibility, disposal, proof (research only)

Repo: /Users/peteromalley/Documents/reigh-workspace/Astrid-threejs-oracle
Commit: 963060ee
Do not edit any files. Report verified facts only. Cite file:line.

## Tasks

1. Read remotion/src/ThreeTimelineComposition.tsx completely.

2. Camera + layout
   - Confirm the scene uses <ThreeCanvas> / Canvas with `orthographic` and a camera config that sets frustum fields (left/right/top/bottom/near/far) plus position. This is the R3F 8 API: Canvas `orthographic` constructs THREE.OrthographicCamera; frustum fields set manual=true. Do NOT require a <OrthographicCamera makeDefault> child — that is R3F 9-only and was correctly removed.
   - Confirm world units map 1:1 to output pixels. Centered-frustum (left=-w/2, right=w/2, top=h/2, bottom=-h/2) is ACCEPTABLE if the layout math uses the same origin (documented in the file). Origin-at-corner (left=0,right=w,top=0,bottom=h) is also acceptable if consistent. Fail only on a half-canvas offset bug (layout origin disagrees with frustum).
   - Confirm theme background is applied as the scene background and shows with zero clips.

3. Frame visibility
   - Clip shown only when currentTime is in [at, at+hold) — half-open. Driven from Remotion useCurrentFrame + useVideoConfig fps only. No useFrame / rAF / wall-clock.

4. Z ordering
   - Deterministic. Reversed track order: later visual track nearer the camera (on top). Cite the formula.

5. Disposal
   - Textures / materials / geometry disposed on unmount (useEffect cleanup and/or useMemo disposal). Cite the cleanup.

6. Read `.oracle/findings/threejs-composition-proof.txt`. Confirm it records:
   - bg-only frame 0: distinct_colors=1, non_bg_samples=0
   - text frame 0: distinct_colors>1, non_bg_samples>0 (HELLO)
   - late-clip frame 0: distinct_colors=1, non_bg_samples=0 (clip at 0.5s not visible at t=0)
   Host used 160x90@24fps, bg #1a2e3f. Do not re-render stills.

7. Optional sanity (read-only): grep remotion/node_modules/@react-three/fiber/dist/events-*.esm.js for the camera apply path if cheap. Confirm Canvas `orthographic` + frustum fields is the R3F 8 path. Do not fail if grep is messy; the host already verified events-*.esm.js:1834,1875,789-798.

## Output (<300 words)

```
VERDICT: PASS | FAIL
CAMERA: orthographic pixel-space + consistent origin | <bug>
BACKGROUND_ZERO_CLIPS: yes | no
VISIBILITY: [at, at+hold) from frame/fps | <bug>
Z_ORDER: reversed tracks, later nearer | <bug>
DISPOSAL: yes (cite) | missing
PROOF_FILE: matches host numbers | mismatch
R3F8_CAMERA: sound | unsound
FORBIDDEN_RUNTIME: none | <useFrame/rAF/random/Drei/...>
ISSUES: none | numbered list
```
