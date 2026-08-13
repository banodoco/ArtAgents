# Oracle Batch 1 — verify SwiftShader mapping + WebGL proof (research only)

Repo: /Users/peteromalley/Documents/reigh-workspace/Astrid-threejs-oracle
Do not edit any files. Report verified facts only.

## Tasks

1. Read `.oracle/findings/remotion-swiftshader.txt` and `.oracle/findings/webgl-proof.txt` and `.oracle/findings/batch-1-exec.txt`. Confirm both evidence files exist and contain the claimed content.

2. Independently re-check the pinned Remotion 4.0.455 mapping. Search `remotion/node_modules/@remotion/renderer` with `rg -n --no-ignore 'unsafe-swiftshader|swiftshader' remotion/node_modules/@remotion/renderer/`. Read `remotion/node_modules/@remotion/renderer/dist/open-browser.js` getOpenGlRenderer. Confirm:
   - swangle → ['--use-gl=angle','--use-angle=swiftshader']
   - angle-egl → ['--use-gl=angle','--use-angle=gl-egl']
   - vulkan → ['--use-angle=vulkan', ...]
   - null → []
   - else → [`--use-gl=${renderer}`] so 'angle' → ['--use-gl=angle']
   - NO string `unsafe-swiftshader` exists in this pinned build
   Quote the function. Do not infer from newer Remotion source.

3. WebGL proof honesty:
   - webgl-proof.txt should record Pillow: size (160,90), distinct_colors > 1, red cube pixels.
   - Confirm no proof source/composition remains under remotion/src (search for ThreeProof, ThreeCanvas proof files).
   - Confirm no PNG of the proof is tracked: `git ls-files '*.png' '**/three-proof*' '**/ThreeProof*'`
   - Is "4 distinct colors" consistent with a red cube on black? (black + red + AA edge colors.)

4. Chrome Headless Shell risk: executor says extract-zip left Chrome Headless Shell partially extracted; they manually unzipped into `node_modules/.remotion/chrome-headless-shell/mac-arm64/` and wrote VERSION=149.0.7790.0. Check whether that directory exists now, whether VERSION matches, and whether any of it is tracked (`git ls-files '**/chrome-headless-shell/**' '**/.remotion/**'`). Batch 1 scope is local proof; CI parity is Batch 6. State whether this is a Batch-1 blocker or a future-batch note.

5. Confirm remotion.config.ts currently contains setChromiumOpenGlRenderer('angle').

## Output (<300 words)

```
VERDICT: PASS | FAIL
SWIFTSHADER_FILE: exists + matches | missing/mismatch
WEBGL_FILE: exists + matches | missing/mismatch
MAPPING: confirmed | mismatch (quote)
UNSAFE_SWIFTSHADER: absent | present
PROOF_PNG_TRACKED: no | yes
PROOF_SOURCE_REMAINS: no | yes
PILLOW: <size, colors, red pixels>
COLORS_HONEST: yes | no
CHROME_UNZIP: exists/not; tracked/not; blocker-now | future-batch
ISSUES: none | numbered list
```
