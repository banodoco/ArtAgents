# Inventory appendix — A1-pack-copypaste

_Read-only DeepSeek V4 Pro research against base `2edd0ce`. Verify any functional claim with ast.parse/grep before acting — one claim per audit class has historically been a truncated-read false positive._


### Theme: Pack-executor copy-paste epidemic

**Scope of the problem:** Across 68 pack executor/orchestrator `run.py` files (~24,900 LOC total), six copy-paste patterns account for an estimated 900–1,200 duplicated LOC. The most egregious is the universal result-manifest dict block — ~35 executors build a 10–14 line `{"schema_version": 1, "kind": ..., "inputs": {...}, ...}` dict literal by hand when `build_manifest()` from `astrid/core/contracts/result_manifest.py` already exists. Only **2** files use it. The `_die()` helper is copy-pasted 7 times with **2 incompatible error types** (`SystemExit` vs `AstridError`) and 5 different signatures. The `guard_canonical_entrypoint` call is duplicated 63 times (correct but boilerplate). Two competing executor architectures coexist (21 closure-style `run_pack_main` vs 42 bare `def main`). The runpod pack (`_common.py` 985L + 5×18L thin wrappers) is the sole exemplar of the right design — no other pack has a shared `_common.py`.

**Complete instance inventory:**

