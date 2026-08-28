# Tasklist — FFmpeg text rendering extension

**Status:** FROZEN 2026-08-28 — oracle finalized after pre-execution contract review (findings/pre-exec-contract-review.txt: 3 accepted amendments applied, disposition in receipts/preexec-triage.md). Classification finalized: every task `normal`, zero `[XHARD]` (no tag meets the exceptional threshold).
**Source:** settled plan v4 (snapshot `91e2ca981c7539d2`).  
**Base:** `c6c505af`. Branch: `megado/oracle-run-ffmpeg-text`.  
**Effort:** ~1 focused implementation day. **HUGE-RUN:** no — no cumulative big-batch review boundaries.  
**Model policy (user-pinned, 2026-08-28):** normal → GLM 5.3 Flash (`openrouter:z-ai/glm-5.3-flash`); `[XHARD]` / oracle / planner → Grok 4.6. Planner proposes classification; oracle finalizes before freeze.

**Classifications:** every task is **`normal`**. Zero `[XHARD]`. Overlay termination (plan E1) is load-bearing but already a precise mechanical brief with argv pins and a later live hang check — size, hang risk, and importance do not meet the exceptional threshold.

**Execution order:** B1 (T1) → B2 (T2) → B3 (T3) → B4 (T4+T5) → B5 (T6+T7) → B6 (T8) → B7 (completion, host/oracle-owned). Yaml never leads implementation. Auto-route is not a valid checkpoint until B4 lands.

**Synchronization points:** none. This run is strictly sequential. No parallel work inside a batch; later batches consume only the prior passed checkpoint.

**In-commit red-suite retargets (W3A confirmed these are the complete set):**

| Existing test | Move in the same commit as |
| --- | --- |
| `unknown_clip_kind` in `test_ffmpeg_support.py` currently sets `clipType: "text"` | T2 / B2 — retarget to `text-card` (or another non-text non-media type) |
| `test_ffmpeg_backend.py` `clip_types == ["media"]` | T5 / B4 — retarget to `["media", "text"]` |

Leave `test_support_rejects_non_media_timeline` (`_text_timeline()` = media + `text-card`) unchanged. Do **not** add a second text-card reject (W3B-5).

**Out of this run (do not touch):** `rendering.remotion`, `legacy_hybrid`, `legacy_engine.py`, storyboard compile, media `hold`, media fades, transitions, `clipType: "text-card"` / other effects, per-frame PIL, ffmpeg `drawtext`, bundled TTF, fonttools/woff2, `ImageFont.load_default()`, `-shortest`, a fade zero-guard, a third stream-copy veto in `run.py`, a parallel duration parser, a public `_clip_duration_seconds` export, checksum smoke, CI font package, a second fade extractor, a CSS split of `textShadow` in `support.py`, a new post-END smoke fixture.

---

## Batch 1 — Text raster helper

**Depends on:** nothing (first batch).  
**Advances agent-goal:** in-scope #2 (PIL rasterization: font, size, color, weight, alignment, position/anchor, maxWidth wrap, textShadow); in-scope #3 (fade parser that later drives overlay alpha — fades are **not** baked into the PNG); done-criterion 4 (new unit tests, no pre-existing packs regressions). Does **not** yet satisfy done-criteria 1–3 or 5 (no support, no overlay, no yaml, no live render).  
**North Star:** simplest sufficient toolchain (Pillow already in-tree; no `drawtext`, no font subsystem); output parity (Arial/DejaVu, wrap, shadow, anchor — not text-card chrome); offline by default. Avoid silent fallbacks (`load_default()` face swap) and speculative layers (no font catalog, no parallel duration/color/fade/shadow parsers).

### T1 — `astrid/packs/rendering/backends/ffmpeg/text.py` (new)

**Files:**
- create `astrid/packs/rendering/backends/ffmpeg/text.py`
- create `tests/packs/rendering/test_ffmpeg_text.py`

