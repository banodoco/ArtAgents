# Independent review pass — Batch 2 checkpoint (oracle-commissioned)

You are an independent reviewer for megado Batch 2 (ffmpeg text support). Read the code. Do not edit files. Do not re-run the full pytest suite (host already: 77 passed). You MAY grep, read, and run tiny Python one-liners if they clarify a parser/feature question. Return a structured verdict with file:line evidence.

Bias toward elegance (KISS, YAGNI): flag overengineering, not just bugs. Verdict is binary: PASS or ISSUES.

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

This batch is support-check only. `renderer.yaml` must still declare media-only. Overlay/run is later. Auto-route is NOT in scope. Support may accept media+text before yaml declares it (yaml never leads).

Commit under review: `b66a83ab` (parent `0c895638`).
Diff: `git diff 0c895638..b66a83ab`
Files that should be in the delta: `astrid/packs/rendering/backends/ffmpeg/support.py` and `tests/packs/rendering/test_ffmpeg_support.py` only.

## What to read

1. `git diff 0c895638..b66a83ab -- astrid/packs/rendering/backends/ffmpeg/support.py tests/packs/rendering/test_ffmpeg_support.py`
2. Full current `astrid/packs/rendering/backends/ffmpeg/support.py`
3. New/changed tests in `tests/packs/rendering/test_ffmpeg_support.py` (search for text, fade_envelope, unknown_clip_kind, text-card)
4. Confirm `astrid/packs/rendering/backends/ffmpeg/renderer.yaml` still media-only
5. Confirm `command.py` / `run.py` were not changed in this commit
6. Confirm `unknown_clip_kind` fixture retarget (was `clipType: "text"` on a visual media clip; must now be `text-card` or another non-text non-media type)
7. Confirm `test_support_rejects_non_media_timeline` is unchanged (no new dedicated `text-card` reject test)

## Task contract (T2) — verify implementation matches, fail-closed

