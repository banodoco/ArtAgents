# Executor brief — Batch 1 (megado run ffmpeg-text)

You are the NORMAL EXECUTOR for Batch 1. Mechanical execution only: implement exactly what the task specifies, no scope widening, no refactors beyond the task, no "improvements". Architectural decisions are already made and pinned — follow them literally.

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



## Execution instructions
1. Work in the current repo (you are already in the worktree on branch `megado/oracle-run-ffmpeg-text`; base c6c505af). Do NOT touch any other branch/worktree; do NOT push.
2. Implement T1 exactly. Read the referenced code first (`astrid/core/timeline/validators/timeline.py` `_clip_duration_seconds`, `ThreeTimelineComposition.tsx` anchor/offset semantics, existing `tests/packs/rendering/` conventions) so helpers match reality.
3. Write the tests listed in the task. Color/shadow/fade/empty-content tests call helpers directly and never skip; rasterize tests skip only if the font resolver returns None.
4. Run the batch validation commands listed above; both must be green.
5. Commit everything (code + tests) on the current branch: `git add` only the files you created/modified for this task, commit message: `megado B1: text raster helper (text.py) + unit tests`. Do not push.
6. Report: files changed, test results (paste the pytest summary lines), commit SHA, and any deviation from the task spec (deviations beyond the spec are NOT allowed — if you believe something in the spec is wrong or impossible, STOP and report instead of improvising).

## Notes
- `_parse_fades` list-form semantics: scan the list; independently take the FIRST numeric `fade_in` and the FIRST numeric `fade_out` (mirrors Remotion `getEffectValue`). Unknown keys, non-dict items, non-numeric or negative values raise.
- `_text_window`: import `_clip_duration_seconds` from `astrid.core.timeline.validators.timeline` (do NOT copy its body, do NOT add a public re-export, do NOT use `command.clip_duration_seconds`).
- Font candidate list (ordered): `/System/Library/Fonts/Supplemental/Arial.ttf`, `/System/Library/Fonts/Supplemental/Arial Bold.ttf` (note the SPACE), `/Library/Fonts/Arial.ttf`, `/Library/Fonts/Arial Bold.ttf`, `/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf`, `/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf`. Bold when `text.bold` or `params.weight >= 600`. First existing path wins; none → None.
- Anchor semantics: compound `top|middle|bottom` × `left|center|right`, default `center`/`center`; offsetX/offsetY shift from that anchor origin, matching `ThreeTimelineComposition`.
- Shadow: CSS form `offsetX offsetY blur color` (3-part form omits blur); draw = offset duplicate (+ optional blur) then fill.
- Line height: `1.2 * fontSize`. Full-canvas RGBA PNG, position baked in; fades are NOT baked into the PNG.
