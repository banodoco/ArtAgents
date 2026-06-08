# Milestone 3.5 — Pack and worker migration

## Outcome

Close the write-path bypasses that would otherwise keep direct blob writes alive after the CLI primitives exist. Every pack and worker timeline mutation emits events through the `EventLogBackend` selected for that timeline, using the canonical schema package from m1. Legacy compatibility blobs may still be written or read as derived surfaces, but no pack or worker owns canonical timeline state by writing `assembly.json`, `hype.timeline.json`, `timelines.config`, or arrangement blobs directly.

After this milestone, `verify_chain` covers the full mutation surface used by packs and workers, not only interactive CLI edits.

Profile: `partnered/full/medium`. Estimated effort: 2-3 human-weeks.

## Scope (IN)

1. **`builtin.cut` wholesale timeline writes.**
   - Touchpoints: `astrid/packs/builtin/cut/run.py:1028`, `astrid/packs/builtin/cut/run.py:1193`.
   - Replace `save_timeline` canonical writes with event emission. Expected event kinds: `timeline.imported` for initial constructed timelines when no prior event stream exists, `timeline.config_replaced` for full raw TimelineConfig replacement, and the finer `clip.*`, `track.*`, `audio.*`, `effect.*`, `transition.*`, `theme.*`, and `pool.*` events where cut already has semantic intent.
   - Actor: `system` actor such as `"builtin.cut:<run_id>"`, with optional `actor.via` when invoked by an agent or human-driven orchestrator.
2. **`builtin.refine` timeline and arrangement writes.**
   - Touchpoints: `astrid/packs/builtin/refine/run.py:575`, `astrid/packs/builtin/refine/run.py:542`.
   - Replace `save_timeline` and `save_arrangement` canonical writes with `timeline.config_replaced` when the refine output is coarse-grained, or semantic clip/effect/track events when the refine step can name the edit.
   - Actor: `agent` when an agent chose/refined the edit, otherwise `system` `"builtin.refine:<run_id>"`; carry human/agent provenance in `actor.via`.
3. **`iteration.assemble` two-file timeline writes.**
   - Touchpoints: `astrid/packs/iteration/assemble/run.py:108`, `astrid/packs/iteration/assemble/run.py:109`.
   - Emit events for both generated timeline files before writing derived compatibility outputs. Expected event kinds: `timeline.imported` for lineage seed, `timeline.config_replaced`, and relevant `clip.*` / `track.*` / `audio.*` events.
   - Actor: `system` `"iteration.assemble:<thread_or_run_id>"`.
4. **`builtin.hype` arrangement and `hype.timeline.json` paths.**
   - Touchpoint: `astrid/packs/builtin/hype/run.py`, including direct `load_arrangement` / `save_arrangement` calls and 14+ references to `hype.timeline.json`.
   - Route canonical mutations through event APIs; keep `hype.timeline.json` as a read/write compatibility projection only while m4/m8 consumers still require it.
   - Expected event kinds: `timeline.config_replaced`, `clip.*`, `track.*`, `audio.*`, `pool.*`, and `theme.*` as applicable to the concrete hype stage.
   - Actor: proximate writer wins. Human-launched CLI runs use `human`; agent/orchestrator-launched hype uses `agent`; internal stage rewrites use `system` with `actor.via`.
5. **`open_in_reigh` LocalFs -> Supabase bridge.**
   - Touchpoint: `astrid/packs/builtin/open_in_reigh/run.py:193`.
   - Declare this pack as the explicit LocalFs-to-Supabase bridge. Before m6 it may stage derived outputs as compatibility data. After m6 it uses both backends: read LocalFs events, replay them into Supabase via `append_timeline_event`, and never cross the boundary through `SupabaseDataProvider.save_timeline`.
   - Expected event kinds: replay the original event kinds unchanged, preserving `event_id` only if the m6 idempotency contract permits safe import; otherwise record a bridge `txn_id` and source metadata. Do not emit blob-diff events.
   - Actor: `system` `"open_in_reigh:<invocation_ref>"`, with original actors preserved in replayed events and bridge provenance in `actor.via` or import metadata as designed by m6.
