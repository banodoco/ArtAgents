# Batch 4 checkpoint evidence

- Commit: `4ea29d62` "megado B4: run wiring text overlays + declare text capabilities" (parent 84557393)
- Delta: `renderer.yaml` (+7/−), `run.py` (+103/−), `test_ffmpeg_backend.py` (+9/−), `test_ffmpeg_text.py` (+48). Four files — T4 and T5 in one commit (yaml never leads).
- Executor: GLM 5.3 Flash (exit 0, 1175.9s). Deviations: none (executor's own report; no planner/service.py/test_cli.py edits).
- Host validation: packs triple → **87 passed** (110.7s); `tests/core/rendering/test_cli.py` → **16 passed** (52.9s; `clip_types: media` prefix holds).
- Routing-truth seam: from this commit, `renderer.yaml` declares `clip_types: [media, text]` + `text_overlay`/`fade_envelope` features, and support accepts media+text — default ffmpeg-first auto-route for media+text is now truthful.
- W3B-3: spec-builder unit test present (`_text_overlay_specs` with patched rasterize; windows via `_text_window`, fades via `_parse_fades`).
- Acceptance criteria B4 (tasklist): 1-10 — verified by oracle check-in (checkins/batch-4.md).
