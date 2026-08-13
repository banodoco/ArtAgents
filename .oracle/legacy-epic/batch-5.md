I'll treat this as a read-only Batch 5 checkpoint: first load the megado/checkpoint process, then verify each T5 acceptance item against the worktree and evidence.I'll pull the frozen tasklist, Batch 5 commits, and prior checkpoint artifacts so the review is against the actual acceptance criteria.There's already a Batch 5 check-in on disk. I'll read the frozen acceptance criteria and then independently verify the claimed work.I'll fan the seven acceptance items to isolated reviewers and inspect the critical contracts myself so the verdict isn't just a replay of the submitted evidence.Subagents are scanning the seven items. I'll read the attached-render helper, facade manifest, and caller migrations in parallel.I'll independently verify T5.1 against the six acceptance claims by reading the attachedI'll read render implementationI'll, tests, and imported the listed production files, verify T5.6 docs helpers. tests, and leftover- and T5.7 packagingI'll read the Timport gre against the M1 contractsI'll independently5.4 files and searchps for verify T5.5 by, starting with the listed the repo for leftover T5.2 and T files and gate reading the parity suite cache notes5.3., fixtures, Makefile, and., concrete-renderer imports, CI wiring. and baked remotion/ffmpeg paths.Next I’ll read the M1 docs, packaging config, and smoke/test files for leftover monolith paths.Next I’ll read the five migration testsNext I’ll inspect and grep fixtures, Makefile for leftover renderer targets, and/ skip/fail paths that couldIndependent greps nextrename leftovers violate. the T: production imports, `-m render5.5 gate..run` spawns, and any remotion/ffmpeg hardcoding outside allowlisted paths.I need the imported helpers and the real executor override path — the tests mock `run_executor`, so those are the likely failure points.The old `render.run` path still appears in a few skill docs; I’ll read those sections plus pack/override docs for current M1 contracts.Checking whether the facade `run.py` still imports concrete backends, and whether any production `-m` spawns leak outside manifests.I’ll check remaining semantic fixtures, binary media in git, and how remotion typecheck is treated as blocking.**PASS**

T5.4 is met. The facade manifest is selector-neutral, `resolve_executor_runtime_module` is uncached, and production trees do not import concrete renderers or spawn `render.run` outside the documented allowlist.

**`executor.yaml` is neutral.** Inputs are `engine`, `backend`, `backend_config`, `output_name` (plus timeline/assets/theme/keep). Descriptions are registry/selector language, not a remotion/ffmpeg-only path. Ripgrep of `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/executors/render/executor.yaml` finds no `remotion`/`ffmpeg`. Argv/`runtime_module` point at the facade (`astrid.packs.rendering.executors.render.run`), not a backend.

**`@lru_cache` removed.** `astrid/core/execution/executor/argv.py:10` defines `resolve_executor_runtime_module` with no decorator; docstring at lines 17–19 says it is deliberately uncached. No `lru_cache` import in that file.

**Allowlist test exists and matches the contract.** `tests/core/rendering/test_production_callers.py` greps `astrid/` for backend imports, `legacy_engine` imports, and `astrid.packs.rendering.executors.render.run`, and fails outside backends/, manifests, and `_ALLOWED_FILES` (facade `run.py`/`__init__.py`, compatibility alias, legacy engine, pack launcher).

**Independent repo search (production).**

| Check | Result |
|The uniqueness and fallback---|---|
| `from paths look plausible; next I’ll check whether the/ real `run_executor`import astr rejects `project`id.packs.rendering.exec+`out`utors.render` under together or `astrid/` | ** bypass0** productiones overrides. hits |
| `astrid.packs.rendering.executors.render.run` in `*.{py,yaml,yml,json}` under `astrid/` | **only** `executor.yaml:23` and `:171` |
| `(import\|from) astrid.packs.rendering.backends` | only backends/ + allowlisted `legacy_engine.py`, `audio_reactive_colour.py`, `packs/rendering/run.py` |

Docs (`SKILL.md`/`STAGE.md`) mention `python3 -m …render.run`; those are not production imports or spawns. Facade `run.py` still defaults CLI `engine="remotion"` (`run.py:182`, `:294`) — outside T5.4’s manifest/topology scope.

`tests/core/test_executor_registry_snapshot.py` is a generic registry snapshot; no remotion/ffmpeg bake-in.**ISSUES**

