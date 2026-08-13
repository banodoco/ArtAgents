# Explore: parity fixtures, test coupling, and CI lanes

Project root: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. Read-only exploration. Do NOT edit files.

## What to establish

1. Parity fixture authority:
   - `tests/fixtures/sprint08/` (or wherever the "parity" fixture lives):
     what's inside (README only?), and what `tests/packs/test_renderer_parity.py`
     actually asserts (the epic brief says it hashes input JSON and renders
     nothing — verify and quote).
   - `tests/fixtures/reshape/hype_regression/` and `tests/golden/hype/` —
     what they cover (`merged_render_props.json`?).
   - `tests/packs/rendering/test_audio_reactive_colour.py` — what it asserts.
   - Are there any committed real media fixtures (small mp4s)? Where?
2. Test coupling: which tests import PRIVATE helpers from
   `astrid/packs/rendering/executors/render/` (grep `from astrid.packs.rendering.executors.render`
   and `render_executor` in tests/) — list each and which private symbol.
   Same for `training/executors/asset_cache` and Hype tests.
3. CI lanes: look at `.github/workflows/` — which jobs run real renders
   (ffmpeg? remotion typecheck?), which have optional skips, and where a new
   "renderer parity lane" would slot in. Also check `Makefile` targets
   (`make check`, `make ci`) and `scripts/smoke_wheel_install.sh`.
4. How dependency-based skips are expressed today (pytest.importorskip?
   skipif?) — show one example so new skip messages can match the convention.

## Report format

Ranked findings with file:line evidence. Max 350 words. End with:
- Verified facts
- Unknowns
- Risks (a "parity" gate that exercises nothing)
- Suggested approach