| # | file:line | what | severity |
|---|-----------|------|----------|
| **Pattern (a): Raw result-manifest dict literals (35 instances)** | | | |
| 1 | editorial/executors/arrange/run.py:859 | Raw `{"schema_version": 1, ...}` dict | UGLY |
| 2 | editorial/executors/boundary_candidates/run.py:293 | Raw dict | UGLY |
| 3 | editorial/executors/editor_review/run.py:829 | Raw dict | UGLY |
| 4 | editorial/executors/human_notes/run.py:305 | Raw dict | UGLY |
| 5 | editorial/executors/quality_zones/run.py:143 | Raw dict | UGLY |
| 6 | editorial/executors/quote_scout/run.py:154 | Raw dict | UGLY |
| 7 | editorial/executors/refine/run.py:683 | Raw dict | UGLY |
| 8 | editorial/executors/scenes/run.py:151 | Raw dict | UGLY |
| 9 | editorial/executors/script_pipeline/run.py:431 | Raw dict + shadow `write_manifest()` at L419 | BLOCKER |
| 10 | editorial/executors/script_pipeline/run.py:539 | Second raw dict in same file | UGLY |
| 11 | editorial/executors/shots/run.py:130 | Raw dict | UGLY |
| 12 | editorial/executors/transcribe/run.py:307 | Raw dict | UGLY |
| 13 | editorial/executors/triage/run.py:312 | Raw dict | UGLY |
| 14 | editorial/executors/validate/run.py:136 | Raw dict (first of two) | UGLY |
| 15 | editorial/executors/validate/run.py:271 | Raw dict (second) | UGLY |
| 16 | foley/executors/foley_review/run.py:179 | Raw dict | UGLY |
| 17 | foley/executors/tile_video/run.py:241 | Raw dict | UGLY |
| 18 | iteration/executors/assemble/run.py:225 | Raw dict | UGLY |
| 19 | iteration/executors/prepare/run.py:89 | Raw dict; also has local `build_manifest()` at L338 shadowing core | BLOCKER |
| 20 | media/executors/speech_repair_lavasr/run.py:302 | Raw dict | UGLY |
| 21 | reigh/executors/open_in_reigh/run.py:201 | Raw dict | UGLY |
| 22 | reigh/executors/spatial_audio_page/run.py:260 | Raw dict | UGLY |
| 23 | rendering/executors/html_canvas_effect/run.py:219 | Raw dict | UGLY |
| 24 | rendering/executors/sprite_sheet/run.py:378 | Raw dict | UGLY |
| 25 | training/executors/pool_build/run.py:232 | Raw dict | UGLY |
| 26 | training/executors/pool_merge/run.py:116 | Raw dict | UGLY |
| 27 | understanding/executors/audio_understand/run.py:517 | Raw dict | UGLY |
| 28 | understanding/executors/scene_describe/run.py:293 | Raw dict | UGLY |
| 29 | understanding/executors/video_understand/run.py:321 | Raw dict | UGLY |
| 30 | understanding/executors/visual_understand/run.py:479 | Raw dict | UGLY |
| 31 | video_editing/executors/cut/run.py:413 | Raw dict | UGLY |
| 32 | youtube/executors/youtube_audio/run.py:123 | Raw dict | UGLY |
| 33 | training/orchestrators/training_run/run.py:193 | Raw dict (first of 3) | UGLY |
| 34 | training/orchestrators/training_run/run.py:704 | Raw dict (second) | UGLY |
| 35 | training/orchestrators/training_run/run.py:750 | Raw dict (third) | UGLY |
| **Correct `build_manifest` usage (only 2 files)** | | | |
| C1 | media/executors/clip_extract/run.py:107 | Uses core `build_manifest()` + `write_manifest()` | — |
| C2 | iteration/executors/prepare/run.py:142 | Uses core `build_manifest()` (but also has local shadow at L338) | — |
| **Also: local manifest builders NOT using core** | | | |
| L1 | generation/executors/generate_image/run.py:248 | Local `_build_manifest()` — 70+ lines, uses `schema_version: 2` | BLOCKER |
| L2 | generation/executors/generate_video/run.py:321 | Local `_build_manifest()` — 70+ lines, same pattern | BLOCKER |
| **Pattern (b): _die() helper — 7 instances, 2 error types** | | | |
| 1 | editorial/executors/boundary_candidates/run.py:22 | `raise SystemExit(f"Error: {message}")` | BLOCKER |
| 2 | foley/executors/tile_video/run.py:23 | `raise AstridError(message, recovery_command=...)` | UGLY |
| 3 | understanding/executors/audio_understand/run.py:65 | `raise AstridError(message, recovery_command=...)` | UGLY |
| 4 | understanding/executors/video_understand/run.py:74 | `raise AstridError(message, recovery_command=...)` | UGLY |
| 5 | understanding/executors/visual_understand/run.py:47 | `raise AstridError(message, recovery_command=...)` | UGLY |
| 6 | youtube/executors/youtube_audio/run.py:23 | `raise AstridError(msg, recovery_command=..., state_snapshot={"exit_code": code})` — unique signature with `code: int = 2` | UGLY |
| 7 | generation/executors/generate_image_openai/run.py:63 | `raise AstridError(message, recovery_command=..., valid_options=...)` — unique signature with `valid_options` kwarg | UGLY |
| **Pattern (c): 4-line dry-run scaffold (3 near-identical copies)** | | | |
| 1 | understanding/executors/video_understand/run.py:234–238 | `if args.dry_run: preview["schema_version"]=1; preview["kind"]=...; print(json.dumps(...)); return 0` | NIT |
| 2 | understanding/executors/visual_understand/run.py:414–418 | Same pattern, var name `payload_preview` | NIT |
| 3 | understanding/executors/audio_understand/run.py:455–459 | Same pattern, var name `preview` | NIT |
| **Similar but distinct dry-run patterns** | | | |
| 4 | rendering/executors/sprite_sheet/run.py:187–202 | Multi-line `print(json.dumps({...}))` dry-run; no schema_version/kind injection | NIT |
| 5 | fal/executors/fal_foley/run.py:105–107 | 3-line `print(json.dumps(...)); return 0` dry-run | NIT |
| **Pattern (d): Two competing executor architectures** | | | |
| | **Closure-style: `def main() -> int: def _run() -> int: ...; return run_pack_main('pack.name', _run, argv=...)` — 21 files** | | |
| 1 | comfy_wrap/executors/run/run.py:166,207 | `run_pack_main("comfy_wrap.run", ...)` | NIT |
| 2 | editorial/executors/quote_scout/run.py:131,169 | `run_pack_main("editorial.quote_scout", ...)` | NIT |
| 3 | foley/executors/tile_video/run.py:180,262 | `run_pack_main("foley.tile_video", ...)` | NIT |
| 4 | generation/executors/generate_image_openai/run.py:494,501 | `run_pack_main("generation.generate_image_openai", ...)` | NIT |
| 5 | iteration/executors/assemble/run.py:122,160 | `run_pack_main("iteration.assemble", ...)` | NIT |
| 6 | iteration/executors/prepare/run.py:65,106 | `run_pack_main("iteration.prepare", ...)` | NIT |
| 7 | media/executors/clip_extract/run.py:73,122 | `run_pack_main("media.clip_extract", ...)` | NIT |
| 8 | media/executors/speech_repair_lavasr/run.py:257,344 | `run_pack_main("media.speech_repair_lavasr", ...)` | NIT |
| 9 | reigh/executors/open_in_reigh/run.py:216,245 | `run_pack_main("reigh.open_in_reigh", ...)` | NIT |
| 10 | reigh/executors/reigh_data/run.py:89,124 | `run_pack_main("reigh.reigh_data", ...)` | NIT |
| 11 | stream_content/executors/clip_candidates/run.py:30,48 | `run_pack_main("stream_content.clip_candidates", ...)` | NIT |
| 12 | stream_content/executors/segment_map/run.py:28,51 | `run_pack_main("stream_content.segment_map", ...)` | NIT |
| 13 | stream_content/orchestrators/distill/run.py:—,436 | `run_pack_main("stream_content.distill", ...)` | NIT |
| 14 | text_analysis/orchestrators/summarize/run.py:—,120 | `run_pack_main("text_analysis.summarize", ...)` | NIT |
| 15 | training/executors/pool_build/run.py:198,251 | `run_pack_main("training.pool_build", ...)` | NIT |
| 16 | understanding/executors/audio_understand/run.py:581,585 | `run_pack_main("understanding.audio_understand", ...)` | NIT |
| 17 | understanding/executors/scene_describe/run.py:258,311 | `run_pack_main("understanding.scene_describe", ...)` | NIT |
| 18 | understanding/executors/visual_understand/run.py:538,542 | `run_pack_main("understanding.visual_understand", ...)` | NIT |
| 19 | youtube/executors/upload/run.py:—,91 | `run_pack_main("youtube.upload", ...)` | NIT |
| 20 | youtube/executors/youtube_audio/run.py:—,140 | `run_pack_main("youtube.youtube_audio", ...)` | NIT |
| 21 | video_editing/orchestrators/animate_image/run.py:—,603 | `run_pack_main(...)` | NIT |
| | **Bare `def main(argv) -> int` + `raise SystemExit(main())` — 42 files** (all remaining non-runpod executors) | | NIT |
| | **Exemplar thin-wrapper (runpod) — 5 files × 18L = 90 LOC** | | |
| E1–E5 | runpod/executors/{provision,session,exec,teardown,pull}/run.py | 18-line wrapper: `guard_canonical_entrypoint(...)` + `from ._common import *` + `raise SystemExit(main())` | — |
| **Pattern (e): guard_canonical_entrypoint — 63 call-sites** | | | |
| | 63 unique `run.py` files (all but script_pipeline, dataset_build, training_run) | `guard_canonical_entrypoint('pack.action')` at top level | NIT |
| | 3 files MISSING it: editorial/executors/script_pipeline/run.py, training/orchestrators/dataset_build/run.py, training/orchestrators/training_run/run.py | No guard call | BLOCKER |
| **Pattern (f): load_api_key — 1 local copy, 8 core users** | | | |
| 1 | editorial/executors/transcribe/run.py:42 | Local 10-line `load_api_key(env_file)` — hardcodes `OPENAI_API_KEY`, reimplements `_candidate_env_files` + `read_env_value` | UGLY |
| 2 | editorial/executors/editor_review/run.py:28 | Imports from `..transcribe.run` (cross-executor sibling import) | UGLY |
| 3 | editorial/executors/refine/run.py:54 | Imports from `..transcribe.run` (cross-executor sibling import) | UGLY |
| C1–C8 | 8 files use `from astrid.core.util.secrets import load_api_key` correctly | fal_foley, visual_understand, audio_understand, sprite_sheet, vary_grid, logo_ideas, generate_image_openai, speech_repair_lavasr | — |

