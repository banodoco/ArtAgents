# Task T1.1 — Characterize and record the baseline (DeepSeek Flash)

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. You
MAY edit files (file, web, terminal toolsets). Python: use
`PYENV_VERSION=3.11.11` (set it in your shell before python commands).

## Context

This is Batch 1 of the "Pluggable Timeline Renderers" epic. Astrid's render
path is `astrid/packs/rendering/executors/render/run.py` (a monolith). The
epic will later extract backends behind contracts; YOUR job is only to
characterize today's behavior with tests and a baseline doc so the extraction
can be proven behavior-preserving. Do NOT refactor run.py.

## Change

1. Create `.oracle/baseline.md` recording:
   - the dirty-tree snapshot origin (commit `6b2ff1a`, "snapshot dirty working
     tree as oracle base");
   - baseline pytest failures/skips: run `pytest -q tests/packs/rendering
     tests/packs/test_audio_render.py` and `pytest -q tests/packs/hype
     tests/packs/iteration tests/packs/editorial` and record pass/fail/skip
     counts and the skip reasons verbatim;
   - the complete production callsite inventory of concrete render usage
     (read `astrid/packs/video_editing/orchestrators/iteration_video/run.py`,
     `astrid/packs/video_editing/executors/cut/run.py`,
     `astrid/packs/video_editing/executors/cut/resume.py`,
     `astrid/packs/video_editing/orchestrators/hype/steps.py`,
     `astrid/packs/editorial/executors/human_notes/run.py`, and
     `tools/render_and_check.py`; list each file:line and whether it imports
     the module in-process, spawns `python -m ...render.run`, or uses the
     canonical `astrid executors run rendering.render`);
   - the empty Sprint 08 fixture state (`tests/fixtures/sprint08/` contents);
   - all three legacy engines (`remotion`, `ffmpeg`, `hybrid`): where each is
     dispatched in run.py (line numbers);
   - the nominal-Remotion auto-FFmpeg routing (`_can_render_with_ffmpeg_media`
     or equivalent) and the audio-reactive early selection
     (`audio_reactive_colour.py` import and dispatch);
   - every v1 provenance key written by `_write_render_provenance` (quote the
     dict construction with line numbers);
   - transition units (how `_timeline_duration_seconds` and segment frames
     are computed);
   - standalone vs attached run ownership (whether run.py creates a
     `run.json` — confirm it does not).
2. Add `tests/packs/rendering/test_legacy_renderer_characterization.py` with
   characterization tests ONLY:
   - `engine=remotion|ffmpeg|hybrid` dispatch selection (assert which internal
     render function would be chosen given a media-only timeline vs a complex
     timeline; you may assert on the public functions/helpers that decide
     routing, do NOT spawn real renders);
   - nominal-Remotion auto-FFmpeg: assert the eligibility helper's result for
     a media-only timeline and a timeline with a text card;
   - audio-reactive early selection: assert the specialization contract check
     (read `audio_reactive_colour.py` to find its entry predicate);
   - v1 provenance keys: build a small helper fixture that calls the
     provenance-building function with a fake context (mock out any heavy
     deps) and assert the exact key set;
   - transition units: assert `_timeline_duration_seconds`/frame math for a
     couple of representative timelines (pure function calls, no subprocess);
   - run ownership: assert `run.py` `main()` does not call
     `prepare_project_run` (grep-based assertion is acceptable here, or an
     import-level assertion).
   Keep the tests deterministic, fast, and subprocess-free where possible.
   Follow existing test conventions in `tests/packs/rendering/`.

## Acceptance

- `pytest -q tests/packs/rendering/test_legacy_renderer_characterization.py`
  passes (new tests green).
- `pytest -q tests/packs/rendering tests/packs/test_audio_render.py` shows no
  NEW failures vs baseline (same pass/fail/skip).
- `.oracle/baseline.md` exists with all the sections above.

Run ONLY the acceptance commands above — do NOT run the full suite, do NOT
run formatters/linters, do NOT touch files outside
`tests/packs/rendering/test_legacy_renderer_characterization.py` and
`.oracle/baseline.md`. Preserve all existing files; never reset anything.
Report: what you recorded, test results, and any surprises.
