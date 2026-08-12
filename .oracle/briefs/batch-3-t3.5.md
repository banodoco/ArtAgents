# Task T3.5 — Extract `rendering.ffmpeg-finalizer` [HARD]

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`.
You have `workspace-write` permissions. Python: `PYENV_VERSION=3.11.11`.

## Context

Batch 3 of "Pluggable Timeline Renderers". T3.1-T3.4 extracted the Remotion
and FFmpeg backends. The render monolith still has `_concat_segments()` —
the FFmpeg concatenation with hard-coded 30 FPS, H.264/AAC stereo 44.1kHz,
no probing. Your job: extract it behind the finalizer contract as
`rendering.ffmpeg-finalizer` (canonical id from the frozen docs), with
complete profile comparison and normalization.

## Change

1. Create `astrid/packs/rendering/finalizers/ffmpeg/`:
   - `__init__.py`, `run.py` (raw-command adapter for the `finalize` verb:
     reads `--request` (FinalizeRequest-shaped with per-segment video
     artifacts), writes `--result`), `finalizer.yaml` (id
     `rendering.ffmpeg-finalizer`, protocol_version 1, command
     `[python3, run.py]`, operations `[finalize, support]`,
     capabilities, required_permissions).
   - Move `_concat_segments()` here as pure logic: preflight every segment
     with the strict media probe (artifacts.validate / media.py), derive
     the output profile from the REQUEST's canonical profile (rational FPS
     from the timeline — NO hard-coded 30), stream-copy segments that are
     already compatible, otherwise normalize (dimensions, rational
     FPS/time base, codecs, pixel format, audio rate/layout/presence),
     recording every normalization in the result.
   - Audio modes: `rendered` (mux segments' audio), `passthrough` (carry
     through), `none` (visual-only segments must not be forced to silence).
   - Preserve attachments outside the finalizer's interpretation.
2. Register in `astrid/packs/rendering/pack.yaml`
   (`extensions.rendering.finalizers`).
3. Keep the facade's hybrid concat working via the finalizer module.
4. Add `tests/packs/rendering/test_ffmpeg_finalizer.py`:
   - single-segment pass-through (no re-encode when compatible);
   - mixed compatible/incompatible segments;
   - 24/25/30 + rational FPS normalization;
   - duration errors rejected before assembly;
   - missing audio/video rejected;
   - codec mismatch → normalization;
   - normalization recorded in result;
   - audio rendered/passthrough/none modes;
   - attachments preserved;
   - cleanup.

## Acceptance

- `pytest -q tests/packs/rendering/test_ffmpeg_finalizer.py` passes.
- `pytest -q tests/packs/rendering` has no NEW failures.
- No hard-coded `fps=30` remains in the finalizer (grep).

Run ONLY those commands. Do NOT run the full suite, formatters, linters. Do
NOT modify `contracts.py`, `schemas/`, `docs/contracts/`, `transport.py`,
`assets.py`, `publication.py`, `backends/remotion/`, `backends/ffmpeg/`, or
Batch-1 frozen files. Preserve all existing work. Report: files created,
test results, the finalizer protocol.
