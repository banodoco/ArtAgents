I'll gate Batch 1 as oracle: read the two-file delta against every B1 criterion, then dispatch GLM verification so the verdict is evidence-backed, not assumed.Commit and two-file delta match the evidence. Next I’ll read `text.py` and the tests, then send GLM a criterion-by-criterion critique brief.I’ve got the two-file delta. Next I’ll pin contracts against the code, then send GLM a KISS/YAGNI critique plus a mechanical AC check.Contracts match so far. Dispatching GLM for mechanical AC plus KISS critique, and running the B1 tests myself.PASS

**AC 1–9**
1. PASS — `text.py` has all T1 helpers. Grep: no `drawtext` / `fonttools` / `woff2` / `PowerGrotesk`; sole `load_default` hit is the required comment (`text.py:68`).
2. PASS — comment names `visual_understand` vs `timeline_visualize` and follows fail-hard (`text.py:68–69`); missing font → `None` / `FileNotFoundError`.
3. PASS — hex/named via `ImageColor.getcolor(..., "RGBA")` (`text.py:101`); only `rgba(...)` is hand-parsed (`text.py:87–100`).
4. PASS — shadow/fade contracts match T1; they are the only parsers in the delta (and the only `fade_in` reader under `astrid/`).
5. PASS — imports canonical `_clip_duration_seconds` (`text.py:21,252`); no body copy; no `command.clip_duration_seconds`; no re-export. `hold: 0` fails.
6. PASS — full-canvas RGBA PNG (`text.py:337–349`); position baked (`text.py:313`); rasterize never calls `_parse_fades`; test asserts `max_alpha == 255` with fades present.
7. PASS — wrap, bottom-center/top-right anchors, W3B-2 ink bbox (`test_rasterize_places_ink_in_anchored_top_right_region`), shadow+`rgba`+invalid raise, color hex/named/`rgba(0,0,0,0.75)`, fades map/list first-match/empty/`None`/unknown/negative/bool, empty content refused. Rasterize/wrap skip only via `_skip_if_no_font`; color/shadow/fade/empty-content never skip. `python -m pytest tests/packs/rendering/test_ffmpeg_text.py -x -q` → **11 passed**.
8. PASS — `git diff c6c505af..0c895638` is two new files only; `renderer.yaml` / `support.py` / `command.py` / `run.py` untouched.
9. PASS — no regression surface: only the new test imports `text`; ffmpeg `__init__.py` does not. Existing `test_ffmpeg_{support,backend,finalizer}` → **68 passed**. Host’s 52-pack sweep failures are pre-existing (golden drift, missing `remotion/node_modules`, live-render timeouts); 0 in ffmpeg support/backend/finalizer.

**North Star**
- Simplest sufficient toolchain: ALIGNED (Pillow only).
- Capability-driven routing: N/A this batch (no yaml/support).
- Output parity: ALIGNED (wrap/anchor/shadow/line-height mirror `ThreeTimelineComposition`).
- Offline by default: ALIGNED (system TTF, no CDN).
- Anti-patterns (routing lies, yaml/support lag, speculative layers, silent `load_default` fallback, scope creep): ALIGNED.

**Issues:** none. GLM mechanical: PASS. GLM elegance: ALIGNED. Nits (weight binarized at 600; ~1–2px PIL vs canvas baseline) are not fail-worthy.
