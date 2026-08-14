Explore in depth: the Chrome Headless Shell environment wart — Remotion 4.0.455's `extract-zip` leaves a partial extraction (only ABOUT/LICENSE), requiring a manual unzip + a VERSION marker file, on every fresh checkout. This is a real developer-experience inelegance flagged after the three.js epic.

Context: In the epic, `npm ci` + first `npx remotion` on a fresh checkout left `node_modules/.remotion/chrome-headless-shell/mac-arm64/` as a 1.5MB stub (ABOUT + LICENSE.headless_shell only, no binary). The fix was: manually unzip the downloaded zip + write `VERSION` = `149.0.7790.0` at `mac-arm64/VERSION` (the path `readVersionFile` reads in `@remotion/renderer/dist/browser/BrowserFetcher.js`). Remotion then accepts the local shell without re-downloading.

Investigate and report VERIFIED facts with file:line evidence:

1. **The root cause**: in `node_modules/@remotion/renderer/dist/browser/BrowserFetcher.js` (v4.0.455), find the `downloadBrowser` → `extract-zip` flow. Why does extraction leave only ABOUT/LICENSE? Is it an extract-zip bug, an EEXIST/overwrite issue, a path-length issue, or a known remotion issue? Search remotion's GitHub issues via web if needed (query: remotion extract-zip chrome-headless-shell mac partial extraction).
2. **The version check**: `readVersionFile` reads `<downloads-folder>/VERSION`. `getRevisionInfo` checks `revision.local && existsSync(executablePath)` then `readVersionFile() === TESTED_VERSION`. What EXACTLY must be on disk for remotion to skip the download: the binary at which path, and VERSION at which path? Quote the exact paths from get-download-destination.js.
3. **Reproduce on THIS machine**: is the wart present in the current checkout? Check `/Users/peteromalley/Documents/reigh-workspace/Astrid/remotion/node_modules/.remotion/` — is the shell complete (193MB, has chrome-headless-shell binary) or a stub? Run `npx remotion compositions src/index.ts` from remotion/ and observe: does it re-download every time or accept the local shell?
4. **Fix options ranked by elegance**:
   (a) a repo-level npm `postinstall` script in `remotion/package.json` that detects the stub and repairs it (re-run extract or copy from a cache) — ships in the repo, fixes every fresh checkout;
   (b) a `remotion/scripts/ensure-chrome-shell` script invoked by an existing make target or documented in README/docs;
   (c) pin `@remotion/renderer` to a version where extract works (is there a fixed 4.0.x? check npm `npm view @remotion/renderer versions` for 4.0.45x-4.0.5xx and any changelog about extract-zip);
   (d) document the manual fix (current state);
   (e) pre-download via a checked-in script using `@puppeteer/browsers`.
   For each: does it actually fix the root cause, what does it add to the repo (scripts? deps? docs?), does it break CI or the wheel, and the elegance tradeoff.
5. **CI implication**: the wheel smoke + `make ci` run remotion typecheck/bundle but NOT full renders (renders are per-backend tests). Would a postinstall fix affect CI? Would a fresh `npm ci` in CI hit the same stub?

Rank findings by relevance to "make a fresh checkout render without manual intervention". <350 words. Evidence with file:line + observed behavior. Recommend ONE option.
