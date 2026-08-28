# Batch 2 checkpoint evidence

- Commit: `b66a83ab` "megado B2: support accepts media+text, fail-closed carve-outs" (parent 0c895638)
- Delta: `astrid/packs/rendering/backends/ffmpeg/support.py` (+129/−10 within) + `tests/packs/rendering/test_ffmpeg_support.py` (+168). Two files, matches tasklist.
- Executor: GLM 5.3 Flash (3000s budget, exit 0; final response was terse "124" — liveness≠correctness, so host re-verified below).
- Host validation: `python -m pytest tests/packs/rendering/test_ffmpeg_support.py tests/packs/rendering/test_ffmpeg_text.py tests/packs/rendering/test_ffmpeg_backend.py -q` → **77 passed** in 185.1s.
- Acceptance criteria B2 (tasklist): 1-8 — verified by oracle check-in (checkins/batch-2.md).
- Note: `renderer.yaml`, `command.py`, `run.py` untouched this batch (criterion 8).
