# Baseline — Pluggable Timeline Renderers (Batch 1, T1.1)

Characterization of the **legacy monolith render path**
(`astrid/packs/rendering/executors/render/run.py`, 1615 lines) recorded so the
later backend extraction can be proven behavior-preserving. No refactor was
performed on `run.py`; this document only records today's behavior.

- Recorded: 2026-08-11
- Python: 3.11.11 (`PYENV_VERSION=3.11.11`)
- HEAD at recording: `efbfcaa` ("oracle: freeze stable plan + tasklist (megado phases 1-4)")
- **Reworked (T1.1R): 2026-08-12** — oracle batch-1 issues 1–2: leaf-vs-facade
  run-ownership distinction + facade characterization tests (issue 1);
  callsite inventory corrections/additions, real transition cases, coverage
  map, C0/C1 suite evidence, and corrected Sprint 08 record (issue 2). HEAD at
  rework: `f8af4b2` ("batch1: renderer contracts, schemas, pack extension,
  trusted registries, baseline characterization").

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

### C0 evidence (T1.1R): general pack/executor suites

Run on 2026-08-12 at HEAD `f8af4b2` (C1); the C0 snapshot (`6b2ff1a`) predates
any rendering characterization work and none of these failures are touched by
the C1 diff (verified via `git diff efbfcaa..f8af4b2`).

- **`pytest -q tests/packs`** → **25 failed, 1460 passed, 37 skipped, 181
  subtests passed** (288.45s). Failure breakdown (all pre-existing / outside
  the renderer scope):
  - 2 known **env-dependent** rendering failures (the recorded ones):
    `test_render_remotion_registry.py::test_registry_generation_skips_when_state_and_outputs_are_current`
    and `::test_render_discovers_fixture_local_effect_assets_without_real_local_pack`.
  - 6 `tests/packs/reigh/test_reigh_integration.py` + 6
    `tests/core/test_project_cli.py::EditCLITest` failures:
    `jsonschema ... 'tracks' is a required property` — the external
    `banodoco-workspace/packages/timeline-schema` dependency now requires
    `tracks`; the reigh/edit test fixtures predate that schema version
    (external-dependency drift, unrelated to rendering).
  - 5 `tests/packs/reigh/test_open_in_reigh.py` bridge-metadata failures
    (`AssertionError: 1 != 0`) — environment-dependent reigh bridge behavior.
  - 3 `tests/packs/test_generate_video_partial_manifest.py` failures
    (`'Namespace' object has no attribute 'video_ref'`) + 3
    `tests/packs/test_pack_enum_recoverability.py` enum-surface mismatches —
    `astrid/packs/generation/executors/generate_video/run.py` was present in
    the oracle base snapshot (`6b2ff1a`) and is not touched by C1.
  - 4 pack layout/validation failures (`[internal-schema] unexpected
    top-level directory: blender`): `test_pack_layout_contract.py`, `test_packs_cli.py`,
    `test_packs_validate.py` (×2) — `astrid/packs/blender/` was present in the
    oracle base snapshot and is not touched by C1.
- **`pytest -q tests/core --ignore=tests/core/rendering`** → **7 failed, 1463
  passed, 37 skipped, 26 subtests passed** (72.00s). Failures:
  `test_dataset_build_credentials_parity.py::test_canonical_provider_count`
  (host env registers a 7th provider — `DEEPSEEK_API_KEY`; environment-dependent)
  and the 6 `EditCLITest` `'tracks'` schema-drift failures above.
- `tests/core/rendering` is run separately because `pytest -q tests/packs
  tests/core` aborts at collection with an import mismatch: the duplicate
  basenames `tests/core/model_catalog/test_registry.py` and
  `tests/core/rendering/test_registry.py` collide (pre-existing structural
  issue). This suite is the batch-1 **contract/registry rework area** (oracle
  issues 3–9, worked in parallel by other agents) — its results are recorded
  in the batch-1 C1 evidence (331 passed for `tests/core/rendering` +
  pack-extension + registry + override suites at commit time). At T1.1R run
  time the suite is mid-rework (current local run: 44 failed / 45 passed, all
  failures being the in-flight contract/registry items) and is NOT part of
  this characterization.

### C1 evidence (T1.1R): Hype/iteration/editorial re-run

- **`pytest -q tests/packs/hype tests/packs/iteration tests/packs/editorial`**
  → **186 passed, 0 failed, 0 skipped** (46.42s) — byte-identical to the
  recorded C0 count (186/0/0): **no new failures**.
- New characterization suites (T1.1R):
  `pytest -q tests/packs/rendering/test_legacy_renderer_characterization.py
  tests/packs/rendering/test_render_facade_run_ownership.py` → **37 passed,
  0 failed** (5.74s).

## 3. Production callsite inventory of concrete render usage

Canonical executor id: `rendering.render`; runtime module
`astrid.packs.rendering.executors.render.run` (executor.yaml
`metadata.runtime_module`, line 134; `pipeline_step: "render"`, line 130).
`guard_canonical_entrypoint('rendering.render')` at run.py:7.

| File | Line | Kind | Detail |
||---|---|---|---|
| `astrid/packs/video_editing/orchestrators/iteration_video/run.py` | 25 | in-process import | `from astrid.packs.rendering.executors.render import run as render_executor` |
| `astrid/packs/video_editing/orchestrators/iteration_video/run.py` | 148 | in-process call | `run_builtin_render()` calls `render_executor.render(brief_out/"hype.timeline.json", brief_out/"hype.assets.json", brief_out/"hype.mp4")` (default engine `remotion`). Lines 141/394 reference `("rendering.render", ...)` only as declarative planned-command tuples, not spawns. |
| `astrid/packs/video_editing/orchestrators/iteration_video/plan_template.py` | 98 | subprocess spawn | `_build_render_cmd` builds a **direct** `{python_exec} -m astrid.packs.rendering.executors.render.run --timeline … --assets … --out {out}/iteration.mp4` string (lines 102–105); emitted into the v2 plan JSON as a shell command and spawned by the plan runner (direct `python -m ...render.run` form, not the canonical `astrid executors run` form). |
| `astrid/packs/video_editing/executors/cut/run.py` | 368 | **latent `ModuleNotFoundError` bug** | `from ..render.run import render as render_remotion` (line 368) inside `if args.render:` — resolves to `astrid.packs.video_editing.executors.render.run`, a **nonexistent sibling module** (no `executors/render` under `astrid/packs/video_editing/`). The `--render` branch crashes at import time; the call at line 370 is unreachable today. |
| `astrid/packs/video_editing/executors/cut/resume.py` | 165 | **latent `ModuleNotFoundError` bug** | `from ..render.run import render as render_remotion` (line 165) inside `if args.render:` — same nonexistent sibling module; the `--render` branch crashes at import time (call at line 167 unreachable). |
| `astrid/packs/video_editing/orchestrators/hype/steps.py` | 362 | subprocess spawn | `render` Step build_cmd: `*step_argv("render.py", args.python_exec), "--timeline", ..., "--assets", ..., "--out", ...` → resolves `pipeline_step "render"` → runtime module `astrid.packs.rendering.executors.render.run` → argv `[python, -m, astrid.packs.rendering.executors.render.run, ...]` (spawns `python -m ...render.run`) |
| `astrid/packs/video_editing/orchestrators/hype/plan_template.py` | 437 | subprocess spawn | `_build_render_cmd` builds the render command through `_executor_cmd(python_exec, "rendering.render", "{produces_root}", {...})` (lines 446–451) — the **canonical `astrid executors run rendering.render`** form (inputs `timeline` + `assets_registry`, optional `theme`); emitted into the v2 plan JSON and spawned by the plan runner. |
| `astrid/packs/editorial/executors/human_notes/run.py` | 251 | subprocess spawn | `_apply_pipeline` `render_cmd`: `*_step_argv("render.py", args.python_exec), "--timeline", ..., "--assets", ..., "--out", ...` — same `python -m astrid.packs.rendering.executors.render.run` spawn; run via `subprocess.run(cmd, check=True)` (line 261) |
| `tools/render_and_check.py` | 40 | canonical CLI spawn | `[py, "-m", "astrid", "executors", "run", "rendering.render", "--out", ..., "--input", "timeline=...", "--input", "assets_registry=..."]` run via `subprocess.run(render_cmd, cwd=REPO)` (line 46) — the canonical `astrid executors run rendering.render` form |

Summary: every production caller uses the monolith module — either
in-process (`render()` function), a direct `python -m ...render.run`
subprocess (hype `steps.py`, `human_notes/run.py`, iteration
`plan_template.py`), or the canonical `astrid executors run rendering.render`
CLI (`hype/plan_template.py` via `_executor_cmd`, `tools/render_and_check.py`),
which itself forks the same runtime module. The `cut/run.py` and
`cut/resume.py` `--render` branches are NOT working callers: their lazy import
targets a nonexistent sibling module and raises `ModuleNotFoundError` at
runtime (latent bugs).

## 4. Sprint 08 fixture state (parity test is opt-in)

The real parity test is **`tests/packs/test_renderer_parity.py`** (not
`tests/test_renderer_parity.py` as the fixture README claims — the README's
path is stale). Its properties:

- **OPT-IN / skipped by default**: the test is marked
  `@pytest.mark.renderer_parity` / `@pytest.mark.integration` /
  `@pytest.mark.opt_in` (lines 54–56) and skips itself unless
  `ASTRID_RENDERER_PARITY=1` (line 24, 58–59). It is not run by the default
  suites and is not in CI.
- **Hashes timeline JSON without rendering**: `_canonical_hash` (lines 49–51)
  sha256s the fixture payload (`json.dumps(sort_keys=True, separators=(",", ":")`)
  and compares against the committed `golden/<name>.sha256` (lines 76–85). No
  render happens.
- **Fixture dir**: `tests/fixtures/sprint08/` contains exactly **one file**:
  `README.md`, which documents that the directory is meant to hold
  `createAgentWorkflowTimelineFixture` / `createEmbedDemoTimelineFixture` JSON
  snapshots plus `golden/<name>.sha256` digests. No `.json` fixtures and no
  `golden/` directory are present.

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

Transition characterization (T1.1R — real transitions, previously none were
constructed) lives in `tests/packs/rendering/test_legacy_renderer_characterization.py`
(transition section, `_complex_clip_windows` with two back-to-back media clips,
fps 30, boundary at 2.0 s):

- **Default duration**: a non-empty transition dict without `duration` /
  `durationFrames` (e.g. `{"type": "crossfade"}`) uses `8 / fps` —
  `test_transition_default_duration_is_8_frames` locks the window
  `(2.0 − 8/30 − 0.25, 2.0 + 8/30 + 0.25)` floor/ceil-rounded to
  `(44/30, 76/30)`; `test_transition_default_duration_scales_with_fps` locks
  `(34/24, 62/24)` at fps 24.
- **`duration` vs `durationFrames`**: `transition.duration` (seconds) wins
  over `transition.durationFrames` — `test_transition_duration_seconds_overrides_default`
  (`(37/30, 83/30)`), `test_transition_duration_frames_divide_by_fps`
  (`(40/30, 80/30)`), `test_transition_duration_seconds_take_precedence_over_duration_frames`
  (both keys → seconds win).
- **Handle padding (0.25 s)**: non-transition complex windows pad by
  `handle_seconds=0.25` and round to frames —
  `test_transition_handle_padding_and_frame_rounding_without_transition`
  (`(0.0, 68/30)`), `test_transition_handle_padding_rounds_off_frame_boundaries`
  (`(7/30, 53/30)`).
- **Clip precedence**: a media clip with BOTH effects and a transition gets the
  transition window, not the effect window (`test_transition_takes_precedence_over_effect_window`);
  `transition` is honored ONLY on media clips — a text-card carrying a
  transition dict still gets the plain padded clip window
  (`test_transition_ignored_for_non_media_clip`); an empty `{}` transition
  dict is falsy and is NOT treated as a transition (no window).
- **Frame rounding / clamping**: `test_transition_longer_than_clip_clamps_to_timeline_bounds`
  locks `(0.0, 4.0)` when the transition exceeds the clip lead-in (start
  clamped to 0, end to duration). The raw helpers `_round_frame_time`,
  `_clip_duration_seconds`, `_clip_timeline_end_seconds`,
  `_timeline_duration_seconds` are pinned by the pre-existing unit tests in
  the same file (`test_timeline_duration_*`, `test_clip_duration_and_timeline_end_math`,
  `test_round_frame_time_modes`).

## 10. Run ownership: leaf module vs public facade (T1.1R correction)

The original T1.1 record proved only the LEAF boundary. The oracle review
(batch-1 issues 1–2) established that the PUBLIC facade DOES own a project run
whenever a project is resolved — `metadata.requires_timeline: false` only
skips timeline resolution, it does NOT disable run ownership.

### (a) Leaf module `astrid/packs/rendering/executors/render/run.py`

- `run.py` `main()` (lines 1556–1611) **never calls `prepare_project_run`**
  (from `astrid/core/project/run.py:145`) and **never creates a `run.json`**.
  Verified by grep: `prepare_project_run` and `run.json` appear nowhere in
  `astrid/packs/rendering/executors/render/run.py` (pinned by
  `test_run_module_never_prepares_project_run`).
- Render as a leaf is a **standalone, unattached** executor: it writes only the
  output video (`--out`, default name `hype.mp4`), a temporary
  `.remotion-props.json` (unlinked in `finally`, lines 1446/1530), staged
  effect assets under `project_dir/public/astrid-effects/<render_hash>/`
  (removed in `finally`, line 1531), and the provenance sidecar
  `{out}.provenance.json` (line 1232).
- Consistent with `executor.yaml` `metadata.requires_timeline: false` (line
  128) — the executor opts out of TIMELINE resolution, not of run ownership.
- `_delete_previous_render_outputs_for_timeline` (lines 1127–1150) is the only
  cross-run bookkeeping: it removes prior sibling `hype.mp4` + sidecar in
  `runs/` for the same timeline, unless `--keep-previous-renders` (lines
  1413–1414).

### (b) Public facade `rendering.render` via the executor runner

Invoked as `astrid executors run rendering.render` — equivalently
`run_executor(ExecutorRunRequest(executor_id="rendering.render", ...))` — the
facade goes through `astrid/core/execution/executor/runner.py` and
`astrid/core/contracts/capability_runner.py::CapabilityRunner.run` (the gate,
lines 106–154), which **DOES create a project run** when a project is
resolved:

- `CapabilityRunner.run` → `resolve_project_request`
  (`runner.py:1041`, `selected_project` in
  `astrid/core/project/guidance.py:107`) → `prepare_project`
  (`runner.py:236`) → **`_prepare_project_request`** (`runner.py:913`), which
  calls **`prepare_project_run`** (`astrid/core/project/run.py:145`) at
  `runner.py:936` with `requires_timeline` resolved from
  `metadata.requires_timeline` (`runner.py:931–935`; `False` for
  `rendering.render` → no timeline demand, but the run record IS created).
  The request is then rewritten at `runner.py:952–953`: `out` →
  `context.run_root` (unless a caller `out` is retained), `run_root` →
  `context.run_root`.
- `run_inner` (`runner.py:254`) → `_run_executor_inner` → `_run_builtin_executor`
  (`runner.py:567`); `rendering.render` declares an explicit `command`
  (executor.yaml lines 19–51) so the command is expanded from it and spawned
  as `python -m astrid.packs.rendering.executors.render.run --timeline … --out {out}/hype.mp4 …`.
- `finalize_project` (`runner.py:257`) → `_finalize_project_executor`
  (`runner.py:1016`) → `finalize_project_run`
  (`astrid/core/project/run.py:363`) writes/updates the ledger with status,
  `tool_id`, artifacts, and `project_resolution`.

Facade behavior is pinned by `tests/packs/rendering/test_render_facade_run_ownership.py`
(no real render: the render subprocess is a test-only no-op that writes
`hype.mp4` at the `--out` path; the real `rendering.render` definition is
loaded from the default registry):

1. **Standalone with a project** (`test_facade_standalone_with_project_creates_one_run_json_and_rewrites_out_to_run_root`):
   exactly ONE `run.json` is created, at the run root
   (`projects/<slug>/runs/<run_id>/run.json`); status `completed`,
   `tool_id: rendering.render`, `kind: executor`,
   `metadata.project_resolution: explicit`; `request.out` (None) is rewritten
   to the run root, so the spawned argv targets `<run_root>/hype.mp4`; the
   subprocess env carries `ASTRID_PROJECT_RUN=1` and `ASTRID_PROJECT_SLUG`.
2. **Task-attached reuse** (`test_facade_task_attached_reuses_run_context_without_new_run_json`):
   with matching `ASTRID_TASK_PROJECT/RUN_ID/STEP_ID` env, the facade reuses
   the orchestrator's run context (`run_root ==
   runs/<parent>/steps/render/v1`, `run_id == parent run id`) and creates **no
   NEW `run.json`** — only the orchestrator's parent run record exists.
   (The task gate's `active_run.json` demand is a separate, task-run concern;
   it is stubbed in the test and characterized by the task-run suites.)
3. **No project** (`test_facade_without_project_fails_before_creating_ledger`):
   `project=None` (and no session binding) → `ExecutorRunnerError`
   "project required" from `_resolve_project_request` (`runner.py:1051`)
   BEFORE any ledger write — no `run.json` anywhere, with or without `out`.
4. **Retained caller-selected output under attachment**
   (`test_facade_task_attached_retains_caller_selected_output`): when the
   project is AUTO-resolved (`project_was_auto_resolved=True`, e.g. session
   binding) inside a task run, the caller's `out` is RETAINED (passed as
   `record_out`, effective out stays the caller path) while the ledger still
   attaches to the task step root; the render argv targets the caller path.
   Note: an EXPLICIT `--project` combined with `--out` is rejected before any
   write (`reject_project_with_out`, `runner.py:921`, `project/run.py:86`).
5. **`run_root` in the request** (`test_facade_run_root_in_request_is_replaced_by_run_context_root`):
   a caller-supplied `request.run_root` is IGNORED/replaced for run creation —
   the ledger is created at `projects/<slug>/runs/<run_id>` and
   `result.run_root` is that real run root; the caller's path is left empty.

Leaf-vs-facade contrast: the LEAF (`python -m …render.run` / `render()`) never
touches the ledger; the FACADE (`astrid executors run rendering.render`) owns a
project run whenever a project is resolved — `requires_timeline: false` only
skips timeline resolution. Callers that want no ledger must invoke the leaf
directly (in-process `render()`), not the facade.

## 11. Props / theme / registry / staging / environment / generated-source map

Every behavior required by the T1.1 brief is either covered by existing tests
or newly added; all listed tests exercise the real `run.py` render path with
heavy dependencies (npx remotion / ffmpeg / asset server) mocked out — no real
render. No additional characterization tests were needed beyond the facade and
transition additions in T1.1R.

| Behavior | Coverage (file:line) | What it locks |
|---|---|---|
| **Props** (`.remotion-props.json` payload + removal) | `tests/packs/rendering/test_render_remotion_registry.py:301` (`test_render_regenerates_registries_before_remotion_and_writes_props`); golden `tests/golden/hype/merged_render_props.json` via `tests/packs/hype/test_hype_e2e.py:1040` (`test_hype_registry_and_merged_render_props_match_golden`) | props payload carries `timeline`/`assets`/`theme`; temp props file removed after render; merged render props match the committed golden |
| **Theme** (theme/composition env, `--theme` forwarding, active theme) | `tests/packs/rendering/test_render_remotion_registry.py:102` (`test_registry_generation_sets_theme_and_composition_env`); `tests/core/test_executor_runner_errors.py:215` (`test_builtin_render_omits_optional_theme_when_not_supplied_and_forwards_when_supplied`); golden `tests/golden/fixture_theme.json` | registry regen sets theme + composition env for the subprocess; executor argv omits `--theme` unless supplied and forwards it verbatim when supplied |
| **Registry** (generation skip/regen/cache/empty-assets synthesis) | `tests/packs/rendering/test_render_remotion_registry.py:134` (skip when current), `:150` (regen on state-hash diff), `:174` (regen on missing output), `:201` (cache tracks element edits + missing outputs), `:739` (`test_main_synthesizes_empty_asset_registry_when_assets_are_absent`); golden `tests/golden/hype/hype.assets.json` via `test_hype_e2e.py:1040` | registry regeneration triggers, cache invalidation, and synthesized empty asset registry behavior |
| **Staging** (effect-asset staging + cleanup) | `tests/packs/rendering/test_render_remotion_registry.py:385` (`test_render_stages_only_used_effect_assets_and_removes_them_after_success`), `:485` (`test_render_removes_staged_assets_and_props_after_remotion_failure`) | only used effect assets are staged; staged assets + props are removed after success and after failure |
| **Environment** (explicit render env, project-run marker) | `tests/packs/rendering/test_render_remotion_registry.py:770` (`test_remotion_render_env_is_explicit_not_host_inherited` — host secrets/`RENDER_HOST_ONLY` never reach remotion), `:102` (theme/composition env); facade env marker: `tests/packs/rendering/test_render_facade_run_ownership.py` (subprocess env carries `ASTRID_PROJECT_RUN=1` + `ASTRID_PROJECT_SLUG`) | render subprocess env is explicit, not host-inherited; facade runs are project-marked |
| **Generated-source** (URL assets, generated render argv, goldens) | `tests/test_url_pipeline_smoke.py:128` (`test_cut_main_writes_url_registry_with_prefetched_sha` — URL inputs prefetched into the registry); `tests/packs/hype/test_hype_e2e.py:494` (`test_generated_hype_render_command_parses_to_required_downstream_render_argv`), `:600` (repeat source grouped string scene items), `:630` (dictionary scene output rejected as for-each source); `tests/golden/hype/` fixtures | URL→registry pipeline, generated render command shape, and golden registry/props outputs |
| **Audio-reactive specialization** | `tests/packs/rendering/test_audio_reactive_colour.py:82` (element schema + fast spec), `:119` (ambiguous markers rejected), `:133` (`test_render_dispatches_compact_effect_to_ffmpeg_specialization` — engine-parametrized, mocked render), `:165` (real-ffmpeg render, skipped when ffmpeg/ffprobe absent) | the strict 2-clip contract, marker validation, and the engine-independent early dispatch |
| **Facade run ownership / out rewrite** (NEW, T1.1R) | `tests/packs/rendering/test_render_facade_run_ownership.py` | see section 10(b) — standalone run.json creation + out rewrite, task-attached reuse, `project=None` error, retained out under attachment, `run_root` replacement |
