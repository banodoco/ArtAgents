# Cleanup Execution Brief — C0, C1a, C2, C3 (three.js renderer inelegance)

You are the EXECUTOR (DeepSeek V4 Flash). Work in `/Users/peteromalley/Documents/reigh-workspace/Astrid-threejs-cleanup` (branch `cleanup-threejs`, base 856798fe + plan commit f5485f58). Execute ONLY the changes below. Do NOT broaden scope. Do NOT edit anything under `astrid/core/`. Do NOT run the full test suite or formatters/linters beyond the specified commands. This is a surgical cleanup — a literal move of helpers, a dedup, a test-helper collapse, a dep pin.

Environment: `PYENV_VERSION=3.11.11`; `PATH="$HOME/.nvm/versions/node/v24.17.0/bin:$PATH"` for npm/remotion. The worktree's remotion has node_modules + a working chrome shell (already set up).

The plan is at `.oracle/plan.md` (Grok). The swarm findings are at `.oracle/findings/0{1-5}-*.txt`. Read the plan's C0/C1/C2/C3 sections fully before starting. The plan's LEAVE table is binding — do NOT do any of the listed "leave" items.

## Context

The three.js renderer epic merged (856798fe) with known inelegance: threejs/run.py imports 7 private remotion helpers (6 are backend-neutral), the 90kHz+AAC mux profile is triplicated, test scaffolding is duplicated across 4 test files, and `@remotion/*` 4.0.455 has an upstream extract-zip bug. A swarm explored; Grok planned C0-C3.

**PROBE VERDICT (already determined — host ran it):** a raw `rendering.threejs` artifact probes video `time_base 1/90000`, audio aac 48000 stereo. **The 90000 + AAC declaration is CORRECT.** So C1 = extraction ONLY (C1a); do NOT delete the time_base/AAC fields. Do NOT change docs/reference/threejs-renderer.md:117.

## C0 — Extract backend-neutral helpers (F2 + F4 production)

Create `astrid/packs/rendering/backends/_shared/__init__.py` (there is NO `backends/__init__.py` — the module is `astrid.packs.rendering.backends._shared`; a package without a parent `__init__` is fine as namespace/packaging handles it — verify the wheel still packs it). Move these as a LITERAL cut (copy the exact body, no behavior change) from `astrid/packs/rendering/backends/remotion/run.py`:

| Move | From (remotion/run.py) | Notes |
|---|---|---|
| `_input_path` | :817 | 3-line path resolver |
| `_load_registry_mapping` | :878 | |
| `_serialize_timeline` | :126 | |
| `_duration_frames` | :1051 | path+profile form; do NOT unify with ffmpeg's probe-form |
| `_canonical_profile` | :887 | **RETYPE** 3rd arg `settings: _RenderSettings` → `theme_path: Path \| None` (body only reads `settings.theme_path`) |
| `_render_provenance_payload` | :483 | **payload keys unchanged** |
| deps: `_resolve_theme_path`, `_theme_for_props`, `_theme_slug_for_render_default`, `_resolved_theme_for_render` | :134-195 | needed by `_canonical_profile` |
| deps: `_active_pack_order_for_provenance`, `_active_theme_for_provenance` | :460, :472 | needed by provenance |
| `_profile_mismatches` | :904 | also delete threejs's byte-identical copy (:298-311) |
| `_parse_min_free_gb(value) -> float \| None` | NEW (body = remotion:860-868 = threejs:268-276) | |
| `_reject_unknown_config(config, allowed, backend_id)` | NEW (body = remotion:836-838 = threejs:251-253) | |

`_shared/__init__.py` must import ONLY `astrid.core` (NO `from astrid.packs` imports — verify with rg after).

**Call-site rewires:**
- `remotion/run.py`: `from astrid.packs.rendering.backends._shared import <names>` and KEEP the same private names bound in-module (legacy_engine + tests patch `remotion._X` — re-exports preserve them). Change `_canonical_profile(..., settings.theme_path)` at its call sites. Use `_reject_unknown_config` + `_parse_min_free_gb` inside `_settings_from_request`.
- `threejs/run.py`: import the 6 neutrals + `_profile_mismatches` + config helpers from `_shared`. KEEP ONLY `_execute_remotion = remotion_backend._execute_remotion` from remotion. Delete the local `_profile_mismatches` + local config snippets. `_canonical_profile(..., settings.theme_path)` at :388 and :503. The identity assert at `test_threejs_backend.py:790` (`threejs._execute_remotion is remotion_backend._execute_remotion`) MUST stay valid.
- `legacy_engine.py`: DO NOT TOUCH (its 26 remotion aliases keep working via re-export).
- `ffmpeg/run.py`: DO NOT RETARGET `_render_provenance_payload` — `test_ffmpeg_support.py:478` patches `ffmpeg.remotion_backend._render_provenance_payload`; ffmpeg still imports remotion for `_effective_registry_state`, `_effect_registry_for_assets`, `_source_pack_id`, `_render_provenance_sidecar_path`.

## C1a — Dedup the 90kHz + AAC mux profile

Add to `_shared/__init__.py`:
```python
def _remotion_mux_profile(profile: RenderProfile) -> RenderProfile:
    return replace(
        profile,
        time_base=(1, 90000),
        audio_codec=profile.audio_codec or "aac",
        audio_sample_rate=profile.audio_sample_rate or 48000,
        audio_channel_layout=profile.audio_channel_layout or "stereo",
    )
```
Replace the three sites: remotion support :1017-1024, remotion render :1095-1109, threejs `_render_declared_profile` :314-321. Delete threejs's `_render_declared_profile` function. Remotion re-exports `_remotion_mux_profile`. Do NOT delete the time_base/AAC force (probe says it's correct).

