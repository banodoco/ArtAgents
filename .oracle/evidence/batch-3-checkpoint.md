# Batch 3 checkpoint evidence

- Commit: `84557393` "megado B3: text overlay filtergraph (-t END cap, dual fades, spine-first)" (parent b66a83ab)
- Delta: `astrid/packs/rendering/backends/ffmpeg/command.py` (+80/−7) + `tests/packs/rendering/test_ffmpeg_text.py` (+224). Two files.
- Executor: GLM 5.3 Flash (exit 0, 1084.5s). Deviations: none (executor's own report).
- Executor empirical verification (recorded): ffmpeg 7.1.1 accepts final overlay re-emitting `[vout]`; pixel probe shows composed overlay over spine at frame 10; PNG `-t` cap > spine extends output to END (benign: smoke design keeps END inside spine); facade failures (test_render_facade*, run_ownership, legacy characterization — 8) verified pre-existing at B2 HEAD via stash/re-run baseline (identical 8 failed / 44 passed).
- Host validation: `pytest test_ffmpeg_text test_ffmpeg_support test_ffmpeg_backend test_ffmpeg_compositor -q` → **100 passed** in 65.9s.
- Acceptance criteria B3 (tasklist): 1-10 — verified by oracle check-in (checkins/batch-3.md).
