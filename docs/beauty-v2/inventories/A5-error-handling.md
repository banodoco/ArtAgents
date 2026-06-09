# Inventory appendix — A5-error-handling

_Read-only DeepSeek V4 Pro research against base `2edd0ce`. Verify any functional claim with ast.parse/grep before acting — one claim per audit class has historically been a truncated-read false positive._


### Theme: Error-handling inconsistency vs the AstridError envelope

**Scope of the problem:** Across the ~118k LOC Astrid codebase, **125 `raise SystemExit`** instances bypass the `AstridError` envelope from non-`__main__` code paths, including **15 in core/** (http.py, secrets.py, llm_clients.py, install_trust.py, audit/cli.py, threads/cli.py, executor/folder.py, orchestrator/folder.py). An additional **9 `FileNotFoundError`** + **3 `FileExistsError`** + **3 `OSError`** + **56 `RuntimeError`** occur in core library paths with no envelope wrapping. **One `_die()`** helper (boundary_candidates/run.py) raises `SystemExit` where 4 sibling packs raise `AstridError`. **`ProjectError`** (project.py:53) extends `AstridError` but discards `valid_options`/`recovery_command`/`state_snapshot` — a degraded envelope. Approximately **30 pack run.py files** use bare `main()` with no `run_pack_main` wrapping, meaning `ValueError`/`RuntimeError`/generic `Exception` in those packs escape without any envelope coercions. The two pack-executor regimes (`run_pack_main`-wrapped vs bare) create a split where half the tree gets degraded-fallback and half doesn't.

**Complete instance inventory:**

| # | file:line | what | severity |
|---|-----------|------|----------|
| 1 | core/util/http.py:131 | `raise SystemExit` on HTTPError in `get_bytes` | BLOCKER |
| 2 | core/util/http.py:135 | `raise SystemExit` on URLError in `get_bytes` | BLOCKER |
| 3 | core/util/http.py:165 | `raise SystemExit` on FAILED/ERROR/CANCELLED in `poll_until` | BLOCKER |
| 4 | core/util/http.py:170 | `raise SystemExit` on timeout in `poll_until` | BLOCKER |
| 5 | core/util/http.py:195 | `raise SystemExit` on HTTPError in `_send` | BLOCKER |
| 6 | core/util/http.py:201 | `raise SystemExit` on URLError in `_send` | BLOCKER |
| 7 | core/util/http.py:271 | `raise SystemExit` on missing status_url in `fal_submit_poll` | BLOCKER |
| 8 | core/util/secrets.py:114 | `raise SystemExit` in `require_secret` (secret not found) | BLOCKER |
| 9 | core/util/llm_clients.py:215 | `raise SystemExit` in secret resolution | BLOCKER |
| 10 | core/pack/install_trust.py:196 | `raise SystemExit(1)` in trust verification | UGLY |
| 11 | core/pack/install_trust.py:213 | `raise SystemExit(1)` in trust verification | UGLY |
| 12 | core/audit/cli.py:42 | `raise SystemExit(str(exc))` in audit CLI | UGLY |
| 13 | core/threads/cli.py:119 | `raise SystemExit(str(exc))` in threads CLI | UGLY |
| 14 | core/executor/folder.py:263 | `raise SystemExit(1)` in executor discovery | UGLY |
| 15 | core/orchestrator/folder.py:241 | `raise SystemExit(1)` in orchestrator discovery | UGLY |
| 16 | core/project/source.py:27 | `raise FileExistsError` in `add_source` | UGLY |
| 17 | core/project/source.py:41 | `raise FileNotFoundError` in `require_source` | BLOCKER |
| 18 | core/project/project.py:108 | `ProjectError` discards envelope fields | BLOCKER |
| 19 | core/project/project.py:209 | `raise FileNotFoundError` bare source not found | UGLY |
| 20 | core/project/run.py:497 | `raise FileNotFoundError` run not found | UGLY |
| 21 | core/contracts/result_manifest.py:94 | `raise FileNotFoundError` required output missing | UGLY |
| 22 | core/model_catalog/registry.py:119 | `raise FileNotFoundError` model registry not found | UGLY |
| 23 | core/model_catalog/registry.py:216 | `raise FileNotFoundError` lora registry not found | UGLY |
| 24 | core/audit/graph.py:12 | `raise FileNotFoundError` audit ledger not found | UGLY |
| 25 | core/timeline/banodoco_composer.py:309 | `raise FileNotFoundError` theme not found | UGLY |
| 26 | core/pack/store.py:384 | `raise FileNotFoundError` pack store | UGLY |
| 27 | core/util/atomic_io.py:145 | `raise OSError` failed to read JSON | NIT |
| 28 | core/timeline/repair.py:159,196 | `raise OSError` (2×) failed timeline repair | NIT |
| 29 | core/pack/entrypoint.py:56 | `sys.exit(2)` in `guard_canonical_entrypoint` | UGLY |
| 30 | skills/harnesses/base.py:152 | `raise FileExistsError` symlink conflict | NIT |
| 31 | sdk/events.py:40,43 | `raise FileNotFoundError` (2×) run not found, events missing | UGLY |
| 32–39 | packs/video_editing/executors/cut/probe.py:20,26,50,54,61,64,71,75 | `raise SystemExit` (8×) in library probe functions | BLOCKER |
| 40–44 | packs/video_editing/executors/cut/registry.py:47,50,52,61,69 | `raise SystemExit` (5×) in registry functions | BLOCKER |
| 45–48 | packs/video_editing/executors/cut/resume.py:46,88,92,122 | `raise SystemExit` (4×) in resume functions | BLOCKER |
| 49–50 | packs/video_editing/executors/cut/run.py:186,196 | `raise SystemExit` in `load_scenes`/`load_transcript_segments` | BLOCKER |
| 51 | packs/video_editing/executors/cut/timeline_build.py:280 | `raise SystemExit` in timeline builder | UGLY |
| 52 | packs/foley/orchestrators/foley_map/run.py:85 | `raise SystemExit` VLM call failed | UGLY |
| 53 | packs/editorial/executors/boundary_candidates/run.py:22–23 | `_die()` raises `SystemExit` instead of `AstridError` | BLOCKER |
| 54–58 | packs/training/executors/asset_cache/run.py:349,355,381,384,388,394,397 | `raise SystemExit` (7×) ffprobe clone of probe.py bugs | UGLY |
| 59–63 | packs/editorial/executors/validate/run.py:77,79,96,103,163 | `raise SystemExit` (5×) in validation | UGLY |
| 64–65 | packs/editorial/executors/scenes/run.py:72,137 | `raise SystemExit` (2×) | UGLY |
| 66–69 | packs/editorial/executors/quality_zones/run.py:117,119,181,183 | `raise SystemExit` (4×) | UGLY |
| 70–75 | packs/generation/executors/generate_image/run.py:79,88,103,114,120,191 | `raise SystemExit` (6×) | UGLY |
| 76–84 | packs/generation/executors/generate_video/run.py:92,147,156,171,182,188,264,440,444 | `raise SystemExit` (9×) | UGLY |
| 85–91 | packs/video_editing/orchestrators/vary_grid/run.py:194,196,307,309,315,319 | `raise SystemExit` (6×) | UGLY |
| 92–98 | packs/video_editing/orchestrators/logo_ideas/run.py:168,176,180,198,232,242,246 | `raise SystemExit` (7×) | UGLY |
| 99–100 | packs/editorial/executors/transcribe/run.py:51,181,290 | `raise SystemExit` (3×) | UGLY |
| 101–104 | packs/editorial/executors/script_pipeline/run.py:509,511,513,619 | `raise SystemExit` (4×) | UGLY |
| 105–108 | packs/editorial/executors/shots/run.py:45,51,109,111 | `raise SystemExit` (4×) | UGLY |
| 109 | packs/fal/executors/fal_foley/run.py:56 | `raise SystemExit` fal result missing audio | UGLY |
| 110 | packs/rendering/executors/sprite_sheet/upscale.py:80 | `raise SystemExit` FAL_KEY not found | UGLY |
| 111 | packs/video_editing/orchestrators/hype/runner.py:511 | `raise SystemExit` URL expired | UGLY |
| 112 | ~30 packs | `main()` not wrapped by `run_pack_main` → no envelope fallback | BLOCKER |
| 113 | core/pack/entrypoint.py:77–104 | `run_pack_main` exists but only ~21/50 packs use it | BLOCKER |

**Root cause:** The codebase has no enforced rule for how library code communicates failures. `HttpClient`, `require_secret`, ffprobe helpers, and asset resolution were written as "script-first" code where `raise SystemExit` felt natural — they assumed a CLI caller that would catch the exit. But these modules are imported across the tree (e.g., `probe.py` is re-exported from `cut/run.py` for use by other modules), so their `SystemExit` kills any caller process. The canonical `AstridError` envelope and `run_pack_main` wrapper were added later as a remediation layer, but adoption was voluntary per-pack rather than enforced by a shared base class or lint rule. The `_die()` helper pattern proliferated independently in 7 files with no shared definition, leading to the boundary_candidates outlier.

**Cross-impact:** Fixing `HttpClient` (theme here) collides with the **secret-scrubbing seam** — `register_secret`/`scrub_secret` are tested via monkeypatch; changing exception types in `_send`/`get_bytes`/`poll_until` will break those tests. The ffprobe `SystemExit` clones in `asset_cache/run.py` are a direct copy-paste of `cut/probe.py` — fixing one requires fixing both (theme-3: duplicated code). `ProjectError`'s degraded envelope touches every caller of `require_project` (project creation CLI, SDK, managed binding seam). The `run_pack_main` gap in ~30 packs overlaps with the **executor/orchestrator twin** problem (theme-2 of the audit) — both involve the same `entrypoint.py` module and the same `guard_canonical_entrypoint` guard. Changing `_die()` in `boundary_candidates` requires coordinating with the `sprite_sheet` pack which imports `_die` cross-pack from `generate_image_openai.run` (line 464).

**Proposed fix approach:** (1) Add `wrap_degraded_error`-style coercions to the 15 core `SystemExit`/`FileNotFoundError`/`FileExistsError`/`OSError` sites, converting them to `AstridError(degraded=True)` with recovery hints. (2) Create `astrid/core/contracts/die.py` with a single `_die()` that raises `AstridError`, and migrate all 7 local definitions to import it. (3) Fix `ProjectError.__init__` to accept and forward `valid_options`/`recovery_command`/`state_snapshot`. (4) Add a `run_pack_main`-equivalent wrap in `guard_canonical_entrypoint` so every pack gets envelope protection regardless of whether it opts in. (5) Table-driven classification for the remaining ~110 pack-level `SystemExit` instances: those inside `main()` stay as CLI exits (legitimate), those in imported library functions convert to `AstridError`.

**Sequencing & risk:** **Contract-locked** (changing exception type breaks callers/tests): `HttpClient._send`/`get_bytes` (tested via monkeypatch on `_transport`), `require_secret` (called from dozens of packs that catch `SystemExit`), `probe_asset`/`parse_ffprobe_fps` (re-exported from `cut/run.py`), `require_source`/`require_project` (used by SDK + CLI). These must change exception type carefully — add the new `AstridError` raise AND keep a compatibility shim that preserves the old behavior under a deprecation flag for one release cycle. **Safe to change immediately:** `_die()` consolidation (new shared module, no existing importers depend on the exception type), `ProjectError` envelope fix (additive — just forwards more kwargs), `run_pack_main` universal adoption (additive — wraps bare mains). **Must happen first:** the shared `_die()` module, then `ProjectError` fix, then core library site conversions, then pack-by-pack migration.

**Suggested tickets (one-agent-each, sequential):**

- **T1:** Create `astrid/core/contracts/die.py` with canonical `_die(message, *, recovery_command, valid_options) -> NoReturn` raising `AstridError`. Migrate the 4 `AstridError`-raising `_die` definitions (tile_video, generate_image_openai, video_understand, audio_understand, visual_understand, youtube_audio) and the 1 `SystemExit` outlier (boundary_candidates) to import it. Update sprite_sheet's cross-pack import. *(6 files, ~30 LOC changed, zero risk.)*

- **T2:** Fix `ProjectError.__init__` to accept and forward `valid_options`, `recovery_command`, `state_snapshot`. Update the 1 call site (`require_project` at project.py:108) to pass recovery_command. *(1 class + 1 call site, additive, zero risk.)*

- **T3:** Convert the 15 core `SystemExit` sites (http.py ×7, secrets.py ×1, llm_clients.py ×1, install_trust.py ×2, audit/cli.py ×1, threads/cli.py ×1, executor/folder.py ×1, orchestrator/folder.py ×1) to `raise AstridError(...)`. Add `wrap_degraded_error` catch in `run_pack_main` to also trap `SystemExit` during a deprecation window. *(~15 sites, moderate risk — test-coupled.)*

- **T4:** Convert the 9 core `FileNotFoundError` + 3 `FileExistsError` + 3 `OSError` sites to `AstridError` with recovery hints. *(~15 sites, moderate risk.)*

- **T5:** Universal `run_pack_main` adoption: add a `warn_if_bare_main()` lint helper to `guard_canonical_entrypoint`, then convert the ~30 bare-main packs to use `run_pack_main`. *(~30 files, mechanical, low risk per file.)*

- **T6:** Convert pack-level library-function `SystemExit` instances (probe.py ×8, registry.py ×5, resume.py ×4, asset_cache clone ×7, timeline_build ×1, foley_map ×1, etc.) to `AstridError`. Leave `main()`-body `SystemExit` as CLI-valid exits. *(~40 sites across ~12 files, moderate risk.)*