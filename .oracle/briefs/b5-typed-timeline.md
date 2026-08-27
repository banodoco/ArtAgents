# BATCH 5 — typed_timeline pack: generic rows→timeline mapper + Runaway colour render

You are openrouter/meta/muse-spark-1.2-contributor in worktree /Users/peteromalley/Documents/reigh-workspace/Astrid-unified-oracle (branch oracle-unified-execution). NO git commands. NO formatters.

## Tasks (Grok strategy, KISS)

### 5.1 Pack skeleton + generic mapper
Create `astrid/packs/typed_timeline/`:
- `pack.yaml` (id typed_timeline, version 1, depends core>=1)
- `mapper.py` — generic TypedDataTimelineMapper(rows, mapping.yaml) → timeline JSON (tracks/clips/params). Support scopes: aggregated (one clip with events[] from rows) and per-row (one clip/row with at/paramMapper). Frames: prefer metadata.frame else ms_to_frame. Handle fps, total_duration, stitch ordinal. Dotted paths + 4 builtins (const, first, ms_to_frame, $total_duration_sec). Reuse existing effects as sinks (no new effect).
- `sources.py` — per-table loaders: runaway_transitions -> RunawayRepository.list (stitch shards by ordinal, optional run_id filter) + json file source for tests.
- `frames.py` — ms↔frame, total_frames.
- `mappings/runaway_colour.yaml` — aggregated audio-reactive-colour (initialColor #16B09B, events from metadata.colour_hex/frame, fps 48, total 8085, hard_cut). `mappings/runaway_text.yaml` — per-row text-card (content: prompt, overlay track first).
- Tests: 3-row aggregated + per-row unit, frame prefer-metadata vs ms, shard stitch, 566 golden vs audio-reactive-v1.json.

### 5.2 Executors
- `executors/map/{executor.yaml,run.py,STAGE.md}` — admits kernel run+child task, calls mapper, writes timeline.json (+ assets.json) into that run, no second ledger.
- `orchestrators/render/{orchestrator.yaml,run.py,STAGE.md}` — children: typed_timeline.map then rendering.render (ffmpeg fast-path). Invoke via sdk.invoke.

### 5.3 Wiring + verification
- `sdk.invoke("typed_timeline.render", inputs={source: runaway, run_id, mapping: runaway_colour}, project="runaway-piano-colour-demo")` → kernel run+task with events/receipts, timeline valid via match_and_validate, 10-row ffmpeg smoke, same rows+YAML → same JSON hash, old files untouched.

Verify: 3-row unit, 566 golden, match_and_validate, ffmpeg smoke, idempotency, same-hash.

North Star: ONE store, ONE path, every run observable, honest docs.
