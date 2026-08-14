# Megado Batch 1 — Pin dependencies and prove WebGL

You are the EXECUTOR (DeepSeek V4 Flash). Work in `/Users/peteromalley/Documents/reigh-workspace/Astrid-threejs-oracle` (git branch `oracle-run-threejs`). Execute ONLY the tasks below. Do NOT broaden scope. Do NOT edit anything under `astrid/core/`. Do NOT run the full test suite. Do NOT run formatters/linters. This is one batch of a larger pipeline; the oracle gates the result.

Environment: `PATH="$HOME/.nvm/versions/node/v24.17.0/bin:$PATH"` (Node 24) for npm work and the WebGL proof; `PYENV_VERSION=3.11.11` for Python. The `remotion/` project currently has NO node_modules.

Context: Astrid is adding a `rendering.threejs` backend where three.js renders inside the existing Remotion project via `@remotion/three`. This batch installs exact deps and proves headless WebGL works through Remotion's Chromium before any adapter code is written.

## Tasks

### T1.1 — Add exact dependencies
Edit `remotion/package.json` dependencies to add EXACTLY:
- `@remotion/three@4.0.455`
- `@react-three/fiber@8.18.0`
- `three@0.185.1`
- `@types/three@0.185.4`

Do NOT use `latest`. Do NOT change existing remotion/react/react-dom versions. Do NOT add R3F v9.

### T1.2 — npm install + commit lockfile
Run `npm install` from `remotion/` with Node 24 on PATH. Commit `remotion/package-lock.json` (must be lockfileVersion 3). If `npm run typecheck` (T1.6) shows a React 19 types vs React 18 / R3F 8 conflict (the @types/react@19.2.14 dev-dep), align `@types/react` and `@types/react-dom` to React 18 majors and re-install. Record what you did.

### T1.3 — Global ANGLE config
In `remotion/remotion.config.ts`, add `Config.setChromiumOpenGlRenderer('angle');`. No raw Chromium flags. No system-Chrome dependency.

### T1.4 — Inspect the pinned Remotion SwiftShader mapping
Run `rg -n "unsafe-swiftshader|swiftshader" remotion/node_modules/@remotion/renderer/` and save the matching lines + file paths into `.oracle/findings/remotion-swiftshader.txt`. This is evidence of how Remotion 4.0.455 maps the `angle` gl option; do NOT assume main-branch behavior.

### T1.5 — [XHARD] WebGL frame proof
Create a DISPOSABLE proof (do not commit it):
1. A minimal composition file under `remotion/src/` (e.g. `ThreeProof.tsx`) that renders a `<ThreeCanvas>` scene — a bright red rotating cube or a plane with a distinct color — at 160x90, driven by Remotion frame clock (useCurrentFrame for rotation, NO requestAnimationFrame).
2. Register it in `remotion/src/Root.tsx` as `ThreeProof` (temporarily) so `npx remotion still` can find it.
3. Run: `npx remotion still src/index.ts ThreeProof --frame=0 /tmp/three-proof-frame0.png` (or equivalent from remotion/). If WebGL context creation fails, capture the exact error and the flags to fix it; do not give up after one try — check the T1.4 mapping for the right `--gl`/flag combo. The goal: a non-uniform PNG proving WebGL rendered.
4. With PYENV_VERSION=3.11.11, use Pillow (`python3 -c "from PIL import Image; ..."`) to assert: image size 160x90, and more than one distinct pixel color (non-uniform).
5. Remove the disposable proof source + registration + output before checkpoint. `git status` must be clean of proof artifacts.

### T1.6 — Typecheck + bundle
Run `npm run typecheck` and `npm run bundle` from `remotion/` (Node 24 PATH). Both must exit 0.

### T1.7 — Zero-core-edit + cleanliness proof
Run `git diff --name-only <base-sha>..HEAD -- astrid/core/` — must print NOTHING. `git status --short` must show no node_modules, browser cache, proof source, PNG, bundle, or rendered-video artifacts (node_modules must be gitignored — verify; if not, add the right ignore entry, do not commit node_modules).

## Acceptance (what the oracle will verify)
- remotion/package.json has the 4 exact deps; lockfile v3 committed.
- remotion.config.ts has `Config.setChromiumOpenGlRenderer('angle')`.
- `.oracle/findings/remotion-swiftshader.txt` has the pinned mapping evidence.
- The WebGL proof produced a non-uniform 160x90 PNG (evidence: screenshot or the Pillow assertion output saved to `.oracle/findings/webgl-proof.txt`).
- typecheck + bundle pass.
- No astrid/core/ changes; no artifacts committed.

## Protocol
- Commit your work as `megado: batch 1 — pin three.js deps, prove WebGL`.
- Report: what you did, the exact versions installed, the SwiftShader mapping lines, the WebGL proof command + Pillow output, typecheck/bundle exit codes, and the final `git status --short` + `git diff --name-only <base-sha>..HEAD -- astrid/core/` output.
- Keep the report under 400 words. Evidence-first.