**Root cause:** The pack-executor scaffolding was never designed — it accreted organically. Each new executor was created by copying the nearest sibling and tweaking the pack name string. The `runpod` pack got the shared-`_common.py` treatment because its 5 subcommands are tightly coupled (provision→session→exec→teardown→pull lifecycle). All other packs lack even a pack-level `_common.py`, let alone a core-level `ExecutorScaffold` abstraction. The `build_manifest`/`write_manifest` helpers exist in core but were added after most executors already had hand-rolled dicts; nobody retrofitted them. The `_die()` helper emerged independently in each pack that needed early-exit diagnostics, with each author picking their own error type and signature.

**Cross-impact (READ CAREFULLY):**
- **Theme: test-monkeypatch seams.** The closure-style `run_pack_main('name', _run, argv)` pattern exposes `_run` for test injection (e.g., `clip_extract` tests inject `runner=...`). Bare `def main(argv)->int` files lack this seam. Any consolidation that removes `run_pack_main` or changes the calling convention will break tests that monkeypatch `_run` internals. The `subprocess` module is also exposed through `_common.py`'s `__all__` for this reason.
- **Theme: error-contract reconciliation.** The `_die()` split between `SystemExit` and `AstridError` collides with the error-classification theme. `SystemExit` bypasses structured error reporting; `AstridError` carries `recovery_command`/`state_snapshot`/`valid_options`. Fixing this must align with the error taxonomy audit.
- **Theme: import contract (cross-executor sibling imports).** `editor_review` and `refine` import `load_api_key` from `..transcribe.run` — a sibling executor. This creates a hidden dependency cycle risk. Consolidating `load_api_key` into a pack `_common.py` or core would break these imports and require updating all callers simultaneously.
- **Theme: manifest schema divergence.** `generate_image` and `generate_video` use `schema_version: 2` while core `build_manifest` defaults to `schema_version: 1`. Any migration to core `build_manifest` must handle this version gap or extend the core helper to accept a custom schema version.
- **File naming collisions:** `iteration/executors/prepare/run.py` defines a local `build_manifest()` at L338 that shadows the core import at L24 — any refactor must rename the local or reconcile signatures.

