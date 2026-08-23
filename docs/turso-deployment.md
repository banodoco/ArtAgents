# Turso deployment — the remaining step (DC4)

This is THE remaining deployment step before hybrid sync is live (done-criteria 4 conditional). Everything else (local SQLite authority, kernel writes, backfill marker discipline) is already cut over.

## What this doc covers

Provisioning a Turso database, applying the S-owned replica schema, installing the driver, setting env, first-sync and steady-state polling. No data is lost; local SQLite stays authority.

## 1. Provision Turso (once)

```bash
# via turso CLI
turso db create astrid-timelines --group <group>  # pick region near your users
turso db show astrid-timelines --url      # → libsql://astrid-timelines-xxx.turso.io
turso db tokens create astrid-timelines --expiration none
```

Record URL and token as `TURSO_DATABASE_URL` and `TURSO_AUTH_TOKEN` (see §3).

## 2. Apply the replica schema (R1)

DDL originates in `ArtAgents/packages/timeline-schema/sql/turso/0001_turso_replica_schema.sql` and is S-owned (R1). The local schema-pack runner covers local migrations (``0001–0003``) only; the Turso replica schema is applied separately via the replica transport — not through the local runner. Astrid does NOT vend a copy of the Turso DDL: `astrid/packs/timeline/schema-pack.yaml` lists only `migrations/0001_initial.sql` through `0003_add_source_provenance.sql` (local authority tables). The sole source is the sibling S checkout at `../ArtAgents/packages/timeline-schema/sql/turso/0001_turso_replica_schema.sql` relative to the Astrid repo root (or `/workspace/goalmd-sqlite-20260822/repos/ArtAgents/...` in CI).

**From Astrid (replica schema applicator):**

The replica schema file contains multiple statements (two tables + two indexes) and must be split before batch execution (libsql executes one statement at a time). Use the quote/comment-aware splitter:

```python
from pathlib import Path
from astrid.core.timeline.eventlog.turso import (
    FakeTursoTransport,
    LibSqlHttpTransport,
    TursoReplicaClient,
    apply_replica_schema,
)

sql = Path("../ArtAgents/packages/timeline-schema/sql/turso/0001_turso_replica_schema.sql").read_text()
# against a transport (or TursoReplicaClient — both accepted):
transport = FakeTursoTransport()  # swap for LibSqlHttpTransport() in prod (reads TURSO_* env)
stmts = apply_replica_schema(transport, sql)
print(f"turso replica schema applied ({len(stmts)} statements)")
# or via the replica client:
# replica = TursoReplicaClient(transport)
# apply_replica_schema(replica, sql)
```
Or apply via `turso` CLI shell:

```bash
turso db shell astrid-timelines < ../ArtAgents/packages/timeline-schema/sql/turso/0001_turso_replica_schema.sql
```

Verify:

```bash
turso db shell astrid-timelines "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
# → documents
# → events
```

Checksums: `bash ArtAgents/packages/timeline-schema/scripts/check-codegen.sh` must exit 0 (covers `sql/turso/CHECKSUMS` freshness; drift fails loudly). Pipeline: `sql/turso/*.sql` is parse-valid on `:memory:`, additive-only, and strictly versioned (`0001_...`).

## 3. Env vars (typed, fail-closed)

Turso transport is lazy and optional — Astrid serves without it.

```bash
export TURSO_DATABASE_URL="libsql://astrid-timelines-xxx.turso.io"
export TURSO_AUTH_TOKEN="eyJ..."   # turso db tokens create output
```

Absent env → `TursoConfigError` with actionable message (no silent fallback). The driver itself is optional:

```bash
pip install libsql-experimental   # provides `libsql_experimental` (Turso HTTP client); `libsql` also accepted
# Without it, first operation (execute_batch/query) raises TursoConfigError:
#   "libsql driver is not installed — install with: pip install libsql-experimental ..."
# LibSqlHttpTransport() construction succeeds with env set; the driver is loaded lazily at first use.
# The transport accepts either `import libsql` or `import libsql_experimental` (fallback) — both share the same connect surface.
```
`grep -rn "turso" astrid | grep -v test` shows only `astrid/core/timeline/eventlog/turso.py`, `astrid/core/timeline/turso_sync.py`, and this doc/env seams — no pub-sub, no websocket, no LWW.

## 4. Driver install (optional dep)

`pyproject.toml` does NOT list `libsql`; add only on hosts that sync:

```toml
# optional extra (not required for local-only deploys)
# pip install 'astrid[turso]'  # if you vendor an extra; otherwise see above
```

Local SQLite stays authority; the editor never imports `turso.py`.

## 5. First sync (one timeline, manual)

Turso sync is polling + watchdog ack (no pub-sub). The polling service reuses `sync_state` primitives and `write_keep_both_artifact` fork pattern.

**Entry points (library, not CLI):**

