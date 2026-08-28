# Agent goal — FFmpeg text rendering extension (megado run, 2026-08-28)

Advances [North Star](./northstar.md): moves text rendering from the Chrome/webpack/CDN Remotion path into the single-binary FFmpeg path, directly serving "simplest sufficient toolchain" and "offline and fast by default", bounded by "output parity" and the capability/support-check agreement principle.

## Objective
Implement `docs/ffmpeg-text-extension.md` (committed at base SHA `c6c505af`) in this worktree so that timelines containing **media + text clips** render end-to-end through the `rendering.ffmpeg` backend, with Remotion unchanged as the fallback for complex segments.

## Authoritative inputs
- `docs/ffmpeg-text-extension.md` @ `46f1aff0` — the seed plan
- Base code state @ `c6c505af` (custody: `./custody.md`)
- User run declaration (below)

## In scope
1. `astrid/packs/rendering/backends/ffmpeg/renderer.yaml` — declare `text` clip type, `media_only: false`, `text_overlay: true`, `fade_envelope: true`.
2. `astrid/packs/rendering/backends/ffmpeg/run.py` — text clip handling: PIL rasterization to transparent PNG (font, size, color, weight, alignment, position/anchor, maxWidth wrap, textShadow), overlay chaining in ONE filtergraph per section, timing via `enable='between(t,start,end)'`.
3. Fade envelope (`effects.fade_in`/`fade_out`) applied to text overlay alpha.
4. `astrid/packs/rendering/backends/ffmpeg/support.py` — return `supported` for media+text timelines the backend can actually render; stay fail-closed otherwise.
5. Tests covering the new behavior; docs update if behavior/claims change.

## Non-goals
- Transitions between media clips; media fade envelopes beyond what the seed plan's fade-envelope step requires.
- Changes to `rendering.remotion`, the `legacy_hybrid` planner, or any other backend/pack.
- A new cross-backend font-management subsystem (font sourcing stays an ffmpeg-backend-local concern).
- Storyboard compile pipeline changes.

## Settled decisions
- Model declaration (user-pinned 2026-08-28, restated, not asked again): **Grok 4.6** = planner/revision/tasklist/oracle/`[XHARD]` (the judgment slots); **GLM 5.3 Flash** (`openrouter:z-ai/glm-5.3-flash` via hermes launcher) = sense-checkers/explorers/normal executors. No switches without user approval.
- The seed plan doc is the starting plan; it is revised through the megado loop, not rewritten from scratch.
- Worktree/branch per custody.md; never `main`.

## Open boundaries (planner resolves within scope)
- Font sourcing: system fonts vs bundled TTF; PIL cannot load `woff2` directly (fonttools conversion or bundled TTF needed).
- Whether "fade envelope" extends to media clips or is text-overlay-only (seed plan wording covers text overlay alpha).
- Exact wrap/shadow fidelity expectations vs Remotion output (parity bar: visibly equivalent for slide-style text, not pixel-identical browser text).

## Authorization boundaries
- Mutate this worktree only. Commit on `megado/oracle-run-ffmpeg-text` after each passing batch.
- Push at finish: explicit refspec `HEAD:megado/oracle-run-ffmpeg-text` → origin. Never main, never deploy/promote.

## Done criteria (all required)
1. A media+text timeline renders through `rendering.ffmpeg`: text visible, positioned per anchor/offset, timed, faded per envelope; output plays.
2. `support.py` accepts media+text timelines the backend renders, and remains fail-closed for unsupported features.
3. `renderer.yaml` capabilities match implemented reality (North Star: no routing lies).
4. `python -m pytest tests/packs/rendering/ -x -q` passes; no pre-existing test regressions in touched surfaces.
5. A short live render smoke test (real ffmpeg invocation on a minimal media+text timeline) succeeds.
6. Docs touched only where behavior changed (e.g. the seed plan's claims now match reality).

## Final validation commands
- `python -m pytest tests/packs/rendering/ -x -q` (authoritative suite run once by host)
- Live smoke render of a minimal media+text timeline via the ffmpeg backend (command finalized in tasklist)
- `git diff c6c505af..HEAD -- astrid/packs/rendering/backends/ffmpeg/` reviewed by oracle

## Sync/promotion policy
- Commit per batch checkpoint; push branch at completion; no merge to main, no deploy. Stop conditions: `blocked` / `failed` / `undetermined` / `retryable` / `escalate` per megado skill — stop and escalate rather than silently widen scope.
