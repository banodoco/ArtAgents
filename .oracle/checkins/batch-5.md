# Batch 5 oracle checkpoint

**Verdict:** PASS
**Commit:** 8723ca05 vs previous af907878
**Flash:** `.oracle/findings/oracle-b5-{tests,diff,critique}.txt`

```
PASS
- Commit `8723ca05` is 3 test files, +612: `test_threejs_hybrid.py` +289, `test_remotion_backend.py` +145, `test_threejs_backend.py` +178. `git diff --name-only af907878..8723ca05 -- astrid/core/` empty. No PNG/mp4/`node_modules`/out/build committed. Range also contains `.oracle/checkins/batch-4.md` (checkpoint-4 bookkeeping, not this commit).
- Mixed: genuine text `[0,0.5)` + lavfi media `[0.5,1.0)` through public `render(backend="rendering.threejs-hybrid")`. Exact `segments_v2` `[(rendering.threejs,0,12),(rendering.remotion,12,24)]`; planner + `rendering.ffmpeg-finalizer`; `support_decision.backend == renderer.id` both; fragments threejs+remotion; `legacy_v1.engine=threejs`; `audio_ownership=rendered`. ffprobe: h264, `"420p" in pix_fmt`, 320×180, `time_base=1/12288`, `nb_read_frames=24`, AAC```
PASS
- Commit `8723ca05` is 3 test files, +612: `test_threejs_hybrid.py` +289, `test_remotion_backend.py` +145, `test_threejs_backend.py` +178. `git diff --name-only af907878..8723ca05 -- astrid/core/` empty. No media/caches committed.
- Mixed: genuine text `[0,0.5)` + lavfi media `[0.5,1.0)` via public `render(backend="rendering.threejs-hybrid")`. Exact `segments_v2` `[(rendering.threejs,0,12),(rendering.remotion,12,24)]`; planner + `rendering.ffmpeg-finalizer`; `support_decision.backend == renderer.id` both; fragments threejs+remotion; `legacy_v1.engine=threejs`; ownership `rendered`. ffprobe: h264, `"420p" in pix_fmt`, 320×180, `time_base=1/12288`, `nb_read_frames=24`, AAC, duration `1.0±0.1`; two-render sha256; frame0≠frame12 md5.
- Remotion: public `render(backend="rendering.remotion")` (not mocked); engine/fragment remotion; `rendering.threejs` absent; real 12-frame h264 320×180 AAC.
- Lock: `threejs._execute_remotion is remotion_backend._execute_remotion`; spawn; real lock around stubbed CLI (`remotion/run.py:613`); remotion blocked 0.3s; one `*.lock`.
- Offline: `npm config set offline true` around a real threejs render; restored in `finally`.
- Skips only `_missing_environment` before render. Host T5.7: 98 passed, 2 pre-existing skips.
- Flash (`omp` deepseek-v4-flash): `.oracle/findings/oracle-b5-{tests,diff,critique}.txt` all PASS. Finalizer fragment not asserted (T5.3 asks Three+Remotion fragments + routing.finalizer). Helper dup + global npm-offline mutation noted, not blocking.
```

Batch 6 may start.
