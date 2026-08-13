# Batch 4 oracle checkpoint

**Verdict:** PASS
**Commit:** af907878 vs previous fdf6dfae
**Flash:** `.oracle/findings/oracle-b4-{algo,tests,critique}.txt`

```
PASS
- Commit `af907878` is 7 files, +1304/−2: planners/threejs_hybrid/{__init__.py,planner.yaml,run.py}, pack.yaml +1, test_threejs_hybrid.py +540, test_freeze.py, test_builtin_registration.py. `git diff --name-only fdf6dfae..af907878 -- astrid/core/` empty. No PNG/mp4/node_modules/out/build committed. Working-tree extras are untracked `.oracle/*` only.
- Identity: BACKEND_ID rendering.threejs-hybrid (`run.py:77`), THREE/REMOTION/FINALIZER ids (`:79-81`). planner.yaml: command `[python3, planners/threejs_hybrid/run.py]`, operations [support, plan], features all bool.
- Algorithm: strictly-overlapping merge (`:134-155`); clip frames round(seconds*fps) min 1 (`:116-131`); total_frames=ceil(duration*fps) (`:242`); 1/4s Remotion handle capped next-occupied+boundary (`:199-224`); gaps+tail Remotion (`:288-297`); coalesce adjacent same-renderer (`:301-311`); exact half-open assert ```
PASS
- Commit `af907878` is 7 files, +1304/−2: `planners/threejs_hybrid/{__init__.py,planner.yaml,run.py}`, `pack.yaml` +1, `test_threejs_hybrid.py` +540, planner-only edits to `test_freeze.py` / `test_builtin_registration.py`. `git diff --name-only fdf6dfae..af907878 -- astrid/core/` empty. No PNG/mp4/`node_modules`/out/build committed.
- Frozen algorithm in `run.py`: strictly-overlapping merge (`:134-155`); `round(seconds*fps)` min-1 (`:116-131`); `total_frames=ceil(duration*fps)` (`:242`); 1/4s Remotion handle capped at next occupied + boundary (`:199-224`); gaps+tail Remotion (`:288-297`); coalesce (`:301-311`); exact half-open assert (`:315-348`).
- Eligibility **imports** backend `_support_reasons` (`:61-62`), not duplicated. Any ineligible clip → whole component Remotion (`:257-261`).
- Real support: `registry.get` + `resolve_evidence`; `support_decision.backend != resolved_id` raises (`:552-573`). Finalizer pinned `rendering.ffmpeg-finalizer`. Empty timeline: planner support rejects (`:393-398`); direct `rendering.threejs` still accepts (`test_threejs_backend.py:234`).
- Timescale: 24→`(1,12288)`, 30→`(1,15360)`; NTSC keeps large numerator. `planner.yaml`: id `rendering.threejs-hybrid`, command `[python3, planners/threejs_hybrid/run.py]`, operations `[support, plan]`, features bool-only.
- Tests cover every characterized exact window (text-only, overlap, text→media→text, effects/transition/opacity/audio-fades/non-base media, gaps, tail, handles, coalesce, empty reject, tiling, support identity). Host `_window_plan` probes match. Oracle re-ran hybrid+freeze+builtin: **41 passed**. Flash (`omp` deepseek-v4-flash): `.oracle/findings/oracle-b4-{algo,tests,critique}.txt` all PASS. Flash’s 7 pytest fails were omp-sandbox missing `timeline-schema` on untouched backend tests — not a Batch 4 regression. Host: 96 on the six-file suite.
```

Batch 5 may start.
