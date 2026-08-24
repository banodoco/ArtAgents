# Timeline authority correction

Date: 2026-08-24

## Outcome

Timeline visualization now follows one explicit authority contract:

- implicit/default/slug/UUID/ULID/`all` selection resolves the canonical SQLite
  timeline only;
- the row is the current snapshot projection and the immutable hash-chained
  stream head supplies the version/hash provenance;
- a filesystem `assembly.jsonl` remains available only through the explicit
  `timeline_source` legacy compatibility input;
- `rendering.render` remains explicit file mode. It consumes an exported or
  pipeline-produced timeline JSON and does not resolve managed timeline refs.

This is deliberately snapshot-plus-append-only-audit, not a second
filesystem event-sourced aggregate.

## Corrections

### Kernel selection and deterministic identity

`select_kernel_timelines` now captures the actual tail event id, integrity
hash, timestamp, and `event_streams.head_seq`. Cold managed selectors query
that path first and never allow a matching legacy directory to outrank it.

The private compatibility materialization no longer uses wall clock time or
random event IDs. Its schema-compatible event IDs are stable functions of the
kernel tail. After projection, the frozen snapshot is pinned to:

- the real kernel stream version;
- the real kernel tail hash;
- a deterministic ULID-shaped public compatibility ID (the evidence schema
  requires ULIDs while kernel event IDs are UUID hex);
- the exact kernel event UUID and hash in `KERNEL_AUTHORITY` diagnostics.

Invalid canonical configs are no longer replaced with an empty timeline. A
missing/non-array `tracks` or `clips` fails with a save-and-retry instruction;
deeper timeline schema failures remain explicit rather than changing content.

### History and diff

`timeline.config_replaced` is now in the lifecycle history query and is treated
as a snapshot-bearing version by both `history` and adjacent-version `diff`.
Archive/unarchive remain ordered lifecycle versions and do not masquerade as
content changes.

### Invocation cache and exact replay

Visualization idempotency now includes the resolved canonical timeline ID,
head version, kernel event ID, and kernel hash. A timeline mutation therefore
mints a new run even when command flags are unchanged. Legacy explicit sources
include the `assembly.jsonl` digest.

An unchanged exact replay still returns the original run, but now reconstructs
the complete durable `outputs.artifacts` set from `task_outputs` instead of
returning `ok: true, outputs: {}`.

### Durable frozen navigation

The visualization pack hash ledger is now published as a secondary kernel
output. `from_view` accepts the durable manifest CAS path returned by the
public command, resolves its exact completed project/task ownership, rehydrates
all sibling outputs from their verified CAS locators, verifies every digest and
the pack ledger, and then performs frozen navigation. Foreign CAS files and
non-visualization outputs remain rejected.

## Fresh live public journey

Disposable root:

```text
/private/tmp/astrid-timeline-fix.Xzm7gH
```

The journey used only public CLI commands for project/timeline work:

```bash
export ASTRID_PROJECTS_ROOT=/private/tmp/astrid-timeline-fix.Xzm7gH
python3 -m astrid projects create authority-fix --name "Authority Fix" --json
python3 -m astrid timelines create main --project authority-fix --name Main \
  --default --config '<config>' --registry '{"assets":{}}' --json
python3 -m astrid timelines save main --project authority-fix \
  --config '<v2-config>' --registry '{"assets":{}}' \
  --expected-version 1 --json
python3 -m astrid timelines visualize main --project authority-fix \
  --format md --json
python3 -m astrid timelines visualize main --project authority-fix \
  --format png --json
python3 -m astrid timelines save main --project authority-fix \
  --config '<v3-config>' --registry '{"assets":{}}' \
  --expected-version 2 --json
python3 -m astrid timelines history main --project authority-fix --json
python3 -m astrid timelines diff main --project authority-fix --json
python3 -m astrid timelines archive main --project authority-fix --json
python3 -m astrid timelines unarchive main --project authority-fix --json
```

Observed evidence:

- unchanged v2 MD and PNG visualizations had identical
  `SNS:49ae8b1a2500fbd0eec7d21a6bc3e18d0fd179d7efc1c6553ead6a6004a74886`;
- both reported event-head version `2` and real tail hash
  `e85f768d095858658288fd30f66ac782a607ef205b04282bef9d2d4824b68e7e`;
- saving v3 changed the run from `059b111a59c5709d4d92a6cc17` to
  `f961448e5e78e328395b09d635` and advanced the snapshot;
- exact v3 replay returned run `f961448e5e78e328395b09d635` again with all
  11 durable artifacts, not an empty output mapping;
- after archive/unarchive, history was exactly created v1, saved v2, saved v3,
  archived v4, unarchived v5;
- v5 MD and PNG runs (`da495e5e47a1cc3e914eb159fb` and
  `16c7afa320743af31ca0c23bde`) shared
  `SNS:9ab8018156969152abfb5f6a91db5703840150ed524c2a1b06f52a45a9fa8347`;
- both reported version `5` and hash
  `d0fdcb611c736eddb763c249c698e0b867147720627c9e30e7a62e770dd3d853`,
  exactly matching the SQLite stream tail. Diagnostics retained exact kernel
  event UUID `bba23280f3df496ea4e1cd539b4e4514`;
- frozen navigation from the returned durable CAS manifest succeeded as run
  `a35f7da9ae2fc1f393489601d6` with 12 durable artifacts.

The first deliberately malformed timeline used a track with the wrong kind
and omitted required label. Visualization failed explicitly with the timeline
schema error; it did not silently visualize an empty replacement.

## Focused checks

```text
python3 -m compileall -q <changed Python paths>     PASS
git diff --check -- <changed paths>                 PASS
pytest -q tests/v10/test_replace_config.py \
  tests/v10/test_timeline_repository.py \
  tests/sdk/test_timelines.py                       73 passed
```

The targeted frozen-suite run reached the pre-existing expectation that a
returned manifest lives under `<project>/runs`; the current kernel completion
contract correctly returns a durable root-level CAS locator instead. The fresh
public `from_view` replay above is the primary acceptance evidence for the
corrected durable contract.

## Remaining boundary

The compatibility snapshot schema requires `event_head.last_event_id` to be an
uppercase ULID, while core kernel event IDs are UUID hex. The evidence pack
therefore exposes a deterministic mapped ID in that field and the exact kernel
UUID in diagnostics; the version and hash are the real kernel values. A future
schema revision could add a distinct `source_event_id` field and remove this
adapter without changing authority.
