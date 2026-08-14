# Oracle Batch 1 — verify commit 99e6d24c (research only)

Repo: /Users/peteromalley/Documents/reigh-workspace/Astrid-threejs-oracle
Branch: oracle-run-threejs
Run base SHA: b1c5f53c
Batch 1 commit: 99e6d24c

Do not edit any files. Report verified facts only. Cite commands and file paths.

## Tasks

1. Run `git -C /Users/peteromalley/Documents/reigh-workspace/Astrid-threejs-oracle show --stat 99e6d24c` and `git -C /Users/peteromalley/Documents/reigh-workspace/Astrid-threejs-oracle show 99e6d24c -- remotion/package.json remotion/remotion.config.ts remotion/package-lock.json` (lockfile: only the header + the four new deps + @types/react / @types/react-dom if they changed). Also `git show 99e6d24c --name-only`.

2. Confirm remotion/package.json (committed at 99e6d24c) has EXACT versions, no ^ ~ latest:
   - @remotion/three@4.0.455
   - @react-three/fiber@8.18.0
   - three@0.185.1
   - @types/three@0.185.4
   Confirm existing Remotion package versions were not changed.

3. Confirm remotion/package-lock.json lockfileVersion is 3. Confirm the four packages resolved to those exact versions. Note any other package version drift vs b1c5f53c besides the four new deps and (if present) @types/react / @types/react-dom.

4. Confirm remotion.config.ts change is ONLY `Config.setChromiumOpenGlRenderer('angle')` (plus any required import already present). No raw Chromium flags.

5. If @types/react / @types/react-dom changed: report from→to versions. Confirm they are React 18 majors (not 19). Flag any unrelated version drift.

6. Run `git diff --name-only b1c5f53c..99e6d24c -- astrid/core/` — must be empty.
   Run `git diff --name-only b1c5f53c..99e6d24c` and list every path. Flag any PNG, video, node_modules, chrome cache, proof composition, bundle, or other artifact.

7. Run `git status --short` in the repo. Report whether working tree is clean and whether any proof/PNG/node_modules/build artifacts are tracked or untracked.

## Output (<300 words)

```
VERDICT: PASS | FAIL
FILES: <list>
DEPS: <exact or not, quote package.json lines>
LOCKFILE: v<N>
CONFIG: <what changed>
TYPES_REACT: <unchanged | 19.x→18.x with versions>
ASTRID_CORE: empty | <paths>
ARTIFACTS: none | <paths>
DRIFT: none | <packages>
ISSUES: none | numbered list
```