**Changes:**
- `_resolve_font_path(bold) -> Path | None` — ordered TTFs: `/System/Library/Fonts/Supplemental/Arial.ttf` (+ `Arial Bold.ttf`, space in the filename), then `/Library/Fonts/Arial.ttf` (+ Bold), then `/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf` (+ `-Bold`). Bold / `params.weight >= 600` → Bold face. One-line comment: `visual_understand` may `ImageFont.load_default()` for debug labels; `timeline_visualize` fail-hard — this path follows `timeline_visualize`. Missing font → `None`. Never `load_default()`.
- `_parse_color` — `PIL.ImageColor.getcolor(..., "RGBA")` for hex and named; hand-parse only `rgba(r,g,b,a)` (hype’s shadow). One function for fill and shadow. Do not delete the helper; do not hand-parse hex.
- `_parse_text_shadow` — CSS `offsetX offsetY blur color`; 3-part omits blur. Color via `_parse_color`. Invalid nonempty raises; missing/empty → `None`.
- `_parse_fades(effects) -> tuple[float, float]` — the only fade reader in this run. `None` / missing / empty map / empty list → `(0.0, 0.0)`. Map or list-of-objects; keys subset of `{fade_in, fade_out}`; values finite numbers `>= 0` (bool is not a number). List scan matches Remotion `getEffectValue`: first numeric `fade_in` and first numeric `fade_out` independently. Unknown keys, non-dict items, non-numeric or negative values raise.
- `_wrap_lines` — word wrap to `maxWidth`; `<= 0` = one line.
- `_anchor_origin` — compound `top|middle|bottom` × `left|center|right`, default center; offsets as in `ThreeTimelineComposition`.
- `_text_window(clip) -> (at, end)` — thin wrapper: `(at, at + duration)` over `astrid.core.timeline.validators.timeline._clip_duration_seconds`. Do not copy the body. Do not use `command.clip_duration_seconds`. Do not add a public re-export. Fail if duration is `None` or not `> 0` (`hold: 0` fails).
- `rasterize_text_clip(clip, width, height, dest: Path) -> None` — full-canvas RGBA PNG (position baked in; overlay later is always `0:0`). Line height `1.2 * fontSize`. Shadow: offset duplicate + optional blur, then fill. Fades are **not** baked into the PNG. Missing font → `FileNotFoundError`. Empty content refused. Ignore `text.fontFamily` / `italic`.
- Keep the module IO-minimal and unit-testable without ffmpeg.

**Classification:** `normal` — one new helper with a fully specified API; no coupled routing/filtergraph judgment. Proposed model: GLM 5.3 Flash (user-selected normal).

### Checkpoint B1

**Acceptance criteria (oracle verifies):**
1. `text.py` exists with the helpers above; no `drawtext`, no fonttools, no woff2, no PowerGrotesk, no `ImageFont.load_default()`.
2. Font resolver comment names the `visual_understand` / `timeline_visualize` split and follows fail-hard.
3. `_parse_color` uses ImageColor for hex/named and hand-parses only `rgba(...)`.
4. `_parse_text_shadow` and `_parse_fades` match the contracts above; they are the only parsers for those inputs.
5. `_text_window` imports canonical `_clip_duration_seconds`; does not duplicate its body.
6. Rasterize writes a full-canvas RGBA PNG; position is baked in; fades are not.
7. Tests in `tests/packs/rendering/test_ffmpeg_text.py`:
   - wrap
   - bottom-center and top-right anchors
   - **W3B-2:** one rasterize test asserting ink bbox lands in the anchored region (top-right + offsets); `pytest.skip` if resolver returns `None`, same guard as sibling rasterize tests
   - shadow parse including `rgba(...)`; nonempty invalid raises
   - `_parse_color` hex, named, and `rgba(0,0,0,0.75)`
   - `_parse_fades`: map; list-of-objects with independent first-match (including `{fade_in}` then `{fade_out}`); empty/`None` → `(0, 0)`; unknown key / negative / bool raise
   - empty content refused
   - rasterize tests that need a real TTF call the resolver and skip if `None` — no bundled font, no CI font package
   - color/shadow/fade/empty-content tests call helpers directly and do **not** skip
