Explore in depth: the dead code and duplication inside the three.js backend/planner and the rendering test suite — the #4 inelegance flagged after the three.js epic.

Context: The oracle's elegance critiques flagged: (a) dead code shipped in batch 3 and removed in batch 6 (`_effective_registry_state` binding, `_clip_end` in backends/threejs/run.py) — suggesting MORE dead code may remain; (b) per-backend duplication of `_settings_from_request`-style config parsing; (c) duplicated test scaffolding across test_threejs_backend.py, test_remotion_backend.py, test_hyperframes_backend.py (env-skip helpers, asset fixtures, node-on-path context managers, ffprobe assertion helpers).

Investigate and report VERIFIED facts with file:line evidence:

1. **Dead code in the new files**: scan `astrid/packs/rendering/backends/threejs/run.py` and `astrid/packs/rendering/planners/threejs_hybrid/run.py` for: unused imports, unused functions (defined but never called), unused bindings (assigned remotion helpers never invoked), dead branches. Cross-check with ruff (`PYENV_VERSION=3.11.11 python -m ruff check <files>`) AND manual review — ruff catches F401/F841 but not "defined but never called". List every suspect with the evidence it's dead.
2. **Config parsing duplication**: compare the `_settings_from_request`-equivalent in threejs/run.py vs remotion/run.py. How much is identical vs namespace-specific? Could a shared helper parameterized by backend id work? Quote both.
3. **Test scaffolding duplication**: list the shared-pattern helpers in `tests/packs/rendering/test_threejs_backend.py`, `test_remotion_backend.py`, `test_hyperframes_backend.py`:
   - env-skip preflight (`_require_hyperframes_environment`, `_missing_environment`, `_require_threejs_environment`) — compare their logic (node version scan? nvm? ffmpeg check? node_modules check?)
   - node-on-path context managers
   - source-video/asset-registry fixture builders (`_source_video` — is it duplicated? ffmpeg lavfi color source?)
   - ffprobe assertion helpers (codec/dims/frames/duration checks)
   - provenance sidecar assertion helpers
   For each: is it verbatim-duplicated, near-duplicated (drifted), or legitimately different? Is there an existing shared test helper module (`tests/helpers/`? `tests/conftest.py`? `tests/_lifecycle_fixtures.py`?) they SHOULD live in? Quote the existing helper locations.
4. **The extraction tradeoff**: a shared `tests/packs/rendering/_helpers.py` (or conftest fixtures) — what moves, what breaks (test discovery? import paths?), and does it actually reduce duplication enough to justify it (KISS/YAGNI — a 20-line helper duplicated twice may not be worth extracting)?
5. **The settings duplication**: is `_settings_from_request` in threejs/run.py even correct — does it read the right namespace, reject unknown keys, and could it be deleted in favor of something already shared?

Rank findings by relevance to "remove dead code and reduce real duplication without over-abstracting". <350 words. Evidence with file:line. For each finding say FIX / LEAVE with reasoning.