6. **`publish` read-only projection consumer.**
   - Touchpoint: `astrid/packs/builtin/publish/run.py:520`.
   - Confirm it reads through the m4 projection / compatibility blob and does not create a new write bypass. Add regression tests to keep it read-only.
   - Actor: none for reads; if publish records timeline metadata later, it must use a `system` actor.
7. **Banodoco worker generation write-back.**
   - Touchpoint: `astrid/core/integrations/worker/banodoco_worker.py:344`.
   - Replace `provider.save_timeline` after generation tasks with event appends through the selected backend.
   - Expected event kinds: use semantic generated edit kinds where available (`clip.added`, `clip.replaced`, `asset`/pool events from m3), or `timeline.config_replaced` for coarse generation outputs.
   - Actor: `system` `"banodoco_worker:claim:<task_id>"` or equivalent, with `actor.via` preserving the user/agent task initiator.

## Anti-scope

- Legacy compatibility blob reads remain supported, but no new write-side blob bypasses are allowed.
- Reigh-app web UI migration is not part of m3.5; m6 owns it.
- CLI mutation verbs are not expanded here; m2 and m3 own those APIs.
- Projection purity and golden fixtures remain m4's job.
- Supabase RPC implementation remains m6's job. `open_in_reigh` only switches to true replay once m6 exists.

## Locked Decisions

- Pack and worker writes use `EventLogBackend`; they do not write `assembly.jsonl` directly.
- Every pack/worker event has an actor matching the m1 schema. The proximate writer wins; upstream human/agent provenance goes in `actor.via`.
- `arrangement.replaced` is migration-only legacy. Coarse pack outputs use `timeline.config_replaced`; planners must prefer semantic m2/m3 events where the pack already knows the edit.
- Compatibility outputs are derived surfaces. A pack may refresh them only after appending events and only through the projection/helper path designed for m4.
- `open_in_reigh` is the named cross-boundary bridge; other packs must not invent LocalFs-to-Supabase blob copy paths.

## Open Questions

- Which pack outputs can be decomposed cleanly into semantic m2/m3 events versus requiring `timeline.config_replaced`?
- Should bridge replay preserve original event ids or create new Supabase event ids with source-event metadata?
- How should pack run ids be normalized for actor ids when a pack is invoked outside task-mode?
- Do pack-produced assets need stable `asset_ref` payloads before all URL-stability decisions are resolved in m6/m9?

## Constraints

- Do not break existing rendered outputs. Compatibility blobs should remain byte- or schema-equivalent where current consumers require them.
- Do not mutate plan files or task event logs by hand.
- Tests must not require Supabase credentials except for bridge tests explicitly gated after m6.
- No new direct calls to `save_timeline`, `save_arrangement`, or `SupabaseDataProvider.save_timeline` may remain on write paths after migration.

## Done Criteria

- Every listed pack and worker write path emits timeline events before any compatibility output is refreshed.
- Agentic tests cover every migrated pack write path with explicit actor attribution, including `actor.via` where provenance is chained.
- `astrid timelines audit` passes for every pack-produced timeline fixture.
- `open_in_reigh` is documented and tested as the only LocalFs -> Supabase bridge path, with true RPC replay activated once m6 is present.
- `publish` is tested as a projection/compatibility read consumer and does not write canonical timeline state.
- A repository search for the named direct-write APIs finds no unapproved pack/worker write bypasses.

## Touchpoints

- `astrid/packs/builtin/cut/run.py:1028`
- `astrid/packs/builtin/cut/run.py:1193`
- `astrid/packs/builtin/refine/run.py:575`
- `astrid/packs/builtin/refine/run.py:542`
- `astrid/packs/iteration/assemble/run.py:108`
- `astrid/packs/iteration/assemble/run.py:109`
- `astrid/packs/builtin/hype/run.py`
- `astrid/packs/builtin/open_in_reigh/run.py:193`
- `astrid/packs/builtin/publish/run.py:520`
- `astrid/core/integrations/worker/banodoco_worker.py:344`
- Event APIs and schema package from m1-m3.
- Pack/worker agentic test fixtures selected by the planner.
