# Independent review pass — Batch 3 checkpoint (oracle-commissioned)

You are an independent reviewer for megado Batch 3 (ffmpeg text overlay filtergraph). Read the code. Do not edit files. Do not re-run the full pytest suite (host already: 100 passed in `test_ffmpeg_text` + `test_ffmpeg_support` + `test_ffmpeg_backend` + `test_ffmpeg_compositor`). You MAY grep, read, and run tiny Python one-liners that inspect argv (no live ffmpeg). Return a structured verdict with file:line evidence.

Bias toward elegance (KISS, YAGNI): flag overengineering, not just bugs. Cut scope that isn't pulling its weight. Verdict is binary: first line exactly `PASS` or `ISSUES`.

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

Module-level filtergraph overlays in `command.py`. Hang-fix is mandatory (E1). Auto-route is NOT in play. `run.py` / `renderer.yaml` must be unchanged. Do not rasterize. Do not call `_parse_fades`. Overlay list comes from the caller.

Commit under review: `84557393` (parent `b66a83ab`).
Diff: `git diff b66a83ab..84557393`
Files that should be in the delta: `astrid/packs/rendering/backends/ffmpeg/command.py` and `tests/packs/rendering/test_ffmpeg_text.py` only.

## What to read

1. `git diff b66a83ab..84557393 -- astrid/packs/rendering/backends/ffmpeg/command.py tests/packs/rendering/test_ffmpeg_text.py`
2. Full current `astrid/packs/rendering/backends/ffmpeg/command.py` (especially `TextOverlaySpec`, `RenderCommandInputs`, visual/audio asset collection, stream-copy branch, overlay argv/filtergraph)
3. New overlay tests in `tests/packs/rendering/test_ffmpeg_text.py`
4. Confirm `run.py` and `renderer.yaml` are not in the diff
5. Confirm `support.py` is not in the diff
6. How visual concat inputs, asset `-i` list, audio-track collection, `clip_duration_seconds`, and visual-duration max treat `clipType != "media"`

## Task contract (T3) — verify implementation matches, hang-fix exact

- `RenderCommandInputs` gains optional `text_overlays: tuple[TextOverlaySpec, ...] = ()` with fields `path`, `at`, `end`, `fade_in`, `fade_out`. Pure: still no file writes.
- Visual concat inputs and asset `-i` list: `clipType == "media"` only. Same filter for audio-track collection. `clip_duration_seconds` / visual-duration max stay on media clips only.
- When `text_overlays` is non-empty, **never** take the stream-copy branch (`copy_video_input` stays `None`) so a `[vout]` spine always exists (veto #2; does not depend on `run.py`).
- After asset `-i`s, append each overlay as `-loop 1 -t {END:.6f} -i {png}` (PNG inputs last). Then after `[vout]` concat, for overlay input index `N`:
  ```
  [N:v]format=rgba,fade=t=in:st=AT:d=FADE_IN:alpha=1,fade=t=out:st=END-FADE_OUT:d=FADE_OUT:alpha=1[ovK]
  [prev][ovK]overlay=0:0:enable='between(t,AT,END)':format=auto[next]
  ```
  Always emit both fade filters (`d=0.000000` is a legal no-op — **no zero-guard**). Last label stays `[vout]`. `{AT,END,FADE_*}:.6f` like the rest of `command.py`. Filtergraph is one argv element (`";".join`). `enable='between(t,…)'` single quotes stay literal in the Python string (no shell).
- **Do not** use `-shortest`. **Do not** omit `-t`. **Do not** put the PNG on the overlay main side. **Do not** use `-t {END-AT}`. **Do not** add `-framerate`. Input `-t` is overlay **END** (absolute timeline time).
- Overlay order: track array order, then `at`, then clip index (later overlay on top). Media is the base; all text is above it. Command.py takes the overlay list from the caller — it must not re-sort, rasterize, or parse fades.
- `build_render_command` / `from_data` / facade builders take the overlay list from the caller. Do not rasterize here. Do not call `_parse_fades` here.

## Acceptance criteria — judge each one PASS or FAIL with evidence

1. Argv for a non-empty overlay list contains extra `-loop 1 -t <END> -i` (PNG inputs after assets).
2. **One** `-t` assertion: overlay input index + parsed `-t` value equals overlay END (`:.6f`) — covers both “`-t` is present” and “value is END, not duration”. Confirm tests actually assert END, not duration, and that production code uses overlay END not `END-AT`.
3. `overlay=0:0` with spine/prev **before** the overlay input (PNG is secondary). Cite the exact filter string. Confirm PNG is never the overlay main side.
4. `enable='between(t,…)'` with literal single quotes in the Python string; filtergraph is one argv element.
5. **Both** fade filters are present even when `d=0`. Confirm there is **no** `if fade > 0` / zero-guard that omits a fade.
6. Stream-copy is **not** selected when `text_overlays` is non-empty (`copy_video_input` is `None`). Media-only empty overlays may still stream-copy.
7. **No** `-shortest` anywhere on that argv (and not emitted by overlay code at all).
8. Existing media-only command tests still pass (no overlay inputs; stream-copy still available). Host already ran them; confirm empty `text_overlays` does not change the media-only argv path.
9. Visual/audio asset collection ignores `clipType != "media"` so a text clip does not demand an `asset`.
10. `run.py` / `renderer.yaml` still unchanged. This checkpoint is module-level; auto-route is still not in play.

## Mandatory hang-fix / wiring hunt (do not skip)

For each, cite the exact code path:

- Overlay input `-t` is `{end:.6f}` (absolute END), never `{end-at}` duration, never omitted.
- `-loop 1` is present per PNG input.
- PNG inputs are appended AFTER asset `-i`s.
- Overlay filter is `[prev][ovK]overlay=0:0:...` (spine first), never `[ovK][prev]`.
- Both fade filters always emitted, including `d=0.000000`.
- No `-shortest` in overlay argv construction.
- No `-framerate` added for PNG inputs.
- Stream-copy veto is `if text_overlays: copy_video_input = None` (or equivalent) independent of `run.py`.
- Media-only visual concat / asset `-i` / audio collection skip non-media clips.
- No rasterize / PIL / `_parse_fades` / font loading in `command.py`.
- `from_data` / facade / `build_render_command` accept overlays from the caller without inventing them.
- Overlay chain last label remains `[vout]`.
- Filtergraph is a single argv element (one `-filter_complex` value, `";".join`).
- Literal single quotes around `between(t,…)` in the Python source string.

## Elegance critique (required)

Flag overengineering, speculative branches, extra config, unused helpers, sorting that the caller already did, zero-guards, inverted wiring, or anything outside T3. Do NOT fail the batch for nits that still meet the contract. ISSUES only for contract holes, hang-risk wiring, or North Star anti-patterns that actually landed.

## Output shape (strict)

First line: `PASS` or `ISSUES`

Then:
- AC 1–10: each PASS or FAIL with file:line evidence (one line each).
- Hang-fix hunt: PASS/FAIL one-liners for the bullets above.
- North Star: one explicit ALIGNED / DRIFT / N/A disposition per principle and per anti-pattern.
- Elegance: at most 5 nits; say "none" if none.
- If ISSUES: numbered list of required fixes. If PASS: "Issues: none."

Cap: 400 words after the first line. Evidence over narrative.
