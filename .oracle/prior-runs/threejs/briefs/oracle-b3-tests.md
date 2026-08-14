# Oracle Batch 3 — tests, preflight, real-render assertions (research only)

Repo: /Users/peteromalley/Documents/reigh-workspace/Astrid-threejs-oracle
Commit: fdf6dfae
Do not edit any files. Report verified facts only. Cite file:line.

## Tasks

1. Read tests/packs/rendering/test_threejs_backend.py in full.

2. List every test function name. Confirm coverage for:
   - static manifest discovery
   - empty/text support accept
   - every rejection class with stable clip reasons
   - own-namespace config parsing
   - non-None window rejection
   - protocol failures
   - identity invariants (support backend, fragment key, engine=threejs, no rendering.remotion identity)
   - rendered ownership
   - fixed composition
   - backend fragment/provenance
   - environment preflight
   - shared Remotion lock reuse
   - two real-render tests: empty timeline + text timeline through public service

3. Preflight / skip policy (CRITICAL):
   - Find every pytest.skip / skipif / xfail.
   - Read the preflight helper used by real-render tests.
   - Skip is allowed ONLY for genuinely missing binaries/packages (node, npx, ffprobe, remotion project, three, r3f) or unavailable WebGL context.
   - FAIL if an ordinary render failure (nonzero remotion, bad mp4, assertion error, timeout after env is present) is converted into a skip.
   - Cite the skip conditions exactly.

4. Real-render assertions: confirm both real-render tests probe with ffprobe for:
   codec (h264), dimensions, fps, frame count, duration, yuv420p, AAC.
   Confirm they extract a frame and assert non-background pixels + checksum.
   Confirm sidecar assertions for: resolved_backend, segments_v2[].renderer.id, backend_fragments.rendering.threejs, audio_ownership rendered, engine threejs.
   Empty render must assert one valid frame.

5. Check tests/packs/rendering/test_builtin_registration.py was NOT modified in fdf6dfae (host says only test_freeze.py +1). If it was not modified, confirm whether registration tests still pass by reading the current expected surface — does test_builtin_registration already discover backends dynamically, so no edit was needed? Cite evidence.

6. Do NOT re-run the full real-render suite (host already ran 12 passed ~28s including both real renders, and 56 passed / 2 skipped on the checkpoint suite). You MAY grep the test file and, if cheap, run:
   `PYENV_VERSION=3.11.11 python -m pytest -q tests/packs/rendering/test_threejs_backend.py -k 'not real_render' --tb=no`
   only if you need to confirm non-render tests collect. Do not spend more than 60s on pytest.

## Output (<350 words)

```
VERDICT: PASS | FAIL
TESTS: <count> functions: <names>
COVERAGE_GAPS: none | <missing classes>
SKIPS: <each skip with condition>
SKIP_POLICY: honest | converts-render-failure-to-skip
REAL_EMPTY: ffprobe+1-frame+sidecar | <gap>
REAL_TEXT: ffprobe+pixels+sidecar | <gap>
SIDECAR: resolved_backend / segments_v2.renderer.id / fragments.rendering.threejs / audio_ownership=rendered / engine=threejs | <gap>
BUILTIN_REG: no-edit-needed (why) | missing-edit
ISSUES: none | numbered list
```
