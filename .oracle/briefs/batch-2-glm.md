# Executor brief — Batch 2 (megado run ffmpeg-text)

You are the NORMAL EXECUTOR for Batch 2. Mechanical execution only: implement exactly what the task specifies — no scope widening, no refactors beyond the task. Architectural decisions are pinned; follow them literally. If you believe something in the spec is wrong or impossible, STOP and report instead of improvising.

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

## Batch 2 — Support check (module-level; not an auto-route checkpoint)

**Depends on:** B1 PASS.  
**Advances agent-goal:** in-scope #4 and done-criterion 2 (`support.py` accepts media+text the backend will render, fail-closed otherwise). Does **not** yet satisfy done-criterion 1 (no overlay/run) or 3 (yaml still media-only — **intentionally**; yaml never leads). Auto-route is **not** truthful after this batch alone.  
**North Star:** capability-driven routing and fail-closed support. Avoid routing lies (do not declare yaml yet); avoid yaml/support lag (support may accept before yaml, but yaml stays behind implementation, not ahead); avoid silent fallbacks (reject text `from`, `x`/`y`, missing font — no silent ignore, no `load_default()`). Shared `_parse_fades` / `_parse_text_shadow` close the silent-no-fade / silent-bad-shadow hole.

### T2 — `astrid/packs/rendering/backends/ffmpeg/support.py`

**Files:**
- `astrid/packs/rendering/backends/ffmpeg/support.py`
- `tests/packs/rendering/test_ffmpeg_support.py`
- accept cases may live in `tests/packs/rendering/test_ffmpeg_text.py` if that avoids a second fixture dialect in the support file