**Proposed fix approach:**
1. **Pack-level `_common.py`** (modeled on `runpod/executors/_common.py`): Create one shared module per pack (editorial, understanding, generation, foley, media, etc.) that re-exports `guard_canonical_entrypoint`, provides a pack-specific `run(argv)` implementing `main`, and houses shared helpers (`_die`, `build_manifest` wrapper, `load_api_key`). Each executor `run.py` becomes a 15–20 line thin wrapper.
2. **Core-level `ExecutorScaffold`**: Abstract the `guard_canonical_entrypoint` + `if __name__ == '__main__': raise SystemExit(main())` + `run_pack_main` dance into a single `@pack_entrypoint('pack.action')` decorator or `define_pack_entrypoint()` function, reducing each `run.py` to ~5 lines.
3. **Manifest retrofit**: Migrate all 35 raw dicts to `build_manifest()` and `write_manifest()`. Extend `build_manifest` to accept `schema_version=2` for generation pack compatibility.
4. **`_die` consolidation**: Move to `astrid.core.pack.errors` as `pack_die(message, *, recovery_command=None, ...)` with `AstridError` as the single raise type.

**Sequencing & risk:**
- **First (safe, independent):** Add `schema_version` parameter to core `build_manifest()` — no callers break, pure extension.
- **Second (safe, independent):** Create core `pack_die()` in `astrid.core.pack.errors` — no existing callers break, pure addition.
- **Third (risky — contract-locked):** Retrofit manifest dicts to `build_manifest()` one pack at a time. The generation pack is highest risk (schema v2, custom fields). Editorial pack has 14 files and is the most copy-paste dense. Start with understanding pack (4 executors, all use same dry-run scaffold + same `_die` + same manifest pattern — highest ROI).
- **Fourth (risky — widely imported, test-coupled):** Create pack-level `_common.py` files. The editorial transcribe `load_api_key` is imported by sibling executors with `from ..transcribe.run import load_api_key` — those imports must be updated atomically. The `subprocess` monkeypatch seam in tests must be preserved.
- **Fifth (risky — changes every run.py):** Introduce core `ExecutorScaffold` / `@pack_entrypoint` — touches all 63 `guard_canonical_entrypoint` call-sites and both architecture styles.

**Suggested tickets (one-agent-each, sequential):**

- **T1:** Add `schema_version` kwarg to core `build_manifest()` (default=1). Add `pack_die()` to `astrid.core.pack.errors`. Both additive, zero risk. Verify: existing tests pass.
- **T2:** Retrofit understanding pack (4 executors): replace raw manifest dicts with `build_manifest()`, replace 3×4-line dry-run scaffold with shared helper, consolidate 3 `_die()` copies into core `pack_die()`. Verify: all understanding tests pass.
- **T3:** Create `editorial/executors/_common.py`: hoist `load_api_key` from `transcribe/run.py`, add `build_editorial_manifest()` wrapper. Retrofit transcribe as first consumer. Update `editor_review` and `refine` imports from `..transcribe.run` to `.._common`. Verify: transcribe, editor_review, refine tests pass.
- **T4:** Retrofit remaining editorial executors (arrange, boundary_candidates, human_notes, human_review, inspect_cut, quality_zones, quote_scout, scenes, shots, triage, validate) to use `_common.py` + `build_manifest`. Fix `script_pipeline`'s shadow `write_manifest`. Verify: full editorial test suite.
- **T5:** Create `generation/executors/_common.py`: unify `generate_image` and `generate_video` local `_build_manifest()` into one shared helper using core `build_manifest(schema_version=2)`. Verify: generation tests.
- **T6:** Create `media/executors/_common.py` (clip_extract already uses `build_manifest` — migrate speech_repair_lavasr). Create `foley/executors/_common.py`, `rendering/executors/_common.py`, `training/executors/_common.py`. One ticket per pack; each is independent.
- **T7:** Create core `@pack_entrypoint('pack.action')` decorator. Migrate all 63 `guard_canonical_entrypoint` + `if __name__` blocks. Unify the two architecture styles. This is the biggest win (eliminates ~300 LOC of boilerplate) but highest risk — do last, after all pack `_common.py` files are stable.

**Estimated LOC win:** ~900–1,200 duplicated lines eliminated across 68 files (roughly 35% of total executor/orchestrator run.py LOC). The runpod model proves the concept: 985L shared + 5×18L wrappers = 1,075L vs. ~5,000L if each had been a standalone copy.