# Batch 5 checkpoint evidence

- Commit: `5fd08a28` "megado B5: live media+text smoke (hang, window, parity guards)" (parent 4ea29d62)
- Delta: `tests/packs/rendering/test_ffmpeg_text.py` (+214). One file (test authoring only).
- Executor: GLM 5.3 Flash (exit 0, 503.3s). Deviations: none; two documented in-spec judgment calls (optional audio included via canonical include_audio shape; pre-AT plate luma read from a t=0.5 extract rather than computed).
- **T7 — authoritative host/oracle live run (once):** `python -m pytest tests/packs/rendering/test_ffmpeg_text.py::test_live_media_plus_text_smoke -x -q` → **1 passed in 11.12s** (raw output: `evidence/batch-5-live-smoke.txt`).
  - Proves live: supported=True; finite output duration (no `-loop 1` hang); mid-window frame not blank (W3B-4); post-END frame luma ≈ pre-AT plate.
  - Done-criteria 1 (media+text renders: visible, positioned, timed, faded, plays) and 5 (live smoke) satisfied.
- Acceptance criteria B5 (tasklist): 1-7 — verified by oracle check-in (checkins/batch-5.md).