- Accept `clipType == "text"` on a visual track. Require `text.content` non-empty string.
- Reject text `from` explicitly (key presence, including `from: 0`).
- Validate duration through `_text_window` / `_clip_duration_seconds` (positive duration; `hold: 0` fails). After the `from` reject, a `to`-without-`hold` clip has implicit `from=0`, so duration equals `to`. Do not treat `to` as an absolute timeline end.
- Allow `params` keys `{anchor, offsetX, offsetY, maxWidth, textShadow, weight}` only (unknown param → reject).
- Carve text `effects` out of the generic `_EFFECT_KEYS` rejection and run `_parse_fades`; any `ValueError` is a support reason. Media clips still reject all `effects` (including `fade_in`). Other `_EFFECT_KEYS` (`entrance`, `exit`, `continuous`, `keyframes`) stay rejected on text. `text-card` and every other non-media type stay rejected.
- If `text.color` is present, parse with `_parse_color`. If `params.textShadow` is nonempty, parse with `_parse_text_shadow` — do NOT split the CSS string to reach a color. Bad color or malformed shadow → `supported=False`.
- Visual-media spine unchanged: exactly one visual track that carries media clips, gapless, no overlap, media still needs `from`/`to` (not `hold`). Extra visual tracks allowed iff they contain only `text` clips. Empty extra visual tracks reject. Text may overlap media in time. Text may sit on the media visual track.
- Reject: text on an audio track; text with `asset`; text with x/y/width/height/crop/transition/opacity≠1/speed≠1. x/y/width/height stay on the existing `_POSITION_KEYS` path — do NOT add a second checker. Do NOT punch a hole in `_POSITION_KEYS` for text.
- If any text clip is present, resolve a font path; missing font → reason, `supported=False`. Never rasterize at support time. Never `load_default()`.
- Request-sensitive features when any text overlay is present: `media_only: False`, `text_overlay: True`, `fade_envelope: <any text clip whose _parse_fades pair has a value > 0>`, and force `whole_media` / `stream_copy` false (veto #1). Media-only requests keep `media_only: True` and current stream-copy logic.

## Acceptance criteria — judge each one PASS or FAIL with evidence

1. Support accepts one visual media + one/N text overlays on the same visual track, AND extra text-only visual tracks.
2. On an accept path WITH fades > 0: `report.features["media_only"] is False`, `["text_overlay"] is True`, `["stream_copy"] is False`, `["whole_media"] is False`, and `["fade_envelope"] is True`. Not a full-dict equality on `features`.
3. One no-effects text accept (media + text, no `effects` / empty effects) asserts `report.features["fade_envelope"] is False` (and still media_only False, text_overlay True, stream_copy False, whole_media False).
4. Support still rejects: text-only (no visual media); extra visual MEDIA track; empty extra visual track; text effects other than fade (unknown key via `_parse_fades`); unknown params; missing font (patch resolver to `None`); media `effects.fade_in`; text `from`; text + `x`/`y`/`width`/`height`; text on an audio track. The x/y and audio-track cases are required.
5. No new `text-card` reject test in the new list. Coverage remains `test_support_rejects_non_media_timeline`.
6. `unknown_clip_kind` retarget landed in this commit; that parametrized case still fail-closes.
7. Support does not rasterize. Support calls `_parse_text_shadow` on nonempty shadow (no CSS split) and `_parse_fades` for text effects (no second extractor).
8. `renderer.yaml` still declares media-only. `command.py` / `run.py` overlay path not required yet. Do not treat default `astrid render` auto-route as in-scope.

## Mandatory fail-closed hole hunt (do not skip)

For each of these, cite the exact code path that rejects, and confirm it is NOT silently ignored:

- text `from` (including `from: 0`)
- text `x`/`y`/`width`/`height` via existing `_POSITION_KEYS` (no second checker, no hole punched for text)
- text on an audio track
- text with `asset`
- unknown params
- non-fade text effects (`entrance`/`exit`/`continuous`/`keyframes` and unknown keys via `_parse_fades`)
- missing font (resolver returns None → supported=False; no load_default)
- media `effects` still fully rejected (including `fade_in`) — no hole punched in media effects rejection
- empty extra visual track
- extra visual MEDIA track
- text-only timeline (no visual media)

Also confirm:
- `_POSITION_KEYS` is not filtered/skipped for text
- `_EFFECT_KEYS` carve-out is text-only; media still hits the generic reject
- no CSS split to extract shadow color
- no rasterize / PIL Image / save PNG in support.py
- `text-card` is NOT newly accepted

## Elegance critique (KISS / YAGNI)

Flag:
- speculative helpers/layers/config that nothing needs
- parallel parsers instead of reusing `_parse_fades` / `_parse_text_shadow` / `_parse_color` / `_text_window`
- duplicated duration/window logic
- test overkill that isn't pulling its weight
- yaml declared early (routing lie)
- silent ignore of keys that should reject

Do NOT fail the batch for nits that do not violate AC, North Star, or fail-closed contract. If you find overengineering that still meets AC, record it as a nit, not an ISSUES verdict, unless it is a real contract hole.

## Output format (strict)

First line exactly: `PASS` or `ISSUES`

Then:

```
AC1: PASS|FAIL — <one sentence + file:line>
AC2: ...
AC3: ...
AC4: ... (name each reject case PASS/FAIL)
AC5: ...
AC6: ...
AC7: ...
AC8: ...

HOLES: none | list any fail-closed hole with file:line
POSITION_KEYS: intact | hole (evidence)
MEDIA_EFFECTS: intact | hole (evidence)

NORTH STAR:
- Simplest sufficient toolchain: ALIGNED|DRIFT — <one line>
- Capability-driven routing: ALIGNED|DRIFT — <one line>
- Output parity: ALIGNED|N/A|DRIFT — <one line>
- Offline and fast: ALIGNED|N/A|DRIFT — <one line>
- Anti-pattern routing lies: ALIGNED|DRIFT
- Anti-pattern yaml/support lag: ALIGNED|DRIFT (support-ahead-of-yaml is allowed this batch; yaml-ahead is not)
- Anti-pattern speculative layers: ALIGNED|DRIFT
- Anti-pattern silent fallbacks: ALIGNED|DRIFT
- Anti-pattern scope creep: ALIGNED|DRIFT

ELEGANCE: ALIGNED | ISSUES — <nits vs contract holes>
ISSUES: none | numbered list with evidence
```

Cap the whole response at 500 words. Evidence over narrative. Take a position; do not hedge.
