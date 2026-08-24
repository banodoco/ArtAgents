# Restored event readback fix

**Date:** 2026-08-23  
**Surface:** live project-scoped SDK invocation, public CLI, backup/restore  
**Scope guard:** fresh disposable roots; no cloud credentials or cloud calls.

## Finding

The corrected maker acceptance flow could successfully invoke
`rendering.render` and the kernel CLI `runs events` read model, but
`astrid.read_events(..., verify=True)` depended on the optional filesystem
`runs/<run_id>/events.jsonl` projection. Portable backup preserves the
canonical SQLite ledger, not that local process projection, so restored SDK
readback failed with a misleading run-not-found error.

The kernel event tables remain the single execution authority. The fix keeps
the filesystem stream as the preferred SDK source when present and adds a
read-only fallback to the matching `core.run` SQLite stream when the
projection is absent. Fallback records use `EventStreamRecord(source="kernel")`
and preserve event id, project/stream sequence, kind, timestamp, domain data,
and both integrity hashes. With verification enabled, the fallback checks the
stream head/count, contiguous sequence, previous-hash links, and recomputed
event hashes. It rejects a run addressed through another project and fails
closed as `CapabilityEventLogError` on corruption; it never creates a
projection or writes the restored root.

## Live proof

Fresh roots:

- source: `/tmp/astrid-event-live-source2.9Yuwea`
- backup: `/tmp/astrid-event-live-backup2.GwMSoV`
- restore: `/tmp/astrid-event-live-restore2.rjlFSH`
- project: `evt-demo`
- successful render run: `85195cd53313c655616995f3d7`

The agent authored a visible `HELLO ASTRID` text timeline and invoked the
public SDK capability with the full 640×360 H.264/AAC profile and strict
`rendering.remotion` backend. `InvocationResult.ok` was `True`. The run's
`core.run` stream contained:

```text
core.run.created
event_id=69291051585b4299b46cb8cf589281c7
event_hash=e1da7fdf5fa44943d69793a3415344bd07ae25fcf1abd704e51dfa6b7716c725
```

Before backup, CLI `runs events` and SDK `astrid.read_events(...,
verify=True)` agreed on kind and event id. The run directory projection was
not present, so this also exercised the fallback before restore.

The source root contents were then deleted. After `backup create` and a
cross-root `backup restore`, the restored run directory projection was still
absent, while the kernel database was present. The restored public CLI and
SDK outputs matched exactly:

```text
CLI: core.run.created / 69291051585b4299b46cb8cf589281c7
SDK: kernel / core.run.created / 69291051585b4299b46cb8cf589281c7
match: True
verify=True: passed
```

## Focused regression coverage

`tests/sdk/test_restored_event_readback.py` covers:

1. fallback read with no filesystem projection;
2. cross-project run-id rejection; and
3. tampered kernel payload rejection with typed event-log failure.

Focused result:

```text
pytest -q tests/sdk/test_restored_event_readback.py
3 passed

pytest -q tests/sdk/test_restored_event_readback.py \
  tests/test_onboarding_parity.py -k 'read_events or subscribe_events' \
  tests/test_sdk_public_surface.py -k 'read_events or subscribe_events'
11 passed, 119 deselected
```

The SDK reference, first-agentic-UX guide, and core skill now document the
source distinction and restored-run fallback contract.
