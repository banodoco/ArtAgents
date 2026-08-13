# Task T3.4 — Strict FFmpeg support and audio semantics [HARD]

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`.
You have `workspace-write` permissions. Python: `PYENV_VERSION=3.11.11`.

## Context

Batch 3 of "Pluggable Timeline Renderers". T3.3 (before you) extracted the
FFmpeg backend to `astrid/packs/rendering/backends/ffmpeg/` with pure
builders. Your job: make its `support` STRICT (fail closed) and implement
exact audio semantics. The exploration findings
(`.oracle/findings/06-ffmpeg-media-audio.txt` and
`15-audio-semantics.txt`) documented the current fail-open gaps: visual
gaps, overlapping audio, speed changes, missing sources, unsupported
track/clip types, muted tracks silently dropped, fades ignored.

## Change

1. `astrid/packs/rendering/backends/ffmpeg/support.py`:
   - `support(request, timeline_data, assets)` → `SupportReport` that FAILS
     CLOSED for: unknown clip/track kinds, invalid frame bounds, visual
     gaps/overlaps, speed != 1.0, transforms, crop, effects, transitions,
     opacity, discarded visual audio, overlapping audio, fades, missing
     media streams, missing binaries. Each rejection includes a reason and
     alternatives (qualified backend ids).
   - Request-sensitive: the audio-reactive specialization and the
     whole-media optimization are expressed as SUPPORT EVIDENCE (features
     dict), not facade-level branches.
2. Audio semantics (exact):
   - track-volume × clip-volume gain multiplies into the `volume=` filter;
   - track `muted` wins over everything; clip `volume: 0` = silence;
   - supported sequential audio mixing (non-overlapping clips concat);
   - stream-copy fast path preserved;
   - explicit `audio_ownership` in results — visual-only backends must NOT
     synthesize silence; any legacy silence compatibility belongs to host
     audio completion (Batch 4).
3. Keep `audio_reactive_colour` working as a specialization with markers,
   event count, frame count, fps, hash in provenance fragments.
4. Add `tests/packs/rendering/test_ffmpeg_support.py` covering every
   rejection rule + the audio gain/mute/volume/mixing rules.
5. `tests/packs/test_audio_render.py` must stay green.

## Acceptance

- `pytest -q tests/packs/rendering/test_ffmpeg_support.py tests/packs/test_audio_render.py` passes.
- `pytest -q tests/packs/rendering` has no NEW failures.

Run ONLY those commands. Do NOT run the full suite, formatters, linters. Do
NOT modify `contracts.py`, `schemas/`, `docs/contracts/`, `transport.py`,
`assets.py`, `publication.py`, `backends/remotion/`, or Batch-1 frozen
files. Preserve all existing work. Report: files changed, test results, the
audio-semantics rules implemented.
