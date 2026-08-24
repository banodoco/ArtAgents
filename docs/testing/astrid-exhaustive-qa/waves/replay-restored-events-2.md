# Replay: restored event readback (wave 2)

Date: 2026-08-23

## Verdict

PASS for the requested restored kernel fallback path. The source project was
created and exercised only through the public CLI/SDK, backed up, removed from
its original root, and restored into a different disposable root. The restored
CLI and SDK readbacks retained run identity, status, event identity/order,
sequence, and integrity hashes.

## Disposable setup and invocations

- Source root: `/tmp/astrid-replay2.kFZXX8/source` (absent before restore;
  moved to a disposable tombstone because the command runner rejects recursive
  delete commands).
- Restored root: `/tmp/astrid-replay2.kFZXX8/restore`.
- Project: `replay2`, id `5fb331a3-1135-5ed2-b682-757b234a0b22`.
- Succeeded invocation/run: `editorial.quality_zones`, run
  `1d05179f748a96d8c920ef7ad5`, task `526364beeee162c2cb29d147d0`;
  restored status `succeeded` and one primary plus one secondary output.
- Failed invocation/run: `editorial.validate`, run
  `ba8f4b0c28d7fd0f8aea61b04e`, task `79d36d57d776c7c0d996302a69`;
  restored status `failed` with the expected terminal executor error.

Both task event chains were read back after restore and verified as intact:

| task | sequence/kinds |
| --- | --- |
| succeeded | `1 core.task.created` → `2 core.task.claimed` → `3 core.task.started` → `4 core.task.completed` |
| failed | `1 core.task.created` → `2 core.task.claimed` → `3 core.task.started` → `4 core.task.failed` |

Each chain's `previous_event_hash` matched the preceding event hash. The
run-level stream exposed by `runs events` contains its canonical
`core.run.created` record (sequence 1); the child lifecycle chain is exposed by
`tasks events`.

## Backup and restore

`backup create` succeeded with `media_files: 2` and `sqlite_pages: 140`.
Restore succeeded with `restored_media_files: 2`, `rebased_media_locators: 2`,
and zero unresolved external locators.

## CLI vs SDK comparison after restore

For both selected runs, `python3 -m astrid runs events ... --json` and
`astrid.read_events("replay2", run_id, projects_root=restore, verify=True)`
were compared field-for-field on event id, kind, order, sequence, and hash:

| run | source-vs-restored CLI | restored CLI-vs-SDK | SDK source |
| --- | --- | --- | --- |
| `1d05179f748a96d8c920ef7ad5` | identical | identical | `kernel` |
| `ba8f4b0c28d7fd0f8aea61b04e` | identical | identical | `kernel` |

The exact run-level records were:

- succeeded: event `2c2af30c8bed484f9c634dd009c4f021`, kind
  `core.run.created`, seq `1`, hash
  `9df6fbb78b947cfcb65b9f002147ad9f11114ba793da2e3ae7dee78cc96b5417`.
- failed: event `06738465908045c4b75b6b95951e89f7`, kind
  `core.run.created`, seq `1`, hash
  `8ff9fd1f02285e0cd5a7f9bd2b5f4f2fe2f4305c107af8787dd231d3a8b80643`.

No `run.json` or `events.jsonl` projection was produced by this public
invocation flow under either run. Therefore the SDK explicitly reported
`EventStreamRecord.source == "kernel"`, exercising the documented fallback;
it did not fabricate a projection.

## Typed failure checks

- Cross-project read: reading the succeeded run id under a newly created
  project `other` failed closed as typed `CapabilityPreconditionError` with
  `run ... not found in project 'other'`.
- Corrupt disposable event source: a malformed `events.jsonl` placed only in
  a separate disposable restored root failed closed as typed
  `CapabilityEventLogError` (`event log line 1 is missing hash`). No production
  database was edited.

The temporary roots and fixtures used for this replay are disposable; the only
workspace artifact intentionally retained is this report. No production code,
tests, or database were changed.
