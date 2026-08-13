Explore in depth: exact compatible dependency versions for embedding three.js in Astrid's Remotion project (remotion/ dir, @remotion/cli based), so a `rendering.threejs` backend can render WebGL scenes through Remotion's capture pipeline.

Investigate and report VERIFIED facts with file/command evidence:

1. **Current versions** in /Users/peteromalley/Documents/reigh-workspace/Astrid-threejs-oracle/remotion/package.json: remotion, @remotion/cli, @remotion/renderer, react, react-dom. Also the node version constraints (engines field, .nvmrc, CI configs).
2. **@remotion/three**: does it exist, latest version, its peer requirements (remotion version, three version, @types/three, react). Is `@remotion/three` compatible with the project's installed remotion 4.x? npm metadata: `npm view @remotion/three@latest peerDependencies dependencies version`, and `npm view remotion@4.0.455 version` (or whatever is installed). Record exact versions that fit together.
3. **React Three Fiber (R3F)**: is R3F needed or does @remotion/three work with raw three.js? (@remotion/three provides <ThreeCanvas> — check if it needs @react-three/fiber as peer.) If R3F is required, its version compatible with react 18.3.1 and three r16x/r17x.
4. **three + @types/three**: latest three version (r16x? r17x?), @types/three matching. WebGLRenderer API surface in that version (alpha, antialias, preserveDrawingBuffer options still valid?).
5. **License implications**: three (MIT), @remotion/three (license?), R3F (MIT), @types/three (MIT). Any copyleft or commercial-restriction gotchas for embedding in an open-source toolkit? (Remotion itself: company license — check the installed remotion package's LICENSE and whether the project already ships it.)
6. **Node minimum**: what Node does the current remotion project require (node_modules/@remotion/* engines, package.json engines)? HyperFrames needs >=22; does remotion 4.x need >=18/20/22?
7. **Install method**: would adding three deps to remotion/package.json + lockfile update be the mechanism (npm install in remotion/)? Any workspace root package.json in the repo (check /Users/peteromalley/Documents/reigh-workspace/Astrid-threejs-oracle/package.json, pyproject.toml for node deps)?

Rank findings by relevance to "can we add @remotion/three + three to the existing remotion project today, and at what exact versions". <300 words. Evidence with exact versions/paths.
