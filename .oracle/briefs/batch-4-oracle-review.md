# Independent review pass — Batch 4 checkpoint (oracle-commissioned)

You are an independent reviewer for megado Batch 4 (run wiring + capability declaration — the routing-truth seam). Read the code. Do not edit files. Do not re-run the pytest suite (host already: packs triple 87 passed; `tests/core/rendering/test_cli.py` 16 passed). You MAY grep, read, and run tiny Python one-liners that inspect source (no live ffmpeg). Return a structured verdict with file:line evidence.

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

T4 and T5 land in the **same commit**; yaml never leads. Wire both ffmpeg render paths through one private spec-builder helper; declare yaml capabilities that match implemented reality. Do not add a third stream-copy veto in run.py. Do not add a second fade extractor. Do not touch planner/`legacy_hybrid`/`service.py`/`test_cli.py`. Do not add an auto-route test.

Commit under review: `4ea29d62` (parent `84557393`).
Diff: `git diff 84557393..4ea29d62`
Files that should be in the delta: `run.py`, `renderer.yaml`, `tests/packs/rendering/test_ffmpeg_backend.py`, `tests/packs/rendering/test_ffmpeg_text.py` only.

## What to read

1. `git diff 84557393..4ea29d62`
2. `astrid/packs/rendering/backends/ffmpeg/run.py` — `_text_overlay_specs`, `_protocol_render`, `_render_ffmpeg_media_to_path`, provenance `engine=`, audio-reactive branch, `stream_copy_allowed=`
3. `astrid/packs/rendering/backends/ffmpeg/renderer.yaml`
4. `tests/packs/rendering/test_ffmpeg_text.py` — W3B-3 spec-builder test
5. `tests/packs/rendering/test_ffmpeg_backend.py` — clip_types + features dict-equality
6. Confirm `support.py`, `command.py`, `test_cli.py`, planner, `legacy_hybrid`, `service.py` are **not** in the diff
7. Confirm `support.py` already accepts media+text and reports `text_overlay` / `fade_envelope` (B2) so yaml declaration is truthful, not leading

## Task contract

### T4 — run.py
- After support succeeds, both `_protocol_render` and `_render_ffmpeg_media_to_path` must: TemporaryDirectory for PNGs, rasterize via helper, pass `TextOverlaySpec`s into the command builder, invoke ffmpeg **before** the temp dir exits.
- Fade numbers from `_parse_fades(clip.get("effects"))` only. No second extractor.
- Keep `stream_copy_allowed=bool(report.features.get("stream_copy"))` as today’s relay. Do **not** re-check overlays in run.py (command.py veto #2 is enough).
- Provenance stays `engine: "ffmpeg"`. Audio-reactive specialization path unchanged (overlays live in the non-specialization branch).
- One private helper is allowed (not a new package).

### T5 — renderer.yaml
```yaml
clip_types: [media, text]
features:
  media_only: false
  text_overlay: true
  fade_envelope: true
  stream_copy: true
  sequential_audio: true
```
- Description is not “media-only”.
- `stream_copy: true` is a **capability** (media-only requests may still copy); support features stay request-sensitive.
- In-commit retarget of `test_ffmpeg_backend.py` clip_types + features dict-equality.
- Do not edit `test_cli.py`. Do not add a `service.py` auto-route test.

## Acceptance criteria — judge each one PASS or FAIL with evidence

1. Both render paths rasterize text to a temp dir, pass specs into the command builder, and invoke ffmpeg before the temp dir is gone. Cite the `with TemporaryDirectory` blocks and the subprocess/runner call **inside** them.
2. Spec fades come from `_parse_fades`; run.py has no second fade extractor.
3. `stream_copy_allowed=bool(report.features.get("stream_copy"))` is unchanged (no overlay re-check in run.py).
4. W3B-3: one unit test on the private spec-builder with rasterize patched; asserts `at`/`end` via `_text_window` and fades via `_parse_fades`.
5. Provenance still records `engine: "ffmpeg"`. Audio-reactive path unchanged.
6. `renderer.yaml` matches the block above; description is not “media-only”.
7. `test_ffmpeg_backend.py` asserts `clip_types == ["media", "text"]` and the features dict-equality. Retarget is in this commit.
8. `test_cli.py` was not edited. Host already passed 16 tests (`clip_types: media` is a prefix of `clip_types: media, text`). Confirm the file is absent from the diff.
9. No planner/`service.py` auto-route test added. Support-accepts-media+text (B2) plus yaml `text` is the routing-truth evidence.
10. T4 implementation is in the same commit as T5 yaml — yaml does not lead. Four files only.

## Load-bearing hunts (do not skip)

For each, cite the exact code path:

- `_render_ffmpeg_media_to_path`: rasterize + `build_render_command_from_data(..., text_overlays=...)` + runner/subprocess.run all inside the same `with TemporaryDirectory`.
- `_protocol_render`: rasterize + `build_render_command(..., text_overlays=...)` + `subprocess.run` all inside the same `with TemporaryDirectory`.
- Audio-reactive `if specialization_spec is not None` branch still calls `audio_reactive_colour.render` with no overlay wiring.
- No `if text_overlays: stream_copy_allowed = False` (or equivalent third veto) in run.py.
- Helper sorts track-array-order, then `at`, then clip index (caller order for command.py).
- `rasterize_text_clip` is called with canvas from `timeline_canvas`.
- No new package; helper is a private function in run.py.
- yaml `stream_copy: true` remains; support remains request-sensitive.

## Elegance critique (required)

Flag overengineering, speculative branches, extra config, unused helpers, a second fade reader, a third stream-copy veto, yaml-leading, auto-route tests, or anything outside T4/T5. Do NOT fail the batch for nits that still meet the contract. ISSUES only for contract holes, routing lies, or North Star anti-patterns that actually landed.

## Output shape (strict)

First line: `PASS` or `ISSUES`

Then:
- AC 1–10: each PASS or FAIL with file:line evidence (one line each).
- Load-bearing hunts: PASS/FAIL one-liners.
- North Star: one explicit ALIGNED / DRIFT / N/A disposition per principle and per anti-pattern.
- Elegance: at most 5 nits; say "none" if none.
- If ISSUES: numbered list of required fixes. If PASS: "Issues: none."

Cap: 400 words after the first line. Evidence over narrative.