8. No `renderer.yaml` / `support.py` / `command.py` / `run.py` behavior change in this batch.
9. Existing packs rendering tests still pass.

**Validation commands:**
```bash
python -m pytest tests/packs/rendering/test_ffmpeg_text.py -x -q
python -m pytest tests/packs/rendering/ -x -q --ignore=tests/packs/rendering/test_ffmpeg_text.py
(Second command: no pre-existing packs regression — full packs glob minus the new file. Amendment PREEXEC-1: dropped `-k "not live"`, which deselected unrelated tests containing "live" (test_timeline_visualize_frozen.py:274 etc.) and under-verified the stated purpose.)

**Commit:** on `megado/oracle-run-ffmpeg-text` after PASS. Do not push yet.

---

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

## Batch 4 — Run wiring + capability declaration (routing-truth seam)

**Depends on:** B3 PASS. T4 and T5 land **in this same batch**; yaml never leads implementation.  
**Advances agent-goal:** in-scope #1 (yaml), #2 (`run.py` rasterize → overlay specs → ffmpeg), #3 (fade numbers on specs from `_parse_fades`); done-criteria 1 (implementation of the render path), 3 (yaml matches implemented reality), 4 (manifest/CLI tests). Default ffmpeg-first auto-route for media+text becomes truthful only after this batch.  
**North Star:** capability-driven routing — declare only what is implemented; yaml and support agree; no routing lies. Avoid yaml/support lag (they land with the overlay path). Avoid a third stream-copy veto and a second fade reader. Provenance stays `engine: "ffmpeg"` (no silent Remotion fallback inside this backend).

### T4 — `astrid/packs/rendering/backends/ffmpeg/run.py`

**Files:**
- `astrid/packs/rendering/backends/ffmpeg/run.py`
- spec-builder unit test in `tests/packs/rendering/test_ffmpeg_text.py`

**Changes:**
- In `_protocol_render` and `_render_ffmpeg_media_to_path`, after support succeeds: if text clips exist, `TemporaryDirectory` for PNGs, rasterize each, pass `TextOverlaySpec`s into the command builder, run ffmpeg **before** the temp dir is gone.
- Fade numbers on each spec come from `_parse_fades(clip.get("effects"))` — same function support already ran. No second extractor.
- Keep `stream_copy_allowed=bool(report.features.get("stream_copy"))` as today’s relay. Do **not** re-check overlays here. Command.py’s `text_overlays` guard is veto #2.
- Keep existing provenance. Do not change audio-reactive specialization.
- A small private helper that builds the `TextOverlaySpec` tuple from clips (rasterize + `_text_window` + `_parse_fades`) is allowed so the two render paths do not duplicate; it is not a new package.

**Classification:** `normal` — wiring two existing render paths through one helper with parsers already in T1 and overlays already in T3. Proposed model: GLM 5.3 Flash.

### T5 — `astrid/packs/rendering/backends/ffmpeg/renderer.yaml`

**Files:**
- `astrid/packs/rendering/backends/ffmpeg/renderer.yaml`
- `tests/packs/rendering/test_ffmpeg_backend.py` (`clip_types` + features dict-equality)

**Changes:**
```yaml
clip_types: [media, text]
features:
  media_only: false
  text_overlay: true
  fade_envelope: true
  stream_copy: true
  sequential_audio: true
