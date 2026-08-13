# Batch 1 oracle checkpoint

**Verdict:** PASS
**Commit:** 99e6d24c vs base b1c5f53c
**Flash:** `.oracle/findings/oracle-b1-{diff,proof,critique}.txt`

## PASS
- `99e6d24c` is 7 files, +487/−15. Exact pins: `@remotion/three@4.0.455`, `@react-three/fiber@8.18.0`, `three@0.185.1`, `@types/three@0.185.4` (no `^`/`~`/`latest`). Existing Remotion 4.0.455 unchanged. Lockfile v3; those four resolve exactly.
- `remotion.config.ts` adds only `Config.setChromiumOpenGlRenderer('angle');`. No raw flags.
- `@types/react` `^19.2.14`→`^18.3.12` (18.3.31) and `@types/react-dom` `^19.2.3`→`^18.3.1` (18.3.7) is the documented R3F-8 / React-19 JSX fix. No other version drift.
- `.oracle/findings/remotion-swiftshader.txt` and `webgl-proof.txt` exist. Pinned `open-browser.js` 4.0.455: `'angle'` → `--use-gl=angle`; no `unsafe-swiftshader`. Pillow: 160×90, 4 colors, 1690× (186,0,8). Proof source/PNG untracked. 4 colors = black + red + AA edges.
- `git diff --name-only b1c5f53c..99e6d24c -- astrid/core/` empty. No PNG/video/`node_```
PASS
- Commit 99e6d24c is 7 files, +487/−15. Exact pins: `@remotion/three@4.0.455`, `@react-three/fiber@8.18.0`, `three@0.185.1`, `@types/three@0.185.4` (no `^`/`~`/`latest`). Existing Remotion 4.0.455 unchanged. Lockfile v3; those four resolve exactly.
- `remotion.config.ts` adds only `Config.setChromiumOpenGlRenderer('angle');`. No raw Chromium flags.
- `@types/react` `^19.2.14`→`^18.3.12` (18.3.31) and `@types/react-dom` `^19.2.3`→`^18.3.1` (18.3.7) is the documented R3F-8 / React-19 JSX fix. No other version drift.
- Evidence files exist: `.oracle/findings/remotion-swiftshader.txt`, `webgl-proof.txt`. Pinned `open-browser.js` 4.0.455: `'angle'` → `--use-gl=angle`; no `unsafe-swiftshader` string. Pillow: 160×90, 4 colors, 1690× (186,0,8). Proof source/PNG untracked. 4 colors = black + red + AA edges.
- `git diff --name-only b1c5f53c..99e6d24c -- astrid/core/` is empty. No PNG/video/`node_modules`/Chrome cache/bundle in the commit.
- Chrome Headless Shell was manually unzipped into gitignored `node_modules/.remotion/` (VERSION `149.0.7790.0`). Acceptable for this local-proof batch; `npm ci` extract-zip is Batch 6, not a Batch 1 blocker.
- Flash (OMP deepseek-v4-flash) diff + proof + elegance all PASS. Types alignment justified; lockfile churn proportional; no Batch 2+ leakage.
```

Batch 2 may start.