T5.5 is almost complete (populated repo fixtures, real renderer coverage, generated media, blocking CI lanes), but the normal parity suite still self-skips when FFmpeg is missing.

### Fails (blocking)
- **`tests/packs/test_rendererA few contracts_parity.py:89 look sound-99`** — `_require_ffmpeg()` does `pytest.skip("ffmpeg; next I’ll check iteration step-id collisions, leftover binary is unavailable")` and `-m render.run` docs, and the parity suite the session’s skip/fail behavior. `parity_media` fixture calls it. Without FFmpeg, Remotion/FFmpeg/hybrid/raw/audio render tests skip instead of failing. T5.5: *no env self-skip; fail not skip*.

- **`tests/packs/test_renderer_parity.py:644-646`** — `test_remotion_typecheck_is_blocking_when_dependencies_are_installed` `return`s (pass) if `remotion/node_modules` is absent. That is a silent env opt-out, not a blocking typecheck.

- Local typecheck is also soft: **`Makefile:42-48`**, **`scripts/reshape/run_ci_checks.sh:265-272`** and **`:377-382`** print `LANE remotion-typecheck: SKIP` when `node_modules` (or `types.augmentations.d.ts`) is missing. CI is stricter (see below).

### Confirmed OK
1. **Fixtures populated** under `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/fixtures/renderer_parity/`: `media-only`, `effect-clip`, `text-card`, `audio-reactive-colour`, `transition-windows` have tracks/clips; `assets.json` + `theme-overrides.json` are real. Theme visual matches Hype golden (`test_repository_fixtures_are_populated…:271-281` vs `tests/golden/hype/merged_render_props.json`). Audio-reactive reuse: fixture + FFmpeg `audio-reactive-colour/v1` (`:357-359`). Sprint-08 is retired (`tests/fixtures/sprint08/README.md:8-12`).

2. **Empty fixtures fail** — `:271-277` asserts non-empty tracks/clips; missing/empty JSON blows up in `_json` (`:83-86`). Intentional empty timeline is rejected (`:284-301`).

3. **No remotion skip** in the suite. Only the FFmpeg skip above. Remotion Chromium Mach-port denial is accepted (`:234-242`, `:328-330`, `:430-432`) — not an env skip.

4. **Coverage present:** Remotion (`:304-336`), FFmpeg (`:339-359`), remotion→ffmpeg (`:362-378`), all-FFmpeg hybrid (`:381-401`), mixed hybrid (`:404-446`), raw + output names (`:449-469`), audio none/passthrough (`:472-506`), invalid artifact (`:509-535`), failure cleanup (`:284-301`), standalone/attached + names (`:570-641`). Real FFmpeg encode in fixture setup (`:113-150`) and render (`:346-353`).

5. **CI is blocking:** `ci.yml:32-35` installs FFmpeg; `:71-80` `npm ci`; `:87-92` blocking `npm run typecheck` + `pytest -m renderer_parity` (no `continue-on-error`). Mirror: `run_ci_checks.sh:261`, `:366`. `check` depends on both (`Makefile:19`, `:50-51`). `test_ci_json.py:36` timeout `1500`.

6. **No committed MP4s** in `renderer_parity/` (JSON + wrapper only; media generated at `:113-150`).**T5.6 — ISSUES**

Facade, backends, and overrides are current. Attached-child is not.

`docs/contracts/render-backend-v1.md` is an M1 contract (L3–14, L62–86): `python3 -m astrid executors run rendering.render`, facade at `executors/render/run.py`, `RenderService`, no concrete backend imports. Overrides/aliases are specified (L46–47, L501, L263–269 in aliases doc). Creating-packs L284–343 and aliases L226–280 document `extensions.rendering`, qualified ids, and typed renderer/planner/finalizer overrides. Creating-tools L123–130 and the asset-resolution bridge L324–330 tell authors to stay on `rendering.render` / `RenderService`.

**Attached-child is missing everywhere in the T5.6 set.** Production callers use `invoke_attached_render` (`astrid/core/rendering/attached.py:44`, `invocation="attached-child"` at L136). Zero hits for `invoke_attached_render` / `attached-child` in `docs/contracts/render-backend-v1.md`, creating-packs, aliases, creating-tools, render-adapter, the asset-resolution bridge, rendering SKILL/STAGE, or `_core` SKILL. The contract only says embedding “may call `RenderService` directly” (L77–78). Pack authors still have no bound-child recipe.

