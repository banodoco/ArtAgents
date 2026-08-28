# Independent review pass — Batch 6 checkpoint (oracle-commissioned)

You are an independent reviewer for megado Batch 6 (docs: claims match shipped behavior). Read the rewritten doc against the shipped code. Do **not** edit files. Do **not** re-run pytest or live ffmpeg (host/oracle owns those). You MAY grep, read, and run tiny Python one-liners that inspect source. Return a structured verdict with file:line evidence.

Bias toward elegance (KISS, YAGNI): flag overengineering, not just bugs. Cut scope that isn't pulling its weight. Verdict is binary: first line exactly `PASS` or `ISSUES`.

A doc claim that does not match shipped code is an issue (routing lies). Nits that are directionally true summaries are not issues unless they misstate behavior.

## North Star (complete — disposition every principle and anti-pattern)

# North Star — Astrid rendering

## Desirable end state
Astrid renders timelines with the simplest toolchain that produces correct output. FFmpeg — one binary, no Chrome, no webpack, no npm tree, no CDN — is the default engine; heavier engines (Remotion) are used only where they genuinely earn their complexity. Engine choice is invisible to the user except as speed and reliability.

## Enduring principles
- **Simplest sufficient toolchain.** Prefer the fewest moving parts that produce correct, good-looking output.
- **Capability-driven routing.** A backend declares what it supports; the router prefers the cheapest capable backend. Support checks are fail-closed and evidence-based — they never claim more than the backend implements.
- **Output parity.** Switching engines must not visibly regress what the user sees: text layout, fonts, position, timing, fades.
- **Offline and fast by default.** Network/CDN dependencies at render time are liabilities, not features.

## Anti-patterns to avoid
- Declaring a capability the backend doesn't implement (routing lies), or implementing without declaring.
- Widening `renderer.yaml` capabilities while `support.py` semantics lag (or vice versa) — the two must agree.
- Speculative abstraction layers, parallel mechanisms where one exists, config surfaces nothing reads.
- Silent fallbacks that hide which engine actually rendered a video.
- Scope creep: this run is about text rendering in the FFmpeg backend — not transitions, not media effects, not a new font management subsystem.

## Scope of this batch

T8 authors ONLY `docs/ffmpeg-text-extension.md`. Claim-correction against shipped code. No planner/Remotion docs. No production-code edits.

Commit under review: `a5fc84f8` (parent `5fd08a28`).
Diff: `git diff 5fd08a28..a5fc84f8`
Files that should be in the delta: `docs/ffmpeg-text-extension.md` only.
Docs from base: `git diff --name-only c6c505af..HEAD -- docs/` must show only `docs/ffmpeg-text-extension.md`.

## What to read

1. `docs/ffmpeg-text-extension.md` (the rewritten doc — verify EVERY claim)
2. `git diff 5fd08a28..a5fc84f8` and `git diff --name-only c6c505af..HEAD -- docs/`
3. `astrid/packs/rendering/backends/ffmpeg/command.py` — `build_filter_graph`, overlay argv (`-loop 1 -t END`), stream-copy gate
4. `astrid/packs/rendering/backends/ffmpeg/run.py` — `_text_overlay_specs`, stream_copy forwarding, no third veto branch, no section loop
5. `astrid/packs/rendering/backends/ffmpeg/support.py` — `_parse_fades`/`_parse_color`/`_parse_text_shadow` reuse, text `from` reject, font fail-closed, `_whole_media_optimization` stream_copy
6. `astrid/packs/rendering/backends/ffmpeg/text.py` — font candidates, no `load_default()`, `_parse_color` ImageColor+rgba, `_parse_text_shadow`, `blur / 2` Gaussian, `_text_window` wrapping `_clip_duration_seconds`, `_parse_fades`
7. `astrid/packs/rendering/backends/ffmpeg/renderer.yaml`
8. `astrid/core/rendering/service.py` — `_translate_legacy_selector`, `_select` auto-route, `LegacyRenderRoutingWarning`, exception kinds `unsupported`/`binary_missing`
9. `tests/packs/rendering/test_ffmpeg_text.py` — `test_live_media_plus_text_smoke` window observation

## T8 claims that MUST be present in the doc AND match shipped code

Judge each MATCH or MISMATCH with file:line on both the doc and the code:

