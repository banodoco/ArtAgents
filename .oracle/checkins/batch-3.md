# Batch 3 oracle checkpoint

**Verdict:** PASS
**Commit:** fdf6dfae vs previous 963060ee
**Flash:** `.oracle/findings/oracle-b3-{diff,tests,critique}.txt`

```
PASS
- Commit `fdf6dfae` is 6 files, +1416: backends/threejs/{__init__.py,renderer.yaml,run.py}, pack.yaml +1, test_freeze.py +1, test_threejs_backend.py +727. `git diff --name-only 963060ee..fdf6dfae -- astrid/core/` empty. No PNG/mp4/node_modules/out/build committed.
- Identity: BACKEND_ID rendering.threejs (`run.py:71`), engine=threejs (`:538-539`), fragment key BACKEND_ID with renderer=threejs / 1.0.0 / capture_host=remotion / composition=ThreeTimelineComposition / legacy_v1 (`:562-568`). No surface claims rendering.remotion.
- Helpers: binds `_execute_remotion`, `_serialize_timeline`, `_render_provenance_payload`, `_canonical_profile`, `_input_path`, `_duration_frames`, `_load_registry_mapping` (`:61-68`). Owns support / `_protocol_render` / `_settings_from_request`. `_execute_remotion(..., composition_id=THREE_COMPOSITION_ID)` (`:524-532`). No second lock.
- window=None in support (`:363-365`) and render (`:429-434`). Own-namespace only (`:261`). Eligibility: empty/bg +```
PASS
- Commit `fdf6dfae` is 6 files, +1416: `backends/threejs/{__init__.py,renderer.yaml,run.py}`, `pack.yaml` +1, `test_freeze.py` +1, `test_threejs_backend.py` +727. `git diff --name-only 963060ee..fdf6dfae -- astrid/core/` empty. No PNG/mp4/`node_modules`/out/build committed.
- Identity: `BACKEND_ID=rendering.threejs` (`run.py:71`), `engine="threejs"` (`:538`), fragment key `rendering.threejs` with `renderer=threejs` / `1.0.0` / `capture_host=remotion` / `composition=ThreeTimelineComposition` / `legacy_v1` (`:562-568`). No surface claims `rendering.remotion`.
- Reuses only `_execute_remotion`, `_serialize_timeline`, `_render_provenance_payload`, `_canonical_profile`, `_input_path`, `_duration_frames`, `_load_registry_mapping` (`:61-68`). Owns `support` / `_protocol_render` / `_settings_from_request`. Calls `_execute_remotion(..., composition_id=THREE_COMPOSITION_ID)` (`:524-532`). No second lock.
- `window=None` in support (`:363`) and render (`:429`). Own-namespace only (`:261`). Eligibility: empty/background + exact 11 text fields; clip-specific rejections (`:147-216`).
- `renderer.yaml`: features all bool/str, command `[python3, backends/threejs/run.py]`, `audio_ownership: [rendered]`, `supports_windows: false`.
- `test_freeze.py` adds `rendering.threejs` to the frozen renderer set. `test_builtin_registration` inspects remotion/ffmpeg by id only — no edit required.
- Tests: 12 functions. Skip only via `_missing_environment` (`:61-88`) *before* render. Real empty: 1-frame h264+AAC+sidecar. Real text: `"420p" in pix_fmt`, frame-2≠frame-8 md5, sidecar identity. Host: 12 passed ~28s; checkpoint suite 56 passed / 2 pre-existing skips.
- Flash (`omp` deepseek-v4-flash): `.oracle/findings/oracle-b3-{diff,tests,critique}.txt` all PASS. Dead `_clip_end` / unused `_effective_registry_state` (~35 lines) noted, not acceptance-failing.
```

Batch 4 may start.