## C2 — Test helper collapse

New `tests/packs/rendering/_helpers.py` (import from `tests.packs.rendering._helpers`):

| Helper | Action |
|---|---|
| `_execution_env` | one PATH prepend (python bin + node bin). Replaces threejs :106, remotion `_remotion_execution_env` :967, hybrid :674. Inline threejs `_child_path_on_front` into it; delete that helper |
| `_frame_md5` | verbatim ×2 (threejs :587, hybrid :715) → share |
| `_probe` | ship the HYBRID SUPERSET (`-count_frames` + `time_base,nb_read_frames`); threejs's extra `duration` keys are unused — drop them |
| `_source_video(tmp_path, *, audio=False)` | hyperframes :470 video-only vs hybrid :561 +aac; `audio=True` is the hybrid body |

Rewire imports in: `tests/packs/rendering/test_threejs_backend.py`, `test_remotion_backend.py`, `tests/core/rendering/test_threejs_hybrid.py`, `test_hyperframes_backend.py`. Hybrid already does `from tests.packs.rendering.test_threejs_backend import _missing_environment` — KEEP that (env-skip stays put; do NOT merge the env-skip trio — plan says LEAVE).

## C3 — Pin @remotion/* to 4.0.509

- `remotion/package.json`: pin all eight to `4.0.509` — `@remotion/cli`, `@remotion/google-fonts`, `@remotion/layout-utils`, `@remotion/media`, `@remotion/renderer`, `@remotion/three`, `remotion`, `@remotion/bundler`. Leave `@react-three/fiber 8.18.0`, `three 0.185.1`, `@types/three 0.185.4` as-is.
- `cd remotion && npm install` (NOT npm ci) to regenerate the lockfile.
- Confirm the lock no longer depends on `extract-zip` (`grep extract-zip remotion/package-lock.json` → empty).
- `docs/reference/threejs-renderer.md:51` table: `@remotion/three` `4.0.509`.
- Check `astrid/packs/rendering/skill/SKILL.md` for a remotion version mention (plan says :123 "Requires Remotion 4.0.509 (pinned)") — update ONLY if it pins a specific version; if it says 4.0.455, bump it; if it doesn't pin, leave it.
- Do NOT add/remove any `chrome-headless-shell/VERSION` marker (it's a local cache file, not repo content).

## Verification (run in order, fix what breaks)

C0 verify:
```
rg -n "from astrid\.packs|import astrid\.packs" astrid/packs/rendering/backends/_shared   # must be EMPTY
PYENV_VERSION=3.11.11 python -m pytest -q tests/packs/rendering/test_threejs_backend.py tests/packs/rendering/test_remotion_backend.py tests/packs/rendering/test_remotion_locking.py tests/packs/rendering/test_ffmpeg_backend.py tests/packs/rendering/test_ffmpeg_support.py tests/packs/rendering/test_legacy_renderer_characterization.py tests/packs/test_renderer_parity.py tests/core/rendering
PYENV_VERSION=3.11.11 python scripts/reshape/compare_ruff_baseline.py   # count must stay <= 1469
```

C2 verify:
```
PYENV_VERSION=3.11.11 python -m pytest -q tests/packs/rendering/test_threejs_backend.py tests/packs/rendering/test_remotion_backend.py tests/packs/rendering/test_hyperframes_backend.py tests/core/rendering/test_threejs_hybrid.py
```

C3 verify (real renders — PATH needs node 24 + the worktree chrome shell, already present):
```
cd remotion && PATH="$HOME/.nvm/versions/node/v24.17.0/bin:$PATH" npm run typecheck
PYENV_VERSION=3.11.11 PATH="$HOME/.nvm/versions/node/v24.17.0/bin:$PATH" python -m pytest -q \
  tests/packs/rendering/test_remotion_locking.py \
  tests/packs/rendering/test_remotion_backend.py::test_remotion_real_render_under_global_angle_keeps_identity \
  tests/packs/rendering/test_threejs_backend.py::test_threejs_real_render_text_timeline_through_public_service \
  tests/packs/rendering/test_threejs_backend.py::test_threejs_real_render_empty_timeline_through_public_service \
  tests/packs/test_renderer_parity.py
```

Final gate:
```
PYENV_VERSION=3.11.11 python -m pytest -q tests/packs/test_renderer_parity.py tests/packs/rendering/test_legacy_renderer_characterization.py tests/packs/rendering/test_threejs_backend.py tests/packs/rendering/test_remotion_backend.py tests/packs/rendering/test_ffmpeg_backend.py tests/core/rendering
make ruff
make remotion-typecheck
make renderer-parity
```

## Protocol
- Commit per change: `cleanup: C0 shared helper extraction`, `cleanup: C1a mux profile dedup`, `cleanup: C2 test helper collapse`, `cleanup: C3 remotion 4.0.509 pin`. (Or one commit if you prefer atomicity — but each change independently verifiable is better for the oracle.)
- Report <500 words: what moved where, the probe verdict you were given, test counts per change, the extract-zip confirmation, the `_shared` rg-import check, ruff count, final git status. Evidence-first.
