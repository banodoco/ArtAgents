# Independent review pass — FINAL OVERALL REVIEW (cumulative)

You are an independent reviewer for megado run ffmpeg-text. This is a **cumulative integration gate**, not a batch check-in. Assess the INTEGRATED SYSTEM (batches 1–6 together), not just the latest delta. Do **not** edit files. Do **not** re-run pytest or live ffmpeg (host/oracle owns those). You MAY grep, read, and run tiny Python one-liners that inspect source. Return a structured verdict with file:line evidence.

Bias toward elegance (KISS, YAGNI): flag overengineering, not just bugs. Cut scope that isn't pulling its weight. Verdict is binary: first line exactly `PASS` or `ISSUES`.

A finding is an ISSUE only if it is a real contract miss, interface mismatch, routing lie, silent fallback, out-of-scope mutation, or accumulating complexity that fails a done-criterion / North Star anti-pattern. Nits that still satisfy the frozen plan are not issues.

Working directory: `/Users/peteromalley/Documents/reigh-workspace/Astrid-ffmpeg-oracle`
Base SHA: `c6c505af`. HEAD: `a5fc84f8`. Branch: `megado/oracle-run-ffmpeg-text`.
Cumulative scope: `git diff c6c505af..HEAD -- astrid/packs/rendering/backends/ffmpeg/ docs/ffmpeg-text-extension.md tests/packs/rendering/`
Commits: `0c895638` B1, `b66a83ab` B2, `84557393` B3, `4ea29d62` B4, `5fd08a28` B5, `a5fc84f8` B6.

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

## Frozen done criteria (all required)

1. A media+text timeline renders through `rendering.ffmpeg`: text visible, positioned per anchor/offset, timed, faded per envelope; output plays.
2. `support.py` accepts media+text timelines the backend renders, and remains fail-closed for unsupported features.
3. `renderer.yaml` capabilities match implemented reality (no routing lies).
4. `python -m pytest tests/packs/rendering/ -x -q` passes; no pre-existing test regressions **in touched surfaces**.
5. A short live render smoke test (real ffmpeg invocation on a minimal media+text timeline) succeeds.
6. Docs touched only where behavior changed.

Host evidence (do not re-run):
- Live smoke: `.oracle/evidence/batch-5-live-smoke.txt` (1 passed, 11.12s)
- Authoritative suite: `.oracle/evidence/final-suite.txt` (read it; classify whether any failure is caused by THIS run)
- Per-batch check-ins: `.oracle/checkins/batch-{1..6}.md` all claimed PASS
- Untouched-surface note: `tests/packs/rendering/test_timeline_visualize_parity.py` existed at base `c6c505af` and is **not** in this run's diff. Hard-imports `banodoco_timeline_schema`. Sibling `test_threejs_backend.py` skip-guards the same import.

## What to read (integrated, not latest delta)

1. `astrid/packs/rendering/backends/ffmpeg/text.py` (new)
2. `astrid/packs/rendering/backends/ffmpeg/support.py` (text accept/reject + features)
3. `astrid/packs/rendering/backends/ffmpeg/command.py` (`TextOverlaySpec`, `build_filter_graph`, overlay argv)
4. `astrid/packs/rendering/backends/ffmpeg/run.py` (`_text_overlay_specs`, both render paths, stream_copy relay)
5. `astrid/packs/rendering/backends/ffmpeg/renderer.yaml`
6. `docs/ffmpeg-text-extension.md`
7. `tests/packs/rendering/test_ffmpeg_text.py`, `test_ffmpeg_support.py`, `test_ffmpeg_backend.py`
8. `git diff --name-only c6c505af..HEAD` — out-of-scope files?
9. `git diff --name-only c6c505af..HEAD -- docs/` — only seed-plan file?
10. Confirm `rendering.remotion`, `legacy_hybrid`, `legacy_engine.py`, storyboard compile are **not** in the production delta.

## Mechanical integration checklist — judge each MATCH or MISMATCH with file:line

**A. One-system coherence (text.py ↔ support.py ↔ command.py ↔ run.py ↔ yaml)**

1. `_parse_fades`, `_parse_color`, `_parse_text_shadow`, `_text_window`, `_resolve_font_path` are defined once in `text.py` and reused by support and run. No second fade extractor in `run.py`. Support does not re-split CSS `textShadow`. Support does not rasterize.
2. `TextOverlaySpec` fields (`path, at, end, fade_in, fade_out`) match what `_text_overlay_specs` passes. Overlay order: track array order, then `at`, then clip index.
3. Both render paths (`_protocol_render` and `_render_ffmpeg_media_to_path`) rasterize into a `TemporaryDirectory` and invoke ffmpeg **before** the temp dir is gone. Same helper, not two implementations.
4. Overlay argv: `-loop 1 -t {END:.6f} -i` (END is overlay window end, not duration). `overlay=0:0` with spine **before** overlay input. Both fade filters always emitted (`d=0.000000` legal). `enable='between(t,AT,END)'` with literal single quotes. Filtergraph one argv element. **No** `-shortest` in this overlay chain. **No** `-framerate`. PNG not overlay-main.
5. Visual/audio asset collection is `clipType == "media"` only so text does not demand an `asset`.
6. Stream-copy veto in **two** places, not three: (1) support features force `whole_media`/`stream_copy` false when any text overlay is present; (2) `command.py` never takes stream-copy when `text_overlays` is non-empty. `run.py` only relays `stream_copy_allowed=bool(report.features.get("stream_copy"))`.
7. yaml:
   ```
   clip_types: [media, text]
   media_only: false
   text_overlay: true
   fade_envelope: true
   stream_copy: true
   sequential_audio: true
   ```
   Description is not “media-only”. yaml `stream_copy: true` is a capability (media-only may still copy); support features are request-sensitive. `test_ffmpeg_backend.py` dict-equals the features block.
