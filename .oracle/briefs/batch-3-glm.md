# Executor brief — Batch 3 (megado run ffmpeg-text)

You are the NORMAL EXECUTOR for Batch 3. Mechanical execution only: implement exactly what the task specifies — no scope widening, no refactors beyond the task. The filter strings, input order, and `-t` semantics are DECIDED and empirically verified — do not deviate, do not "simplify" them. If you believe something in the spec is wrong, STOP and report.

## North Star (complete — advance this end state; avoid its anti-patterns)

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


## Your task

## Batch 3 — Filtergraph overlays (module-level; hang-fix argv)

**Depends on:** B2 PASS (`validate_ffmpeg_media_timeline` / `structural_reasons` no longer explode on text).  
**Advances agent-goal:** in-scope #2 (overlay chaining in **one** filtergraph, timing via `enable='between(t,start,end)'`) and in-scope #3 (fade filters on overlay alpha). Done-criterion 1 is not yet live-proven (no run wiring / no real ffmpeg).  
**North Star:** simplest sufficient toolchain; no hang; no silent fallback. E1 hang fix is mandatory. Avoid speculative branches (`-shortest`, `-framerate`, fade zero-guard, inverted PNG-as-main wiring).

### T3 — `astrid/packs/rendering/backends/ffmpeg/command.py`

**Files:**
- `astrid/packs/rendering/backends/ffmpeg/command.py`
- overlay argv tests in `tests/packs/rendering/test_ffmpeg_text.py`