```
- `stream_copy: true` remains a **capability** (media-only requests still copy); support features stay request-sensitive.
- Update the one-line `description` so it is not “media-only”.
- **In-commit retarget:** `test_ffmpeg_backend.py` `clip_types == ["media"]` → `["media", "text"]` in this same commit.
- Dict-equality on the declared features block:
  ```python
  assert manifest.capabilities["features"] == {
      "media_only": False,
      "text_overlay": True,
      "fade_envelope": True,
      "stream_copy": True,
      "sequential_audio": True,
  }
  ```
- `tests/core/rendering/test_cli.py` (`"clip_types: media" in text`) still holds as a prefix of `clip_types: media, text`. Do not edit that file. Do not touch planner tests or `legacy_hybrid`. Do not add a `service.py` auto-route test.

**Classification:** `normal` — mechanical yaml + two assertion updates, gated to land with T4. Proposed model: GLM 5.3 Flash.

### Checkpoint B4

**Acceptance criteria (oracle verifies):**
1. Both render paths (`_protocol_render` and `_render_ffmpeg_media_to_path`) rasterize text to a temp dir, pass specs into the command builder, and invoke ffmpeg before the temp dir is gone.
2. Spec fades come from `_parse_fades`; run.py has no second fade extractor.
3. `stream_copy_allowed=bool(report.features.get("stream_copy"))` is unchanged (no overlay re-check in run.py).
4. **W3B-3:** one unit test on the private spec-builder with rasterize patched; asserts `at`/`end` via `_text_window` and fades via `_parse_fades`.
5. Provenance still records `engine: "ffmpeg"`. Audio-reactive path unchanged.
6. `renderer.yaml` matches the block above; description is not “media-only”.
7. `test_ffmpeg_backend.py` asserts `clip_types == ["media", "text"]` and the features dict-equality. That retarget is in this commit.
8. `python -m pytest tests/core/rendering/test_cli.py -q` still passes (`clip_types: media` is a prefix of `clip_types: media, text`).
9. Support-accepts-media+text plus yaml `text` is the evidence the default ffmpeg-first policy will pick this backend. Do not add a planner/`service.py` auto-route test.
10. T4 implementation is present in the same commit as T5 yaml — yaml does not lead.

**Validation commands:**
```bash
python -m pytest tests/packs/rendering/test_ffmpeg_text.py tests/packs/rendering/test_ffmpeg_support.py tests/packs/rendering/test_ffmpeg_backend.py -x -q
python -m pytest tests/core/rendering/test_cli.py -q
```

**Commit:** on `megado/oracle-run-ffmpeg-text` after PASS. This is the first checkpoint at which default `astrid render` / `rendering.render` auto-route for media+text is truthful.

---

## Batch 5 — Live smoke (author + host-run)

**Depends on:** B4 PASS (implementation + co-located unit/support/argv/yaml tests already green).  
**Advances agent-goal:** done-criterion 1 (media+text renders: visible, positioned, timed, faded, plays) and done-criterion 5 (short live render smoke, real ffmpeg).  
**North Star:** hang is caught by a real ffmpeg, not only argv; output parity is “text visible,” not pixel-match; overlay **timing** is observed live. Avoid checksum smoke, extra fixtures, and treating liveness as pixel-identity.

T6 is executor-authored. T7 is the **authoritative host/oracle invocation** of that same test (one owner runs live validation once). Executors may do one local green check while authoring; they must not duplicate extra paid/live runs.

### T6 — Author `test_live_media_plus_text_smoke`

**Files:** `tests/packs/rendering/test_ffmpeg_text.py` only (add the live test). No more unit/support/argv/yaml tests here.

**Changes:**
- Minimal timeline: one `from`/`to` visual media clip (tiny generated **constant-color** H264 via the suite’s real-ffmpeg fixture pattern from `test_ffmpeg_finalizer.py` / compositor smokes), one `clipType: "text"` with `hold`, `params.anchor`, `effects.fade_in/fade_out`, optional audio.
- Window strictly inside the media (e.g. media 4s, text `at=1` `hold=1`, fades `0.2/0.2` → overlay `[1, 2]`).
- Invoke `rendering.ffmpeg` support+render **directly** (protocol `run.main` or `ffmpeg.render`).
- Assert: `supported is True`; output exists; ffprobe has video and a **finite duration** (hang regression: unterminated `-loop 1` yields timeout / `moov atom not found`).
- **W3B-4:** sample a **mid-window** frame (e.g. `t=1.5` for window `[1, 2]`), **not** at window start. That frame is not a blank plate via **luma and/or alpha only**.
- **One extra frame extract after END:** its luma ≈ the pre-AT plate (overlay gone). Same color plate, one more `-ss` extract. No new fixture. Encoder noise allowed; not pixel-identical; not a checksum. No overlay-PNG checksum.
- Skip if ffmpeg/ffprobe missing or font resolver returns `None`.
- **Not** the 76-clip intro storyboard (extra visual media and other pre-existing ffmpeg refusals).
- `pytest-timeout` 120s is a backstop, not the fix. Termination must come from input `-t`.

**Classification:** `normal` — one smoke test copying an existing lavfi→libx264 pattern with pinned sample times. Proposed model: GLM 5.3 Flash.

### T7 — Host-run live smoke (done-criterion 5)

**Files:** none. No code.

**Command (authoritative, host/oracle runs once):**
```bash
python -m pytest tests/packs/rendering/test_ffmpeg_text.py::test_live_media_plus_text_smoke -x -q
```

Same assertions as T6, including mid-window ink and post-END luma ≈ pre-AT.

**Classification:** `normal` — run an already-authored pytest node; not a judgment kernel. Proposed model: n/a (host/oracle owns the live invocation per the agent-goal validation contract). Executor local green check during T6 is allowed; do not duplicate the host run.

### Checkpoint B5

**Acceptance criteria (oracle verifies):**
1. `test_live_media_plus_text_smoke` exists with the timeline shape above.
2. **W3B-4:** the in-window sample is mid-window (e.g. 1.5 for `[1, 2]`), not AT / window start.
3. Post-END frame luma ≈ pre-AT plate; in-window frame is not a blank plate (luma and/or alpha).
4. Output exists, plays, ffprobe duration is finite (no `moov atom not found`, no hang).
5. Skip guards: missing ffmpeg/ffprobe or missing font → skip, not fail.
6. No checksum, no new fixture, no intro-storyboard target.
7. Host/oracle evidence of the authoritative command above (one run). Executor may have one local green check in the implementing batch.

**Validation commands:**
```bash
# executor local green check while authoring (at most once)
python -m pytest tests/packs/rendering/test_ffmpeg_text.py::test_live_media_plus_text_smoke -x -q

