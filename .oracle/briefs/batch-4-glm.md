# Executor brief — Batch 4 (megado run ffmpeg-text)

You are the NORMAL EXECUTOR for Batch 4. Mechanical execution only: implement exactly what the task specifies — no scope widening. T4 (run.py) and T5 (renderer.yaml) land IN THIS SAME COMMIT; yaml never leads implementation. If you believe something in the spec is wrong, STOP and report.

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



## Execution instructions
1. You are in the worktree on branch `megado/oracle-run-ffmpeg-text` (HEAD 84557393 = B3). Landed so far: `text.py` helpers (B1), support carve-outs (B2), command.py overlay filtergraph (B3). Read `astrid/packs/rendering/backends/ffmpeg/run.py` end-to-end FIRST — especially `_protocol_render`, `_render_ffmpeg_media_to_path`, `stream_copy_allowed` relay (run.py:121 area), provenance, and the audio-reactive specialization (do not touch it).
2. T4 exactly:
   - In `_protocol_render` AND `_render_ffmpeg_media_to_path`: after support succeeds, if text clips exist → `TemporaryDirectory` for PNGs, `rasterize_text_clip` each, build `TextOverlaySpec`s, pass into the command builder, run ffmpeg BEFORE the temp dir is gone.
   - Fade numbers per spec come from `_parse_fades(clip.get("effects"))` — the SAME function support ran. No second extractor.
   - A small private helper building the `TextOverlaySpec` tuple from clips (rasterize + `_text_window` + `_parse_fades`) is allowed so the two render paths do not duplicate; it is not a new package.
   - Keep `stream_copy_allowed=bool(report.features.get("stream_copy"))` unchanged — do NOT re-check overlays in run.py (command.py's `text_overlays` guard is veto #2).
   - Keep existing provenance (`engine: "ffmpeg"`). Do not change audio-reactive.
3. T5 exactly:
   - `renderer.yaml`: `clip_types: [media, text]`; features: `media_only: false`, `text_overlay: true`, `fade_envelope: true`, `stream_copy: true`, `sequential_audio: true`; update the one-line `description` so it is not "media-only".
   - `test_ffmpeg_backend.py`: retarget `clip_types == ["media"]` → `["media", "text"]` IN THIS COMMIT; add the features dict-equality assertion: `manifest.capabilities["features"] == {"media_only": False, "text_overlay": True, "fade_envelope": True, "stream_copy": True, "sequential_audio": True}`.
   - Do NOT edit `tests/core/rendering/test_cli.py` (`"clip_types: media" in text` still passes as a prefix). Do NOT touch planner tests or legacy_hybrid. Do NOT add a service.py auto-route test.
4. W3B-3: add ONE unit test on the private spec-builder (patched rasterize; assert `at`/`end` via `_text_window`, fades via `_parse_fades`) in `tests/packs/rendering/test_ffmpeg_text.py`.
5. Validate ALL green:
   - `python -m pytest tests/packs/rendering/test_ffmpeg_text.py tests/packs/rendering/test_ffmpeg_support.py tests/packs/rendering/test_ffmpeg_backend.py -x -q`
   - `python -m pytest tests/core/rendering/test_cli.py -q`
6. COMMIT IMMEDIATELY once green: `git add astrid/packs/rendering/backends/ffmpeg/run.py astrid/packs/rendering/backends/ffmpeg/renderer.yaml tests/packs/rendering/test_ffmpeg_backend.py tests/packs/rendering/test_ffmpeg_text.py`, message: `megado B4: run wiring text overlays + declare text capabilities`. Do not push.
7. Report: files changed, pytest summaries, commit SHA, deviations (none allowed).