```python
from pathlib import Path
from astrid.core.timeline.eventlog.sqlite_backend import SqliteEventLogBackend
from astrid.core.timeline.eventlog.turso import FakeTursoTransport, TursoReplicaClient
from astrid.core.timeline.turso_sync import push_to_turso, pull_from_turso

backend = SqliteEventLogBackend(timeline_id=tid, timeline_home=home, projects_root=root)
replica = TursoReplicaClient(FakeTursoTransport())  # swap for LibSqlHttpTransport() in prod

# push drain + document+version as ONE remote unit (atomic batch)
result = push_to_turso(timeline_id=tid, timeline_home=home, projects_root=root, backend=backend, replica=replica)
print(result.action)  # pushed | up_to_date | conflict

# poll loop (steady-state): pull
result = pull_from_turso(timeline_id=tid, timeline_home=home, projects_root=root, backend=backend, replica=replica)
if result.action == "conflict":
    print("both diverged → your-copy/their-copy artifacts written, authorities intact")
```

Cursor/bookmark: `turso-sync-state.json` inside `timeline_home` (file-based, like `sync_bookmark_path`). Idempotent resume across restarts; interrupted mid-push resumes without duplicating (event_id upsert on remote; cursor advances ONLY after remote commit).

**Manual runbook for first sync:**

1. Ensure backfill marker is present (`<projects_root>/.astrid/backfill-state.json` contains timeline id → SQLite authority). Unmarked timelines stay on `local_fs` and are not synced until backfilled.
2. Run `push_to_turso` once for each backfilled timeline. The first push carries the whole history; the cursor file is created atomically after the remote batch commits.
3. Verify `<timeline_home>/turso-sync-state.json` exists and `replica.fetch_remote_head(tid)["version"]` equals local `backend.head().version`.

Run `pull_from_turso` + `push_to_turso` on a timer (e.g. every 15–30s per timeline) under process supervision. The service:

- reads local via `backend.read_events(after=..., limit=...)` (protocol, not ad-hoc SQL);
- pushes as one batched transaction (fake emulates atomic all-or-nothing; `LibSqlHttpTransport` uses `BEGIN`/`COMMIT`);
- on pull, if `remote version == local known` → no-op; if `local unchanged and remote newer` → applies through `UnitOfWork`/`append_imported_event` (preserves ids, or remaps with continuity — documented in `turso_sync.py` as import-remap; tested via `test_turso_sync.py::test_pull_clean_applies_through_uow`);
- if both diverged → writes `divergence-*.json` artifacts via `sync_divergence.write_keep_both_artifact` (primary, full your-copy/their-copy event payloads + `skipped_rows` diagnostics), returns `conflict`, never overwrites, never merges, never LWW.
  - attribution boundary: remote attribution collapses to the sync agent on apply — pulled events are re-attributed to `turso-sync:pull` (`system`) via `append_imported_event`; the replicated `actor_kind`/`actor_id` columns are preserved only inside the divergence artifact, not on the imported row (asserted in `tests/regression/test_s4_rework1_regressions.py::TestAttributionCollapsed`).
Ownership: the pull path catches typed `OwnerLockError` (direct) and `EventLogError` wrapping `OwnerLockError` (backend seam) → `TursoOwnershipError` (no substring sniffing) and fails closed with that typed error if serve already owns the DB — no second writable connection is opened concurrently. A generic `EventLogError` or other failure whose message happens to contain "owned" is classified as `TursoSyncError`, not ownership.

## 7. Observability

- `turso-sync-state.json` is JSON; inspect `remote_version` / `local_version`.
- `replica.fetch_remote_head(tid)` gives remote version, last_event_id, last_hash.
- Divergence artifacts: `ls <timeline_home>/divergence-*.json` + check `TursoSyncResult.conflict_artifacts`.
- Logs: `TursoSyncError` and `TursoConfigError` are typed; absence of env/driver fails closed before any network call.

## 8. CLI posture

No new `astrid timelines turso-*` verb was added. The existing `timelines` gateway (`astrid/packs/timeline/cli.py`) is a product-family parser for create/list/show/save/archive/history/diff/backfill plus nested `shots`; adding a polling daemon verb would not be a thin (~<40 line) registration over `turso_sync.push_to_turso`/`pull_from_turso` — it would require supervision, timer, and multi-timeline Fan-out that belongs in a service, not a one-shot CLI. The service entry points are the two functions above; operators wire them under their process manager (systemd, launchd, or `hub` `ps`).

If a manual trigger is needed, run a one-liner with the snippet in §5 (or `python -m astrid.core.timeline.turso_sync` if you add a thin wrapper — document here instead of shipping a verb).

## 9. Cutover note

- Local SQLite is THE authority; Turso is REPLICA target only — never a selector fallback, never co-authority.
- Replication allowlist: `timelines` identity columns (`timeline_id`, `project_id`, `event_stream_id`, `name`) + `document_json` + integer `version` and scoped `events` rows (`event_id`, `timeline_id`, `project_id`, `stream_id`, `seq`, `kind`, `payload_json`, `actor_kind`, `actor_id`, `txn_id`, `idempotency_key`, `created_at`) ONLY. `asset_registry_json` excluded; events with `data:`/`base64` payloads are refused (tested in `tests/timeline/test_turso_sync.py`).
- Supabase is demoted at cutover; nothing keeps both replicas (one writer, one file; bridge/FSA remains the asset plane).
- Sync machinery is polling + watchdog ack discipline only (no pub-sub).

## 10. Rollback

Delete `TURSO_DATABASE_URL` env or stop the polling service — local serves uninterrupted (selector never returns a Turso backend; see `test_turso_selector_isolation.py`). To re-enable, re-set env and resume polling; the cursor file is durable and idempotent.
