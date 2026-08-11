# Baseline — Pluggable Timeline Renderers (Batch 1, T1.1)

Characterization of the **legacy monolith render path**
(`astrid/packs/rendering/executors/render/run.py`, 1615 lines) recorded so the
later backend extraction can be proven behavior-preserving. No refactor was
performed on `run.py`; this document only records today's behavior.

- Recorded: 2026-08-11
- Python: 3.11.11 (`PYENV_VERSION=3.11.11`)
- HEAD at recording: `efbfcaa` ("oracle: freeze stable plan + tasklist (megado phases 1-4)")

## 1. Dirty-tree snapshot origin

- Oracle base commit: **`6b2ff1a`** — `chore: snapshot dirty working tree as oracle base (user work preserved)`.
- That commit snapshots the dirty working tree (including user work) as the
  oracle baseline; `efbfcaa` (HEAD) freezes the stable plan + tasklist on top.
- All line numbers in this document refer to `run.py` as of `6b2ff1a`.

## 2. Baseline pytest results (before any new tests)

### `pytest -q tests/packs/rendering tests/packs/test_audio_render.py`

**2 failed, 40 passed, 3 skipped**

Failures (pre-existing, unrelated to renderer backend extraction):

1. `tests/packs/rendering/test_render_remotion_registry.py::RenderRemotionRegistryGenerationTest::test_registry_generation_skips_when_state_and_outputs_are_current`
   — `AssertionError: Expected 'run' to not have been called. Called 1 times.`
2. `tests/packs/rendering/test_render_remotion_registry.py::RenderRemotionRegistryGenerationTest::test_render_discovers_fixture_local_effect_assets_without_real_local_pack`
   — `AssertionError: False is not true : test assumes the developer checkout has real local effects`

Skip reasons (verbatim, as reported by `pytest -ra`):

1. `remotion/src/types.augmentations.ts absent (gitignored generated artifact); augmentation import smoke skipped`
   (`tests/packs/rendering/test_remotion_render_contract.py:23`)
2. `remotion/node_modules absent; typecheck smoke skipped`
   (`tests/packs/rendering/test_remotion_render_contract.py:68`)
3. `ffmpeg/ffprobe and remotion/node_modules are required`
   (`tests/packs/test_audio_render.py:30`)

### `pytest -q tests/packs/hype tests/packs/iteration tests/packs/editorial`

**186 passed, 0 failed, 0 skipped**

## 3. Production callsite inventory of concrete render usage

Canonical executor id: `rendering.render`; runtime module
`astrid.packs.rendering.executors.render.run` (executor.yaml
`metadata.runtime_module`, line 134; `pipeline_step: "render"`, line 130).
`guard_canonical_entrypoint('rendering.render')` at run.py:7.

| File | Line | Kind | Detail |
|---|---|---|---|
| `astrid/packs/video_editing/orchestrators/iteration_video/run.py` | 25 | in-process import | `from astrid.packs.rendering.executors.render import run as render_executor` |
| `astrid/packs/video_editing/orchestrators/iteration_video/run.py` | 148 | in-process call | `run_builtin_render()` calls `render_executor.render(brief_out/"hype.timeline.json", brief_out/"hype.assets.json", brief_out/"hype.mp4")` (default engine `remotion`). Lines 141/394 reference `("rendering.render", ...)` only as declarative planned-command tuples, not spawns. |
| `astrid/packs/video_editing/executors/cut/run.py` | 368 | in-process import (lazy, inside `if args.render:`) | `from ..render.run import render as render_remotion` |
| `astrid/packs/video_editing/executors/cut/run.py` | 370 | in-process call | `render_remotion(timeline_path, assets_path, out_dir/"hype.mp4", project_dir=REPO_ROOT/"remotion")` |
| `astrid/packs/video_editing/executors/cut/resume.py` | 165 | in-process import (lazy, inside `if args.render:`) | `from ..render.run import render as render_remotion` |
| `astrid/packs/video_editing/executors/cut/resume.py` | 167 | in-process call | `render_remotion(timeline_path_out, assets_path_out, out_dir/"hype.mp4", project_dir=REPO_ROOT/"remotion")` |
| `astrid/packs/video_editing/orchestrators/hype/steps.py` | 362 | subprocess spawn | `render` Step build_cmd: `*step_argv("render.py", args.python_exec), "--timeline", ..., "--assets", ..., "--out", ...` → resolves `pipeline_step "render"` → runtime module `astrid.packs.rendering.executors.render.run` → argv `[python, -m, astrid.packs.rendering.executors.render.run, ...]` (spawns `python -m ...render.run`) |
| `astrid/packs/editorial/executors/human_notes/run.py` | 251 | subprocess spawn | `_apply_pipeline` `render_cmd`: `*_step_argv("render.py", args.python_exec), "--timeline", ..., "--assets", ..., "--out", ...` — same `python -m astrid.packs.rendering.executors.render.run` spawn; run via `subprocess.run(cmd, check=True)` (line 261) |
| `tools/render_and_check.py` | 40 | canonical CLI spawn | `[py, "-m", "astrid", "executors", "run", "rendering.render", "--out", ..., "--input", "timeline=...", "--input", "assets_registry=..."]` run via `subprocess.run(render_cmd, cwd=REPO)` (line 46) — the canonical `astrid executors run rendering.render` form |

