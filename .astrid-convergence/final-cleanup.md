# Final merge-specific cleanup

Date: 2026-08-29
Base: `a3269811`
Code commit: recorded by `git log -1` after this cleanup commit

## Changes

- Removed the six tracked `fal-voice-upscale/` scratch paths (three scripts and
  three MP3s), removed its root hygiene allowlist entry, and added `*.mp3` to
  both the ignore rules and tracked-runtime-media classifier.
- Restored `derived_output` to Astrid's clip allowlist. The convergence-only
  parity test now passes against the available pinned schema surface; no broad
  schema weakening or hidden fallback was added.
- Storyboard compiles persist each still asset's finite authored render window
  as registry `duration`, while each clip retains explicit `from: 0`/`to`.
  FFmpeg accepts this declaration only for typed still images with no intrinsic
  ffprobe duration and loops each still input for its own bounded source
  window. Generic media still requires probe-derived duration and media `hold`
  remains unsupported.

## Validation evidence

- Focused repair/render/schema/hygiene suite: **72 passed**.
- Broader storyboard/compiler/expansion/FFmpeg focused suite: **97 passed**;
  hygiene, authority lint, compileall, and `git diff --check` passed.
- Exact convergence-only schema test:
  `tests/timeline/test_timeline_roundtrip_fixture.py::TimelineRoundTripFixtureTest::test_allowlist_parity_with_shared_schema`
  **passed**. Validation used the repo-supported pinned package via
  `ASTRID_TIMELINE_SCHEMA_PYTHONPATH=/Users/peteromalley/Documents/banodoco-workspace/packages/timeline-schema/python`.
- `python3 scripts/reshape/check_repo_hygiene.py`: **rc=0**.
- `PYTHONPATH=. python3 scripts/reshape/authority_lint.py`: **AUTHORITY LINT OK**.

## Real managed render

Using a disposable isolated root and the explicit schema environment, the
canonical sequence validated and compiled the real 25-section
`astrid-intro.storyboard.json` (`50` assets, `26` parent clips, `25` shots),
then ran:

```text
python3 -m astrid timelines render final-cleanup --project astrid-intro \
  --expected-version 2 --backend rendering.ffmpeg \
  --output-name final-cleanup.mp4 --json
```

Run `e82a1309f15d88e6a13e19c139` and task `98e7288ae523ea21e0fcda8541`
settled **succeeded**. Managed expansion recorded `25` pinned children and
`78c8efeb3ee1ddc084f727a6de084c1489a7c731c4d055d5d764890b14e50423` as the
expanded config hash. Output media `01m15n660fs1d8wswgf8dq2rk6` is verified
managed-local; ffprobe reports H.264/AAC, 1920×1080, yuv420p, and
`177.529000` seconds.

## Baseline-only limitations

The known clean-baseline capability failures remain intentionally unchanged:
layer overlay, five Remotion variants, and complex hybrid windows. Missing
optional development tools (`pytest_cov`, `mypy`, `ruff`, `build`) are an
environment limitation, not masked by this patch. No Remotion implementation,
schema package vendoring, or hidden validation fallback was added.