8. Support accept: one visual media spine + text on same track **and** extra text-only visual tracks. Reject: text-only, extra visual **media**, empty extra visual track, `text-card` (existing `_text_timeline()` test only — no new duplicate), unknown params, missing font (resolver None), media `effects` including fade_in, **text `from`**, **text + x/y/width/height via existing `_POSITION_KEYS` (no second checker)**, **text on audio track**, text with asset/crop/transition/opacity≠1/speed≠1. Text effects other than fade fail via `_parse_fades`.
9. Font: Arial/DejaVu TTF candidates including `Arial Bold.ttf` (space). Missing font → `None`; rasterize `FileNotFoundError`; support `supported=False`. **Never** `ImageFont.load_default()`. Comment names visual_understand vs timeline_visualize.
10. Color: ImageColor for hex/named; hand-parse only `rgba(...)`. Shadow CSS 3- or 4-part; invalid nonempty raises.
11. `_text_window` wraps canonical `_clip_duration_seconds` (import, do not copy body). Positive duration required. Does not use `command.clip_duration_seconds`.
12. Provenance still `engine: "ffmpeg"`. Audio-reactive path unchanged. `-shortest` in `audio_reactive_colour.py` is pre-existing — not this chain.
13. Default routing: `rendering.render` None/`remotion` → `(rendering.ffmpeg, rendering.remotion)` `auto_route=True`. Declaring yaml `text` + support accept **does** flip default auto-route. `legacy_hybrid` unused on default path and not in this delta.

**B. Tests that must exist (presence, not re-run)**

- wrap; bottom-center / top-right anchors; one rasterize bbox-in-region (top-right+offsets); skip if no font
- shadow parse including rgba; nonempty invalid raises
- `_parse_color` hex, named, rgba(0,0,0,0.75)
- `_parse_fades` map, list independent first-match, empty/None → (0,0), unknown/negative/bool raise
- empty content refused; color/shadow/fade/empty tests do not skip
- support accept + features: media_only False, text_overlay True, stream_copy False, whole_media False; fade_envelope True when fades>0 and False with no-effects text
- required rejects listed in A.8; no new text-card reject test
- argv: `-loop 1 -t END` with parsed `-t` == overlay END `:.6f`; overlay=0:0 spine-first; both fades when d=0; no stream-copy; no `-shortest`
- spec-builder unit test with rasterize patched (at/end via `_text_window`, fades via `_parse_fades`)
- live smoke: 4s plate, text at=1 hold=1 fades 0.2/0.2, mid-window t=1.5 not blank, post-END ≈ pre-AT, finite duration, skip if no ffmpeg/font; not intro storyboard; no checksum
- `clip_types == ["media", "text"]` + features dict-equality

**C. Scope / forbidden**

Production delta must NOT include: remotion, legacy_hybrid, legacy_engine, storyboard compile, media hold/fades/transitions, text-card support, drawtext, fonttools/woff2, bundled TTF, PowerGrotesk, load_default(), -shortest on this overlay chain, fade zero-guard, third stream-copy veto in run.py, parallel duration parser, public `_clip_duration_seconds` export, checksum smoke, CI font, CSS split of textShadow in support.py.

`git diff --name-only c6c505af..HEAD -- docs/` = `docs/ffmpeg-text-extension.md` only.

**D. Host suite collection error**

Read `.oracle/evidence/final-suite.txt`. If it errors on `test_timeline_visualize_parity.py` / `banodoco_timeline_schema`: decide with evidence whether THIS RUN caused it (file in the diff? import newly broken by our code?) or it is a pre-existing collection hard-import outside touched surfaces. Do **not** fail the product for a host-env missing optional package unless our diff caused it. Criterion 4's "no pre-existing test regressions in touched surfaces" is the bar. Say so explicitly.

## Output (strict)

First line: `PASS` or `ISSUES`

Then ≤500 words:

1. One-system coherence: MATCH/MISMATCH for A.1–A.13 (cite file:line on mismatches; one-liners ok on matches)
2. Done criteria 1–6: PASS/FAIL/UNPROVEN with the evidence path you used (do not re-run)
3. North Star: ALIGNED or VIOLATED per principle/anti-pattern
4. Elegance: anything that isn't pulling its weight (only ISSUES if it actually fails KISS badly or duplicates a mechanism the plan forbade)
5. Ranked issues (if any) with file:line. If none: `Issues: none.`

Take a position. Do not hedge. Do not propose new scope.