Summary: no production caller today uses anything but the monolith module —
either in-process (`render()` function), `python -m ...render.run` subprocess,
or the canonical `astrid executors run rendering.render` CLI (which itself
forks the same runtime module).

## 4. Empty Sprint 08 fixture state

`tests/fixtures/sprint08/` contains exactly **one file**:

- `README.md` — documents that the directory is meant to hold
  `createAgentWorkflowTimelineFixture` / `createEmbedDemoTimelineFixture` JSON
  snapshots plus `golden/<name>.sha256` digests, and that
  `tests/test_renderer_parity.py` skips itself when no fixtures/goldens are
  committed.

No `.json` fixtures and no `golden/` directory are present.

## 5. Legacy engine dispatch in run.py

Three engines, dispatched inside `render()` (lines 1400–1553):

| Engine | Implementation | Defined | Dispatched |
|---|---|---|---|
| `remotion` | npx Remotion render (subprocess `npx remotion render <composition> --props ... --output ...` lines 1493–1510); asset HTTP server lines 1450–1457; element registry regen lines 1443, 967–994 | — | default; `engine != "remotion"` → `ValueError(f"Unsupported render engine: {engine}")` (lines 1437–1438); auto-FFmpeg check line 1439; Remotion path lines 1441–1528. Also used per-segment by hybrid at lines 856–862. |
| `ffmpeg` | `_render_ffmpeg_media` (builds ffmpeg `-filter_complex` concat, lines 518–673) | line 518 | explicit `engine == "ffmpeg"` → lines 1435–1436; auto-route from nominal `remotion` → lines 1439–1440; hybrid all-ffmpeg shortcut → lines 834–835; hybrid ffmpeg segments → lines 853–854. |
| `hybrid` | `_render_hybrid` (window complex regions → Remotion segments, concat via `_concat_segments`, lines 827–902) | line 827 | `engine == "hybrid"` → lines 1425–1434. |

Dispatch order in `render()`: (1) audio-reactive specialization early check
(lines 1415–1424), (2) `hybrid`, (3) `ffmpeg`, (4) unknown-engine ValueError,
(5) nominal `remotion` with auto-FFmpeg eligibility (lines 1437–1440).

CLI `--engine` choices: `("remotion", "ffmpeg", "hybrid")`, default `remotion`
(line 1561).

## 6. Nominal-Remotion auto-FFmpeg routing

- Eligibility helper: **`_can_render_with_ffmpeg_media(timeline_path, assets_path)`**,
  defined at lines 676–689: loads timeline JSON + asset registry, runs
  `_validate_ffmpeg_media_timeline` (lines 491–515: exactly one visual track,
  media clips only, speed == 1.0, visual clips muted (`volume == 0`),
  non-overlapping audio clips), then requires ≥ 1 media clip on a visual track.
  Any exception → `False`.
- Used at line 1439 inside `render()` when `engine == "remotion"`: if True →
  `_render_ffmpeg_media` (line 1440); else → the full Remotion path.
- Net effect: a media-only timeline nominally requested with the default
  `remotion` engine never launches Node; it renders via ffmpeg.

## 7. Audio-reactive early selection

- Module import: line 36 `from astrid.packs.rendering.executors.render import audio_reactive_colour`.
  `EFFECT_ID = "audio-reactive-colour"`, `ADAPTER_ID = "audio-reactive-colour/v1"`
  (audio_reactive_colour.py:14–15).
- Entry predicate: `audio_reactive_colour.match_and_validate(timeline_data, registry, assets_path)`
  (audio_reactive_colour.py:106–274) returns `AudioReactiveColourSpec | None`
  — the strict whole-timeline contract check (exactly 2 clips = one
  `audio-reactive-colour` effect clip on a single visual track + one audio
  media clip, both at zero; params `schemaVersion == 1`, `initialColor`
  `#RRGGBB`, strictly increasing `events` frames; audio asset must be local).
- Dispatch: `_render_audio_reactive_colour_if_supported` (lines 1283–1397)
  gates on: exactly 2 clips with exactly 1 effect clip (lines 1294–1304),
  `_audio_reactive_ffmpeg_element(theme_path)` adapter match (lines 1269–1280,
  1305–1307), then `match_and_validate` (line 1309). On success it calls
  `audio_reactive_colour.render(spec, out_path)` (line 1315) and writes a
  provenance sidecar with `ffmpeg_specialization` + `audio_reactive_colour`
  keys (lines 1335–1358).
- `render()` calls it **first**, before any engine dispatch (lines 1415–1424);
  a non-None result short-circuits `engine=remotion|ffmpeg|hybrid` alike.