1. Filtergraph lives in `command.py` (`build_filter_graph`), not a section loop in `run.py`.
2. Fades are `clip.effects` via one `_parse_fades` shared by support and run.
3. Font is system Arial/DejaVu TTF, fail-closed (no `load_default()`, no fonttools, no woff2, no PowerGrotesk). Bold requires a bold face or fails. `text.fontFamily` and `italic` ignored.
4. Color is ImageColor + `rgba()` branch; shadow via `_parse_text_shadow`; support does not re-split CSS (calls the helpers).
5. Shadow blur implementation is `blur / 2` Gaussian sigma.
6. Text window wraps canonical `_clip_duration_seconds`; text `from` is rejected.
7. Overlay is full-canvas PNG + `overlay=0:0` with `-loop 1 -t END` (not `-shortest`, not `-t END-AT` in this chain). END is the overlay's absolute window end.
8. Default `rendering.render` (no selector, or legacy `remotion` selector) is ffmpeg-first auto-route; any timeline that passes ffmpeg support renders on ffmpeg.
9. Remotion remains the fallback when ffmpeg fail-closes. Cite the actual `_select` paths: (a) raised `RendererException` kinds `unsupported`/`binary_missing` continue; other kinds re-raise; (b) `report.supported is False` continues to the next target. Confirm the doc's listed fail-closes (text-card / unknown clip kinds, media `hold`, extra visual media tracks, missing font, text `from`, x/y transforms, crops, `speed != 1`, transitions) are real support rejections that trigger that fallback.
10. Other errors surface as hard failures rather than silently re-routing.
11. Warning class name is exactly `LegacyRenderRoutingWarning` and it fires when auto-route picks the first target (ffmpeg).
12. `hybrid` selector maps to `rendering.legacy_hybrid`; unused on the default path; unchanged (not in this run's production delta).
13. Intro storyboard is not the smoke target.
14. Stream-copy: yaml declares `stream_copy: true`; support sets the feature only via `_whole_media_optimization` (probe + not registry-alone; h264/yuv420p, duration/resolution/fps/time base); `build_filter_graph` additionally requires no text overlays, at=0, from=0, full duration, same resolution/fps, no visual adjustments; `run.py` has no third independent veto branch.
15. Live smoke observes the overlay window: mid-window visible (t=1.5), post-END (t=2.6) matches pre-AT plate (t=0.5); finite duration ≤ 4.5s.

## Forbidden claims (absence is required)

- MUST NOT claim the hybrid planner still intercepts text.
- MUST NOT claim yaml/support are "not enough" to change default routing.

## Acceptance criteria — judge each PASS or FAIL with evidence

1. Only `docs/ffmpeg-text-extension.md` is in the B6 commit AND in `git diff --name-only c6c505af..HEAD -- docs/`.
2. Every T8 claim bullet is present in the rewritten doc and matches shipped code (use the 15-point list).
3. Both forbidden claims are absent.
4. No other docs files touched.

## Load-bearing hunts (do not skip)

Cite exact code for:

- `LegacyRenderRoutingWarning` class location and the `warnings.warn(..., LegacyRenderRoutingWarning)` call site (when does it fire?).
- `_select` exception filter: `exc.error.kind not in {"unsupported", "binary_missing"}` vs `not report.supported` continue.
- `_translate_legacy_selector`: None → `"remotion"` → `("rendering.ffmpeg", "rendering.remotion")` with `auto_route=True`; `"hybrid"` → planner `rendering.legacy_hybrid` with no auto_route.
- `GaussianBlur(radius=shadow.blur / 2)`.
- Overlay argv: `["-loop", "1", "-t", f"{overlay.end:.6f}", "-i", ...]`.
- `build_filter_graph` stream-copy `if` conditions (list every conjunct).
- `_whole_media_optimization` probe vs registry fields.
- Protocol render path in `run.py`: does it forward `stream_copy_allowed` or does `build_render_command` re-query support? Is either a "third run.py branch"? Directionally-true summary vs lie.
- Grep `run.py` for `section` (must be absent).
- Grep the doc for `intercept`, `not enough`, `load_default`, `fonttools`, `woff2`, `PowerGrotesk`, `-shortest`, `END-AT`, `legacy_hybrid`.

## Elegance critique (required)

Is this one-file claim-correction the smallest sufficient docs change? Flag leftover v1 lies, redundant mechanism descriptions, or over-specified internals that aren't pulling weight. Do not demand extra docs files.

## Output format (strict)

```
PASS
or
ISSUES

AC 1: PASS/FAIL — evidence
AC 2: PASS/FAIL — one line per T8 claim MATCH/MISMATCH with file:line
AC 3: PASS/FAIL — forbidden-claim hunt
AC 4: PASS/FAIL — docs name-only

North Star: one line per principle/anti-pattern ALIGNED/VIOLATED.

Elegance: <80 words.
Issues: none or a numbered list of evidence-backed mismatches only.
```

Cap 400 words. Take a position. Do not hedge.