**Changes:**
- `RenderCommandInputs` gains optional `text_overlays: tuple[TextOverlaySpec, ...] = ()` with fields `path`, `at`, `end`, `fade_in`, `fade_out`. Pure: still no file writes.
- Visual concat inputs and asset `-i` list: **`clipType == "media"` only**. Same filter for audio-track collection. `clip_duration_seconds` / visual-duration max stay on media clips only.
- When `text_overlays` is non-empty, **never** take the stream-copy branch (`copy_video_input` stays `None`) so a `[vout]` spine always exists (veto #2; does not depend on `run.py`).
- After asset `-i`s, append each overlay as **`-loop 1 -t {END:.6f} -i {png}`** (PNG inputs last). Then after `[vout]` concat, for overlay input index `N`:
  ```
  [N:v]format=rgba,fade=t=in:st=AT:d=FADE_IN:alpha=1,fade=t=out:st=END-FADE_OUT:d=FADE_OUT:alpha=1[ovK]
  [prev][ovK]overlay=0:0:enable='between(t,AT,END)':format=auto[next]
  ```
  Always emit both fade filters (`d=0.000000` is a legal no-op — **no zero-guard**). Last label stays `[vout]`. `{AT,END,FADE_*}:.6f` like the rest of `command.py`. Filtergraph is one argv element (`";".join`). `enable='between(t,…)'` single quotes stay literal in the Python string (no shell).
- **Do not** use `-shortest`. **Do not** omit `-t`. **Do not** put the PNG on the overlay main side. **Do not** use `-t {END-AT}`. **Do not** add `-framerate`. Input `-t` is overlay **END** (absolute timeline time).
- Overlay order: track array order, then `at`, then clip index (later overlay on top). Media is the base; all text is above it.
- `build_render_command` / `from_data` / facade builders take the overlay list from the caller. Do not rasterize here. Do not call `_parse_fades` here.

**Classification:** `normal` — E1 is fully specified (exact argv, exact filter strings, exact `-t` END, both fades always). Hang risk is pinned by the `-t` assertion now and the live smoke in B5; a precise mechanical brief is enough. Proposed model: GLM 5.3 Flash.

### Checkpoint B3

**Acceptance criteria (oracle verifies):**
1. Argv for a non-empty overlay list contains extra `-loop 1 -t <END> -i` (PNG inputs after assets).
2. **One** `-t` assertion: overlay input index + parsed `-t` value equals overlay END (`:.6f`) — covers both “`-t` is present” and “value is END, not duration”.
3. `overlay=0:0` with spine/prev **before** the overlay input (PNG is secondary).
4. `enable='between(t,…)'` with literal single quotes in the Python string; filtergraph is one argv element.
5. **Both** fade filters are present even when `d=0`.
6. Stream-copy is **not** selected when `text_overlays` is non-empty (`copy_video_input` is `None`).
7. **No** `-shortest` anywhere on that argv.
8. Existing media-only command tests still pass (no overlay inputs; stream-copy still available).
9. Visual/audio asset collection ignores `clipType != "media"` so a text clip does not demand an `asset`.
10. `run.py` / `renderer.yaml` still unchanged. This checkpoint is module-level; auto-route is still not in play.

**Validation commands:**
```bash
python -m pytest tests/packs/rendering/test_ffmpeg_text.py tests/packs/rendering/test_ffmpeg_support.py tests/packs/rendering/test_ffmpeg_backend.py -x -q
```
(Also run any existing command-builder tests that live under `tests/packs/rendering/` — they must stay green.)

**Commit:** on `megado/oracle-run-ffmpeg-text` after PASS.

---



## Execution instructions
1. You are in the worktree on branch `megado/oracle-run-ffmpeg-text` (HEAD b66a83ab = B2). B1 landed `text.py` (helpers), B2 landed support carve-outs. Read `astrid/packs/rendering/backends/ffmpeg/command.py` end-to-end FIRST, especially `build_filter_graph`, `build_render_command`, `RenderCommandInputs`, `from_data`, and how `copy_video_input` (stream-copy branch) is chosen.
2. Implement T3 exactly:
   - `text_overlays: tuple[TextOverlaySpec, ...] = ()` on `RenderCommandInputs` (fields `path`, `at`, `end`, `fade_in`, `fade_out`).
   - Visual concat inputs and asset `-i` list collect `clipType == "media"` ONLY; same filter for audio-track collection; visual-duration max stays on media clips.
   - Non-empty `text_overlays` => NEVER the stream-copy branch (`copy_video_input` stays `None`).
   - Overlay inputs appended AFTER asset `-i`s as `-loop 1 -t {END:.6f} -i {png}` (PNG inputs last).
   - After the `[vout]` concat, chain per overlay input index N:
     `[N:v]format=rgba,fade=t=in:st=AT:d=FADE_IN:alpha=1,fade=t=out:st=END-FADE_OUT:d=FADE_OUT:alpha=1[ovK]`
     `[prev][ovK]overlay=0:0:enable='between(t,AT,END)':format=auto[next]`
     Always BOTH fade filters (d=0.000000 is a legal no-op — no zero-guard). Last label stays `[vout]`. All numbers `:.6f`. Filtergraph remains ONE argv element (`";".join`); the single quotes in `enable='between(t,…)'` stay literal in the Python string.
   - DO NOT use `-shortest`; DO NOT omit `-t`; DO NOT put the PNG on the overlay main side; DO NOT use `-t (END-AT)`; DO NOT add `-framerate`.
   - Overlay order: track array order, then `at`, then clip index (later on top). Media is base; text above.
   - `build_render_command` / `from_data` / facade builders take the overlay list from the caller; no rasterizing here; do not call `_parse_fades` here.
3. Add the argv tests to `tests/packs/rendering/test_ffmpeg_text.py` per the task list: extra `-loop 1 -t <END> -i` (PNG inputs after assets); ONE `-t` assertion (overlay input index + parsed `-t` value == overlay END `:.6f`); `overlay=0:0` with spine/prev before the overlay input; `enable='between(t,…)'`; BOTH fade filters even when d=0; stream-copy NOT selected when overlays present; NO `-shortest`; existing media-only command tests still pass.
4. Validate: `python -m pytest tests/packs/rendering/test_ffmpeg_text.py tests/packs/rendering/test_ffmpeg_support.py tests/packs/rendering/test_ffmpeg_backend.py -x -q` green, AND run any existing command-builder test files under `tests/packs/rendering/` (e.g. test_ffmpeg_compositor.py's non-live command tests) — they must stay green.
5. COMMIT IMMEDIATELY once green: `git add astrid/packs/rendering/backends/ffmpeg/command.py tests/packs/rendering/test_ffmpeg_text.py`, message: `megado B3: text overlay filtergraph (-t END cap, dual fades, spine-first)`. Do not push.
6. Report: files changed, pytest summaries, commit SHA, deviations (none allowed).

## Why the `-t` cap is non-negotiable (empirical, E1)
`-loop 1 -i png` without input duration HANGS after spine EOF (verified: killed at 60-120s, truncated mp4, `moov atom not found`). `-shortest` does NOT fix it. Input `-t` is overlay END (absolute), covering fade-out completion (`st+d = END`). `fade=…:d=0.000000` exits 0. `enable='between(...)'` quoting is ffmpeg's own — literal in Python, subprocess list argv (no shell).