## 8. v1 provenance keys — `_write_render_provenance`

Function at lines 1173–1233. The dict construction (lines 1189–1226):

```python
payload: dict[str, Any] = {
    "schema_version": 1,                       # line 1190
    "engine": engine,                          # line 1191
    "output": str(out_path.resolve()),         # line 1192
    "timeline": str(timeline_path.resolve()),  # line 1193
    "assets_registry": str(assets_path.resolve()),  # line 1194
    "project_dir": str(project_dir.resolve()), # line 1195
    "composition_id": composition_id,          # line 1196
    "active_pack_order": _active_pack_order_for_provenance(),  # line 1197
    "active_theme": _active_theme_for_provenance(theme_path, active_theme),  # line 1198
    "registry_hash": registry_state.get("hash"),  # line 1199
    "registry_state": registry_state,          # line 1200
    "resolved_effect_ids": [str(effect["effect_id"]) for effect in effects if "effect_id" in effect],  # line 1201
    "resolved_effects": effects,               # line 1202
    "source_pack_ids": sorted({str(effect["source_pack_id"]) for effect in effects if isinstance(effect, dict) and effect.get("source_pack_id")}),  # lines 1203-1209
    "element_roots": sorted({str(effect["element_root"]) for effect in effects if isinstance(effect, dict) and effect.get("element_root")}),  # lines 1210-1216
    "staged_asset_ids": sorted({str(asset_id) for effect in effects if isinstance(effect, dict) for asset_id in effect.get("staged_asset_ids", ())}),  # lines 1217-1224
    "staged_asset_root": stage_summary.get("root"),  # line 1225
}
```

Conditional keys: `segments` added when `segments is not None` (lines
1227–1228); `segment_provenance` added when `segment_provenance is not None`
(lines 1229–1230). Written as `{out_path}.provenance.json` (sidecar path
helper `_render_provenance_sidecar_path`, lines 1123–1124), `sort_keys=True`,
`indent=2` (line 1232).

Audio-reactive runs additionally mutate the sidecar post-write with
`ffmpeg_specialization` and `audio_reactive_colour` (lines 1347–1358).

## 9. Transition units

- `_clip_duration_seconds(clip)` (lines 399–405): `max(0, (to - from)) / speed`;
  `speed <= 0` raises `ValueError`.
- `_clip_timeline_end_seconds(clip)` (lines 408–417): media clip →
  `at + _clip_duration_seconds`; `hold` numeric → `at + max(0, hold)`;
  numeric `to` → `to`; else `at`.
- `_timeline_duration_seconds(timeline_data)` (lines 420–427): explicit
  `metadata.duration_seconds` (numeric) wins; else
  `metadata.expected_duration_seconds`; else `max(_clip_timeline_end_seconds
  over clips, default 0.0)`.
- `_round_frame_time(seconds, fps, *, mode)` (lines 430–438):
  `frames = seconds * fps`; `floor` → `int(frames // 1)`, `ceil` →
  `int(-(-frames // 1))`, else Python `round(frames)`; result `frame / fps`.
- `_complex_clip_windows` (lines 692–763): default transition duration is
  **8 frames / fps** (line 726), overridable by `transition.duration`
  (seconds) or `transition.durationFrames / fps` (lines 727–731); windows are
  padded by `handle_seconds=0.25` and frame-rounded (floor/ceil) (lines
  734–753), then sorted + merged (lines 756–763).
- `_hybrid_segments(timeline_data)` (lines 766–784): total duration =
  `_round_frame_time(_timeline_duration_seconds, fps, mode="ceil")` (line
  768); no complex windows → single `{"engine": "ffmpeg", "from": 0.0, "to":
  duration}` (lines 770–771); otherwise alternating `ffmpeg`/`remotion`
  segments clipped to `[0, duration]` (lines 772–784).

## 10. Standalone vs attached run ownership

- `run.py` `main()` (lines 1556–1611) **never calls
  `prepare_project_run`** (from `astrid/core/project/run.py:145`) and **never
  creates a `run.json`**. Verified by grep: `prepare_project_run` and
  `run.json` appear nowhere in `astrid/packs/rendering/executors/render/run.py`.
- Render is a **standalone, unattached** executor: it writes only the output
  video (`--out`, default name `hype.mp4`), a temporary `.remotion-props.json`
  (unlinked in `finally`, lines 1446/1530), staged effect assets under
  `project_dir/public/astrid-effects/<render_hash>/` (removed in `finally`,
  line 1531), and the provenance sidecar `{out}.provenance.json` (line 1232).
- Consistent with `executor.yaml` `metadata.requires_timeline: false` (line
  128) — the executor opts out of project-run attachment.
- `_delete_previous_render_outputs_for_timeline` (lines 1127–1150) is the only
  cross-run bookkeeping: it removes prior sibling `hype.mp4` + sidecar in
  `runs/` for the same timeline, unless `--keep-previous-renders` (lines
  1413–1414).
