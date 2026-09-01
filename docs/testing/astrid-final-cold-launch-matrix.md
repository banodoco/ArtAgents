# Final Astrid Stage 1 cold-launch matrix

The executable final matrix is
`tests/stage1/test_final_cold_launch_matrix_luna.py`. It is intentionally
no-mock: the test archives the exact runtime release candidate, creates a fresh
current-Mac-shaped `HOME`, starts the neutral runtime through the real
`banodoco-local up --profile astrid` path, then drives Astrid and the generic
host over loopback.

Run it from the Astrid checkout:

```bash
PYTHONPATH=.:../banodoco-workspace-runtime-stage1-convergence/packages/python \
  python3 -m pytest -q tests/stage1/test_final_cold_launch_matrix_luna.py
```

The matrix is serialized where state is shared, but uses real independent
processes for the two concurrent launchers. It proves:

- fresh trusted bootstrap, persisted-profile env-less relaunch, and one-owner
  concurrent launch;
- current-Mac support/catalog/discovery paths, owner-only credentials,
  loopback advertisement, and secret/database-path absence from discovery;
- Astrid CLI project/media admission followed by SDK timeline, shot, and
  reference composition, including source-file removal after managed ingest;
- generic CPU capability registration, readiness, claim, subprocess execution,
  CAS settlement, task cancellation/retry, and restart recovery;
- runtime kill/restart epoch advancement and stale-attempt settlement fencing;
- a real FFmpeg subprocess producing an MP4 plus provenance, `ffprobe`
  validation, CAS digest verification, and attempt-directory cleanup;
- neutral doctor health after mutation and the generated TypeScript
  second-product actor against the same restarted runtime.

The test fails (rather than skips) when `ffmpeg`, `ffprobe`, `node`, or `npm`
is unavailable. Remotion's separate acceptance test remains opt-in because its
dependency tree is not part of the supported Stage 1 cold-launch requirement;
the Stage 1 blueprint requires the registered Astrid render/FFmpeg path and
explicitly makes broader dependency/platform certification post-beta.

The runtime archive is pinned in the test to:
`7ebb2c9c9cf82e1b6f1be38e95ea09643d38e19c`.
