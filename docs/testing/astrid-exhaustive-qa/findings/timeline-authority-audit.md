# Timeline authority audit

Date: 2026-08-24

Scope: read-only audit of timeline create/save/archive/unarchive/history/diff,
visualization, rendering, shots/references, and backup/restore. No product or
test source was changed.

## Short answer

The public timeline CRUD path is kernel-backed: the `timelines` row is the
current snapshot, `event_streams.head_seq` is `config_version`/CAS, and the
kernel `events` table is the immutable hash-chained audit. `TimelineRepository`
updates the row and appends the corresponding event in one SQLite UoW
(`astrid/packs/timeline/repository.py:894-1150`; event append contract:
`astrid/core/events/service.py:288-329`). Archive state is correctly derived
from the latest archive/unarchive event, not a row column
(`astrid/packs/timeline/repository.py:119-138,2053-2067`).

That is not yet one consistent source of truth for consumers. The old managed
filesystem (`timelines/<ULID>/assembly.jsonl` plus JSON sidecars) is still a
second event-log/projection system. The managed write gateway can commit both
stores, but commits the kernel first and the filesystem eventlog second, so the
two resources are not atomic (`astrid/core/timeline/_edit_helpers.py:354-368,
444-550`). Legacy CRUD can also write filesystem state without a kernel
`timeline.created` event (`astrid/core/timeline/crud.py:73-143`).

Most importantly, `timelines visualize` is reproducibly not rendering the
actual kernel event log. If no legacy directory exists, it reads the current
kernel projection (`document_json`/`asset_registry_json`), creates a private
two-event synthetic filesystem log, and then runs the old snapshot reader
(`astrid/packs/rendering/executors/timeline_visualize/select.py:189-272`;
`.../run.py:311-375,1120-1142`). The synthetic events use the current wall-clock
timestamp and freshly generated event IDs. Root's live run produced different
snapshot event-head versions/IDs and SNS digests for repeated unchanged
visualizations (`/private/tmp/astrid-authority.e4cKzw/{viz1,vizsvg,vizpng}.json`).
This is a high-severity reproducibility/authority defect: the same unchanged
kernel timeline does not have a stable visualization snapshot identity.

## Write and read paths

| Operation | Current authority and path | Finding |
| --- | --- | --- |
| Create | Inserts `event_streams`, `timelines`, and `timeline.created` in one UoW; default is in project `settings_json` (`repository.py:645-890`). | Sound kernel snapshot + audit contract. Filesystem legacy create is separate and does not emit the kernel event. |
| Save | Reads row/head, performs expected-version CAS, updates `timelines.document_json` and registry, appends `timeline.saved`, records receipt (`repository.py:894-1150`). | CAS and mutation are atomic within SQLite. Event payload carries the full saved snapshot. |
| `replace_config` | Same CAS/projection pattern, but appends `timeline.config_replaced` (`repository.py:1152-1410`). | **Omission:** this event is declared and written but excluded from `_TIMELINE_HISTORY_KINDS` (`repository.py:140-149,2017-2051`), so public history/diff silently skip a real version. |
| Archive/unarchive | Appends lifecycle events; latest transition is state (`repository.py:1412-1643,2053-2067`). | Correct for the kernel path; no archive column is needed. |
| History/diff | Queries only created/saved/archived/unarchived and uses created/saved payload snapshots (`repository.py:1915-2013,2017-2051`). | Incomplete after `config_replaced`; this is not a faithful event history. |
| Legacy filesystem edit | Appends `assembly.jsonl`, hash-checks/repairs `assembly.head.json`, and projects `assembly.json` (`astrid/core/timeline/eventlog/local_fs.py:58-134`; snapshot authority `astrid/core/timeline/snapshot.py:555-605,649-734`). | A complete older event-sourced model, but it can coexist with the kernel model. |
| Managed editor write | `pack_write_gateway` resolves/binds kernel and commits `replace_config` before appending filesystem events (`_edit_helpers.py:354-368,444-550`). | Fail-closed and preflighted, but still a cross-DB/filesystem two-phase sequence; a post-kernel filesystem failure can leave divergence. |

## Visualization versus rendering

`timelines visualize` first prefers a legacy managed directory; only if none is
selected does it query kernel rows (`run.py:386-417`). Kernel selection directly
reads `t.document_json`, `t.asset_registry_json`, and `s.head_seq`, not a replay
or verification of the kernel `events` chain (`select.py:226-272`). It then
materializes synthetic `timeline.config_replaced` and
`timeline.asset_registry_replaced` events with a fresh timestamp/IDs
(`run.py:328-375`) and feeds those to `acquire_snapshot` (`run.py:1120-1142`).
Thus the route is “kernel current row -> ephemeral old eventlog -> renderer,”
not “kernel event log -> renderer.” A stale/tampered row can disagree with
kernel history while visualization still succeeds.

