# Live editor/CLI timeline authority wave 2

Date: 2026-08-24 (Europe/Berlin)  
Surface: public CLI, `astrid serve` HTTP bridge, public SDK event reads  
Root: disposable `/tmp/astrid-live-editor-timeline-BOb7wO`  
Product source edits: none

## Verdict

**Pass — the bridge and CLI converge on the same canonical kernel timeline.**

The editor bridge did not create or consume a filesystem `assembly.jsonl`
projection. HTTP CAS save, CLI show/history/diff, and timeline visualization
all read the same SQLite-backed timeline identity, document, registry, and
stream head. The only notable friction was operational: `astrid serve` takes
exclusive database ownership, so CLI reads/writes must wait for a clean
shutdown; the startup banner and `/routes` explain this accurately.

## Journey

### Fresh v1 and bridge discovery

Using only the public CLI, I created project `bridge-proof` and default
timeline `primary`:

- timeline UUID: `6c8dcfe0-ac51-5cf7-9a05-5297ef3982fd`
- timeline ULID: `vs67b04wz4a6q153vxaexfbsq9`
- v1: empty config and `registry.assets={}`
- CLI save advanced it to v2 with one valid text clip, `V1 BRIDGE`

The documented command started a local bridge on an ephemeral port. `GET
/routes` returned HTTP 200 and advertised the exact save contract:

```text
POST /projects/{project}/timelines/{timeline}/save
request: {config: object, registry: object, expected_version: integer}
response version: config_version
```

The bridge announced exclusive ownership of the SQLite database and directed
clients to use HTTP while it was running.

### HTTP CAS save → CLI reads and visualization

I POSTed a v2→v3 document through the documented route, adding a second text
clip `subtitle` with content `HTTP V3`. The response was HTTP 200 and
`config_version: 3`.

After cleanly stopping the bridge, public CLI reads returned:

- `timelines show`: version 3, exact timeline identity, config, and registry;
- `timelines history`: exactly three events (`timeline.created` v1,
  `timeline.saved` v2, `timeline.saved` v3), with the v3 event config exactly
  equal to `show.data.config`;
- `timelines diff`: v1→v2 added document fields, v2→v3 changed only `clips`;
- `timelines visualize primary --format md --json`: success, 11 durable
  artifact records, run `dd9f9890305ecbf000694338f5`, and a manifest snapshot
  with UUID/ULID/slug plus `event_head.version: 3`.

The visualization ground-truth contained both clips (`V1 BRIDGE` and
`HTTP V3`) and the same timeline identity. Its event-head hash was
`80051a61abcb9cc25bce46f5540eebbfb2c2ce544e7d483ed0a4d3483d29dac6`.

### Stale HTTP CAS

While the bridge was running again, I POSTed a conflicting document with
`expected_version: 2` after the current head had reached v3. The bridge
returned HTTP 409 with `timeline_version_conflict` and an actionable recovery:
show the current timeline, merge, and retry using `config_version: 3`.
The response explicitly said “no write occurred.” A subsequent HTTP read and
the later CLI history confirmed the stale payload was absent; the stream stayed
at v3 with only the expected three events.

### CLI save → HTTP readback

After stopping the bridge, CLI CAS-saved a third text clip `footer` with
content `CLI V4`, using expected version 3. The CLI returned version 4 and one
`timeline.save` receipt/event. After restarting the bridge, HTTP GET returned
version 4 and an exact deep comparison matched every identity, default flag,
config field, registry field, and version field from the CLI response.

The final CLI history contained exactly four events (v1 create, v2 HTTP-era
CLI save, v3 bridge save, v4 CLI save), and its latest event config/registry
matched `timelines show` exactly.

## Public event verification

The public `astrid.read_events(..., verify=True)` call read the visualization
run from the canonical kernel source (`EventStreamRecord.source="kernel"`).
The run stream exposed the expected `core.run.created` record. Public
`tasks events` for the visualization task exposed the complete four-record
hash chain:

```text
core.task.created   seq 1  previous=null
core.task.claimed   seq 2  previous=9115c4ae...
core.task.started   seq 3  previous=360b7e6d...
core.task.completed seq 4  previous=b16346fd...
```

All event hashes and links verified successfully. Timeline `history` is the
public timeline event read surface; it intentionally returns the document
snapshots and versions rather than exposing receipt/hash internals.

## Filesystem authority check

After both bridge sessions shut down cleanly, the disposable root contained
the SQLite kernel, project metadata, and CLI/HTTP evidence files. A recursive
search found no `assembly.jsonl`, `assembly.identity.json`, or
`assembly.head.json`. Visualization artifacts were published through the
managed content-addressed media store, not as a timeline source projection.

`doctor --json` passed all required checks after shutdown: data paths, media
paths, SQLite quick check, foreign keys, and core/references/shots/timeline
schema versions.

## Friction and severity

- **P2 operational handoff:** while `astrid serve` owns the database, a CLI
  command cannot read or save. This is deliberate single-owner behavior, and
  the startup banner plus `/routes` make the recovery (“use HTTP, then wait
  for shutdown”) discoverable. No data divergence observed.
- **P3 event detail split:** timeline history exposes versioned snapshots but
  not event hashes; run/task event verification is a separate public read.
  This is consistent with receipt/event-internal secrecy, but an agent doing
  end-to-end audit needs both `timelines history` and `tasks events`.

## Cleanup

Both bridge processes received Ctrl-C and printed `Shutting down...`; no
bridge process remained. The disposable root is retained only long enough for
QA evidence review and can be removed as a unit:

```text
/tmp/astrid-live-editor-timeline-BOb7wO
```