Leftover `-m …render.run` is labeled debug in the listed files, so it is not monolith-only, but it still teaches the old spawn:

```154:157:astrid/packs/rendering/executors/render/STAGE.md
python3 -m astrid.packs.rendering.executors.render.run \
  --timeline ./out/hype.timeline.json \
  --assets ./out/hype.assets.json \
  --out ./out/hype.mp4
```

Same at `astrid/packs/rendering/skill/SKILL.md:195` and `astrid/packs/_core/skill/SKILL.md:704`. Out of the T5.6 list but stale: `html_canvas_effect/STAGE.md:45` calls that spawn “the normal renderer.”

`tests/verify_docs_commands.sh` only extracts `python3 -m astrid` from README ` ```text ` and `docs/templates/**/STAGE.md`. Those prefixes (`executors|orchestrators|elements` inspect/run/list) look `--help`-valid; the `render.run` blocks are not scanned.

**T5.7 — PASS**

`pyproject.toml:60-65` ships schemas, parity fixtures, and `packs/rendering/**/*.yaml`. `SOURCES.txt` includes all eight v1 schemas, the nine fixture files, and rendering manifests. `scripts/smoke_wheel_install.sh:144-154` and `tests/core/rendering/test_package_data.py:76-83` both `load_default_registries` and require `rendering.remotion` / `ffmpeg` / `legacy_hybrid` / `ffmpeg-finalizer`. Makefile: `check` (L19) includes mypy + remotion-typecheck; `ci` (L54) adds `wheel` → the smoke script. This pass did not re-run `make`; `.oracle/m1-gate.md` records those gates green.**STRICT verdict: PASS**

Both slices use `invoke_attached_render` / `rendering.render`. No leftover `from ..render.run`, `packs.rendering.executors.render`, or `python -m …render.run` in the listed production files.

### T5.2 — iteration / cut
- Iteration writes the pair in-place: `run_builtin_render` calls `invoke_attached_render(..., brief_out / "iteration.mp4", engine=renderer)` (`run.py:167–176`). No rename/`hype.mp4` hop.
- Sidecar is first-class: `OUTPUT_FILES` (`run.py:28–31`), orchestrator outputs (`orchestrator.yaml:44–58`), plan `produces` + `output_name=iteration.mp4` (`plan_template.py:62–68,111–128`).
- Plan uses the facade (`-m astrid executors run rendering.render`), not a concrete module (`plan_template.py:111–128`; `test_iteration_video.py:175–183`).
- Ledger: `_attached_render_binding` either binds parent `project`/`run_root` + `step_id="iteration-render"` or env-only step attach, never a second run (`run.py:179–206`). Test: one project `run.json`, no `out/run.json` / `hype.mp4` (`test_iteration_video.py:80–93`).
- Cut/resume keep deprecated `--renderer` and forward it as `engine` (`cut/run.py:123–129,374–384`; `resume.py:171–176`; `test_cut_render_migration.py:38–50,95–110`). Env attach uses `cut-render` / `cut-resume-render`; unbound omits `step_id`; no extra `run.json` (`test_cut_render_migration.py:51–58,104–115,118–127`).

### T5.3 — hype / human-notes
- Hype still owns `hype.mp4` + sidecar (`steps.py:38–39,192–198,419–424`; `plan_template.py:44–45,287–293`; `_build_render_cmd` → `rendering.render` with default name).
- Runtime goes through `invoke_hype_render` → `invoke_attached_render` (`steps.py:165–198`; `runner.py:249–251`). Theme/overrides land on the call (`test_hype_render_migration.py:64–74,123–133`).
- Single parent ledger: bound hype render writes `hype.mp4` + sidecar and only `hype-parent/run.json` (`test_hype_render_migration.py:77–133`).
- Human-notes `--apply` renders via `invoke_attached_render` to `hype.mp4`; env bind adds `human-notes-render-*` `step_id`, else public/unbound (`human_notes/run.py:256–264`; `test_human_notes_render.py:56–73`).
- Overrides: attached facade + public `RenderService` both pick up executor/planner/renderer/finalizer overrides (`test_caller_overrides.py:26–79,82–127`).
- `tools/render_and_check.py` unchanged: `astrid executors run rendering.render`, expects `hype.mp4` (`tools/render_and_check.py:39–54`).The T5.5 brief allows skipping only when FFmpeg is missing. I'll run the acceptance suites and keep checking cut deprecation, Hype plans, and packaging.A few extra files in the Batch 5 diff look like leftover test artifacts. I'll inspect those and the remaining contract edges.**PASS**

1. **Parent project/run** — `_resolve_parent_binding` requires a paired slug/run (args or env); partial bindings raise (`attached.py:168–185`). `_validate_parent_run` checks slug/run id, loads the ledger, matches identity, requires `RUNNING`, and requires the run dir (`189–212`). Invalid parent does not call `run_executor` or `RenderService` (`test_attached_render.py:278–307`).

2. **Unique step IDs** — Bound calls require a non-empty `step_id`, `validate_run_id` rejects multi-segment/unsafe ids, and a pre-existing `steps/<id>/` raises `already exists` (`attached.py:96–111`; uniqueness test `66–111`).

3. **All three `ASTRID_TASK_*` vars** — `_scoped_task_env` sets `ASTRID_TASK_PROJECT` / `ASTRID_TASK_RUN_ID` / `ASTRID_TASK_STEP_ID` and restores prior set/empty/unset in `finally` (`215–236`). Tests cover success and child-raise (`114–185`).

4. **Caller output** — Bound path forwards `out=output.parent` and `inputs["output_name"]=output.name`, returns that video, and `link_into_produces` only symlinks into `produces` (`113–159`, `250–257`; `188–211`).

5. **Facade overrides** — Bound path is `ExecutorRunRequest(executor_id="rendering.render")` plus `run_executor` / `registry.get`, which applies `OverrideStore` (`130–144`; `registry.py:120–132`; `capability_runner.py:107–109`; override tests in `test_attached_render.py:214–250` and `test_caller_overrides.py:27–79`).

6. **Public fallback only when unbound** — `RenderService.render` runs only when binding resolves to `(None, None)` (`86–94`, `182–186`). Unbound writes no `run.json` (`253–275`); invalid parent does not fall back (`278–307`).The T5.5/T5.6 “issues” don’t match the frozen briefs. I’ll run the fast acceptance suites so a PASS is based on independent evidence.Those 7 failures look like a missing local schema package, not Batch 5 regressions. I’ll confirm against the project environment.**PASS**

Batch 5 meets the frozen M1-freeze acceptance criteria. Batch 6 can start.

Independent review of `C5-batch4-done..HEAD` (`2d741daf`, `47e6541a`, `b22fc075`, plus the two follow-up gate commits) confirms each T5 item:

| Task | Verdict |
|---|---|
| T5.1 attached-child helper | Bound calls validate parent/run, reject reuse of the same step id, scope and restore all three `ASTRID_TASK_*` vars, keep the caller output name, pass `rendering.render` through `run_executor` (overrides apply), and use public `RenderService` only when unbound. |
| T5.2 iteration/cut | Iteration writes `iteration.mp4` + sidecar in place (no `hype.mp4` rename). Cut/resume keep deprecated `--renderer` and forward it as `engine`. |
| T5.3 hype/human-notes | Hype still produces `hype.mp4` via `invoke_hype_render`. Human-notes goes through the attached helper. `tools/render_and_check.py` stays on the facade CLI. |
| T5.4 facade + topology | `executor.yaml` is selector-neutral. `resolve_executor_runtime_module` is uncached. No production concrete-renderer import or `-m …render.run` spawn outside manifests/backends/allowlist. |
| T5.5 parity | Repo-owned fixtures, generated media, real Remotion/FFmpeg/hybrid/raw coverage, empty fixtures fail, no `ASTRID_RENDERER_PARITY` self-skip. FFmpeg-absent skip is allowed by the T5.5 brief. Typecheck is blocking in CI. |
| T5.6 docs | Facade + `RenderService` are the documented path; leftover `-m …render.run` is labeled debug-only. No removed monolith internals. |
| T5.7 packaging | Schemas, parity fixtures, and rendering manifests are package data; wheel smoke asserts they are discoverable. |

Re-ran the targeted acceptance suites with the project Python (`3.11.11`): **55 passed**.

Recorded M1 matrix in `.oracle/m1-gate.md` matches the remaining gates (`make check`, wheel smoke, Remotion typecheck, parity 18/18). Full-suite failures are the same pre-existing unrelated set already present at `C5-batch4-done`.

Nits only (not blocking): leftover `pipeline-tests-*/plan.json` and `.oracle/ws-keep*` workspaces were committed with the batch. Worth deleting before merge; they do not affect the M1 contract.
