`ISSUES`

**Verified clean:** Diff scope is exactly the mandate — `backends/ffmpeg/{command,run,support,text}.py`, `renderer.yaml`, rendering tests, and the seed doc (B6 corrected it to shipped behavior); no other packs touched. Manifest test pins `clip_types: [media, text]` and all feature flags, so yaml/support agreement is test-enforced. Stream-copy veto agrees in both layers (`support.py:859-861` and `command.py`'s `and not inputs.text_overlays`). Fades are overlay-applied, not baked (`max_alpha == 255` test). Live smoke has hang/window/parity guards. 15 fail-closed text cases. No silent engine fallback; Remotion untouched.

**Finding 1 (substantive, fail-open): text extending past the media spine is silently truncated.**
- `support.py:413-424`: `visual_ranges` collects only `clipType == "media"`; no check anywhere (I read `structural_reasons` and `support()` in full) that a text clip's `_text_window` end lies within the visual media coverage.
- `command.py`: output duration is the media concat spine (`concat=n=...[vout]`, no `-shortest`); a PNG input capped at `-t end` cannot extend output. A text clip ending after the last media clip is accepted by support, rendered, and its tail is dropped invisibly.
- This violates the North Star's "support checks never claim more than the backend implements" and output parity vs Remotion (composition duration covers all clips). Fix is small: reject text windows past visual media coverage in `_validate_text_semantics`/`structural_reasons` (fail-closed), matching the `text_only_no_media` precedent.

**Finding 2 (nit): stale comment.** `text.py:_resolve_font_path` carries "visual_understand may ImageFont.load_default() for debug labels; timeline_visualize fail-hard — this path follows timeline_visualize" — references modules unrelated to this backend; garbled. Delete or rewrite.

**Finding 3 (minor, drift risk):** `support.py:_text_wants_bold` hand-mirrors the rasterizer's bold rule (`bold is True or weight >= 600`). Documented as a mirror, but a rasterizer change silently desyncs support. Extract one shared predicate in `text.py`.

**Finding 4 (minor, unverified):** overlay z-order is (track array, `at`, clip index) per `TextOverlaySpec`'s docstring claim of mirroring the Remotion reference, but the reference's stacking lives in `@banodoco/timeline-composition` and I could not verify out-of-`at`-order arrays stack identically. Edge case; worth one parity test if cheap.

All done criteria 1–6 are otherwise met with evidence. Findings 2–4 are non-blocking; Finding 1 is a bounded fail-open that should be closed before this capability is relied on.
0