# authoritative host/oracle run (once; this is T7)
python -m pytest tests/packs/rendering/test_ffmpeg_text.py::test_live_media_plus_text_smoke -x -q
```

**Commit:** on `megado/oracle-run-ffmpeg-text` after PASS (the test file). Host-run evidence goes under `.oracle/evidence/`.

---

## Batch 6 — Docs (claims match shipped behavior)

**Depends on:** B5 PASS.  
**Advances agent-goal:** done-criterion 6 (docs touched only where behavior/claims changed).  
**North Star:** no routing lies in documentation — do not claim the hybrid planner still intercepts text; do not claim yaml/support are “not enough” to change default routing (v1 was wrong). Avoid scope creep: this file only; no planner/Remotion docs.

### T8 — `docs/ffmpeg-text-extension.md` only

**Files:** `docs/ffmpeg-text-extension.md`

**Changes — correct claims to match shipped behavior:**
- Filtergraph lives in `command.py`, not a section loop in `run.py`.
- Fades are `clip.effects` via one `_parse_fades` shared by support and run.
- Font is system Arial/DejaVu TTF, fail-closed (no `load_default()`, no fonttools, no woff2, no PowerGrotesk).
- Color is ImageColor + `rgba()`; shadow is `_parse_text_shadow` (support does not re-split CSS).
- Text window wraps canonical `_clip_duration_seconds`; text `from` is rejected.
- Overlay is full-canvas PNG + `overlay=0:0` with `-loop 1 -t END` (not `-shortest`, not `-t END-AT`).
- Default `rendering.render` is ffmpeg-first auto-route, so media+text that pass support now render on ffmpeg. Remotion remains the fallback when ffmpeg fail-closes (text-card, media hold, extra visual media, missing font, text `from`, x/y transforms, etc.).
- `legacy_hybrid` is unused on the default path and is unchanged.
- Intro storyboard is not the smoke target.
- Stream-copy is vetoed by support features and the command builder, not a third `run.py` branch.
- Live smoke observes the overlay window (mid-window visible, post-END matches pre-AT).

Do **not** claim the hybrid planner still intercepts text. Do **not** claim yaml/support are “not enough” to change default routing. Do not edit planner/Remotion docs.

**Classification:** `normal` — claim-correction in one seed-plan file against a pinned list. Proposed model: GLM 5.3 Flash.

### Checkpoint B6

**Acceptance criteria (oracle verifies):**
1. Only `docs/ffmpeg-text-extension.md` is edited for docs.
2. Every claim bullet of T8 is present and matches the shipped code: filtergraph location (`command.py`); fades are `clip.effects` via one `_parse_fades` shared by support and run; font is system Arial/DejaVu TTF fail-closed (no `load_default()`, no fonttools, no woff2, no PowerGrotesk); color is ImageColor + `rgba()` branch, shadow via `_parse_text_shadow`; text window wraps canonical `_clip_duration_seconds` and text `from` is rejected; overlay is full-canvas PNG + `overlay=0:0` with `-loop 1 -t END`; default `rendering.render` is ffmpeg-first auto-route with Remotion as fail-closed fallback; `legacy_hybrid` unused on the default path and unchanged; intro storyboard not the smoke target; stream-copy vetoed by support features + command builder (no third `run.py` branch); live smoke observes the overlay window (mid-window visible, post-END ≈ pre-AT).
3. No claim that the hybrid planner intercepts text, and no claim that yaml/support are "not enough" to change default routing.
4. No other docs files touched (`git diff --name-only c6c505af..HEAD -- docs/` shows only `ffmpeg-text-extension.md`).

**Validation commands:**
```bash
python -m pytest tests/packs/rendering/ -x -q
python -m pytest tests/core/rendering/test_cli.py -q
```

**Commit:** on `megado/oracle-run-ffmpeg-text` after PASS.

---

## Batch 7 — Completion (host/oracle-owned; PREEXEC-3)

**Depends on:** B6 PASS. No executor dispatch — the host and oracle own every step (mirrors T7's ownership pattern).

**Steps:**
1. Authoritative full-suite run (once, host): `python -m pytest tests/packs/rendering/ -x -q`
2. Oracle cumulative diff review: `git diff c6c505af..HEAD -- astrid/packs/rendering/backends/ffmpeg/` against every checkpoint's acceptance criteria (final overall review per megado skill — 1-3 independent passes at the oracle's discretion; this run: 1 Grok pass + 1 GLM pass given backend-local scope).
3. Evidence matrix: map every agent-goal done-criterion to its evidence path/command/result (`.oracle/evidence/completion-matrix.md`).
4. Push: `git push origin HEAD:megado/oracle-run-ffmpeg-text` (explicit refspec; never main).
5. Update `status.md`/`execution.log`; `open` the worktree; phase-by-phase report.

**Advances agent-goal:** done-criteria 4 (authoritative suite), plus the completion/sync authorization in agent_goal.md.
**North Star:** no routing lies in the final record; sync only under agent_goal authorization.
**Classification:** `normal` (process steps; no code).