**Changes:**
- Accept `clipType == "text"` on a visual track. Require `text.content` non-empty string.
- **Reject text `from` explicitly** (key presence, including `from: 0`).
- Validate duration through `_text_window` / `_clip_duration_seconds` (positive duration; `hold: 0` fails). After the `from` reject, a `to`-without-`hold` clip has implicit `from=0`, so duration equals `to`. Do not treat `to` as an absolute timeline end.
- Allow `params` keys `{anchor, offsetX, offsetY, maxWidth, textShadow, weight}` only (unknown param → reject).
- Carve text `effects` out of the generic `_EFFECT_KEYS` rejection and run `_parse_fades`; any `ValueError` is a support reason. Media clips still reject all `effects` (including `fade_in`). Other `_EFFECT_KEYS` (`entrance`, `exit`, `continuous`, `keyframes`) stay rejected on text. `text-card` and every other non-media type stay rejected.
- If `text.color` is present, parse with `_parse_color`. If `params.textShadow` is nonempty, parse with `_parse_text_shadow` — do **not** split the CSS string to reach a color. Bad color or malformed shadow → `supported=False`.
- Visual-media spine unchanged: **exactly one visual track that carries media clips**, gapless, no overlap, media still needs `from`/`to` (not `hold`). Extra visual tracks allowed **iff they contain only `text` clips** (hype’s `brand` / caption tracks). Empty extra visual tracks reject. Text may overlap media in time. Text may sit on the media visual track.
- Reject: text on an audio track; text with `asset`; text with x/y/width/height/crop/transition/opacity≠1/speed≠1. x/y/width/height stay on the existing `_POSITION_KEYS` path — do **not** add a second checker. Do not punch a hole in `_POSITION_KEYS` for text.
- If any text clip is present, resolve a font path; missing font → reason, `supported=False`. Never rasterize at support time.
- Request-sensitive features when any text overlay is present: `media_only: False`, `text_overlay: True`, `fade_envelope: <any text clip whose _parse_fades pair has a value > 0>`, and force `whole_media` / `stream_copy` false (veto #1). Media-only requests keep `media_only: True` and current stream-copy logic.
- **In-commit retarget:** `unknown_clip_kind` currently sets `clipType: "text"` on the visual media clip — change that fixture to `text-card` (or another non-text non-media type) in this same commit.
- Leave `test_support_rejects_non_media_timeline` as-is.

**Classification:** `normal` — fail-closed carve-outs against a pinned accept/reject list; parsers already exist in T1. Proposed model: GLM 5.3 Flash.

### Checkpoint B2

**Acceptance criteria (oracle verifies):**
1. Support accepts one visual media + one/N text overlays on the same visual track, **and** extra text-only visual tracks.
2. On an accept path **with fades > 0:** `report.features["media_only"] is False`, `["text_overlay"] is True`, `["stream_copy"] is False`, `["whole_media"] is False` (PREEXEC-2: both halves of veto #1), and **W3B-1** `["fade_envelope"] is True`. Not a full-dict equality on `features`.
3. **W3B-1:** one no-effects text accept (media + text, no `effects` / empty effects) asserts `report.features["fade_envelope"] is False` (and still `media_only False`, `text_overlay True`, `stream_copy False`, `whole_media False`).
4. Support still rejects: text-only (no visual media); extra visual **media** track; empty extra visual track; text effects other than fade (unknown key via `_parse_fades`); unknown params; missing font (patch resolver to `None`); media `effects.fade_in`; **text `from`**; **text + `x`/`y`/`width`/`height`**; **text on an audio track**. The x/y and audio-track cases are required.
5. **W3B-5:** no new `text-card` reject test in the new list. Coverage remains `test_support_rejects_non_media_timeline`.
6. `unknown_clip_kind` retarget landed in this commit; that parametrized case still fail-closes.
7. Support does not rasterize. Support calls `_parse_text_shadow` on nonempty shadow (no CSS split) and `_parse_fades` for text effects (no second extractor).
8. `renderer.yaml` still declares media-only. `command.py` / `run.py` overlay path not required yet. Do not treat default `astrid render` auto-route as in-scope for this checkpoint.

**Validation commands:**
```bash
python -m pytest tests/packs/rendering/test_ffmpeg_support.py tests/packs/rendering/test_ffmpeg_text.py tests/packs/rendering/test_ffmpeg_backend.py -x -q
```

**Commit:** on `megado/oracle-run-ffmpeg-text` after PASS.

---



## Execution instructions
1. You are in the worktree on branch `megado/oracle-run-ffmpeg-text` (HEAD 0c895638 = B1). Read `astrid/packs/rendering/backends/ffmpeg/text.py` FIRST — B1 already landed `_parse_fades`, `_parse_text_shadow`, `_parse_color`, `_text_window` there; you must REUSE them, not re-implement.
2. Read `astrid/packs/rendering/backends/ffmpeg/support.py` and `tests/packs/rendering/test_ffmpeg_support.py` end-to-end before editing. Follow the file's existing fixture dialect.
3. Implement T2 exactly: text-clip acceptance carve-outs, the reject list, font-resolution gate, request-sensitive features, and the in-commit retarget of `unknown_clip_kind` (currently sets `clipType: "text"` → change fixture to `text-card`). Do NOT touch `renderer.yaml` (stays media-only this batch), `command.py`, or `run.py`.
4. Write/adjust tests per the task's test list (accept + reject cases; both W3B-1 feature assertions; the required x/y and audio-track rejects).
5. Validate: `python -m pytest tests/packs/rendering/test_ffmpeg_support.py tests/packs/rendering/test_ffmpeg_text.py tests/packs/rendering/test_ffmpeg_backend.py -x -q` must be green.
6. COMMIT IMMEDIATELY once green (do not polish after committing): `git add astrid/packs/rendering/backends/ffmpeg/support.py tests/packs/rendering/test_ffmpeg_support.py` (+ any test file you added accept cases to), message: `megado B2: support accepts media+text, fail-closed carve-outs`. Do not push.
7. Report: files changed, pytest summary lines, commit SHA, deviations (none allowed beyond spec).

## Reminders
- Support must NOT rasterize; font check = resolver returns None → reason, supported=False.
- Reject text `from` on key presence (even `from: 0`).
- x/y/width/height rejection stays on the existing `_POSITION_KEYS` path — no second checker.
- Media clips still reject ALL effects including fade_in; text clips only get the fade carve-out via `_parse_fades` (any ValueError from it = support reason).
- Report features when any text overlay present: `media_only: False`, `text_overlay: True`, `fade_envelope: <any text fade > 0>`, `whole_media: False`, `stream_copy: False`. Media-only requests keep today's logic.