If a legacy directory exists for the same selector, it wins over the kernel
row. Consequently two representations with the same apparent timeline slug
can produce different content, history, and snapshot identity. Explicit
`timeline_source` is also a filesystem path under the project timeline root,
not a kernel reference (`astrid/sdk/invocation.py:357-425`).

`rendering.render` is a different API: its input is an arbitrary resolved
`timeline_path` (and optional assets registry path), with no UUID/ULID/slug
resolution (`astrid/sdk/rendering.py:366-424`; executor facade
`astrid/packs/rendering/executors/render/run.py:247-303`). It therefore cannot
guarantee that a render uses the canonical kernel timeline unless the caller
first exports/materializes one.

## Shots and references

Shots and references are independent kernel aggregates. The shots repository
explicitly says the only cross-pack currency is exact kernel `media_id` and it
does not FK/import the timeline pack (`astrid/packs/shots/repository.py:1-10`).
The references schema owns project/media references and links, with its own
`reference.reference` stream (`astrid/packs/references/schema-pack.yaml:7-16`).
Neither pack has a timeline foreign key or an alternate timeline authority;
timeline config may contain IDs, but those are payload-level links.

## Backup and restore

Backup is a consistent SQLite snapshot plus `.astrid/media` digest tree and
metadata (`astrid/core/backup/operations.py:1-28,337-400`). It does not copy
project `timelines/<ULID>` eventlogs or sidecars. Therefore kernel timeline
events/history survive restore, while legacy filesystem timeline history does
not. A restored project can change visualization from real eventlog selection
to synthetic kernel materialization, which is another observable authority
split.

## Recommended contract

Use **kernel snapshot + append-only audit**, rather than making the old
filesystem log a second event-sourced aggregate:

1. The SQLite kernel is the sole authority for a timeline. The row is the
   current snapshot; `event_streams.head_seq` is the CAS/config version; every
   mutation (`created`, `saved`, `config_replaced`, `archived`, `unarchived`)
   appends one immutable hash-chained event in the same UoW.
2. Treat every snapshot-bearing event as history. Include
   `timeline.config_replaced` in history and diff, or add a version-snapshot
   table if future events stop carrying full snapshots. Do not silently filter
   committed aggregate events.
3. Make all kernel readers use one resolver/snapshot service. Visualization
   should resolve a kernel ref and build a deterministic snapshot from the
   persisted row/events; synthetic compatibility files must use stable IDs,
   timestamps, and provenance derived from the kernel event (not `now()`). A
   matching legacy directory must not outrank a kernel timeline. Keep explicit
   filesystem input only as a clearly named kernel-less compatibility mode.
4. Either remove filesystem eventlog writes for kernel-bound timelines, or make
   them a derived export with kernel event seq/id/hash provenance and a
   reconciliation/regeneration step. The current commit-kernel-then-append-file
   sequence is not a transaction across both authorities.
5. Add a canonical `timeline_ref`/project-aware path to rendering, or require
   callers to state that `rendering.render` consumes an exported file snapshot.
   Do not infer canonicality from an arbitrary path.
6. Once the filesystem log is derived-only, SQLite backup is sufficient. Until
   then, backup/restore must either include and verify those exports or
   regenerate them from the restored kernel before serving visualization.

## Live-test hypotheses

- Create a kernel timeline, invoke the repository's `replace_config`, then
  compare SQL event kinds/counts with `timelines history` and `timelines diff`.
  The kernel will contain `timeline.config_replaced`; the public outputs will
  omit that version.
- Create a matching legacy directory and kernel timeline, deliberately diverge
  their config, then visualize by slug/default. The filesystem representation
  should win, while `timelines show/history` report the kernel representation.
- Repeat kernel-only visualization without changing the timeline. Compare
  `snapshot.event_head`, event IDs, and SNS fields; they should vary because
  `_materialize_kernel_timeline` uses `TimelineEvent.new` and `datetime.now`.
  Root already observed this in the temporary evidence cited above.
- In a disposable copied database, alter only `timelines.document_json` and
  run `events verify` versus visualization. Verification/history should follow
  the event chain; visualization should follow the altered row, proving the
  projection-authority mismatch.
- Back up and restore a project containing both kernel and legacy timeline
  state. Confirm the DB events remain while `timelines/<ULID>/assembly.jsonl`
  is absent, and observe the visualization route change after restore.

