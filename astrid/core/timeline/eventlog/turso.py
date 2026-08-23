"""Turso replica transport seam and Replica Client (S4).

R1: DDL originates in S (sql/turso/0001); this module consumes it.
R2: Replication allowlist is EXPLICIT and exhaustive (see constants below);
    asset_registry_json never replicates; negative tests prove it.
R3: Local SQLite is authority; Turso is replica target only.
R5: single authority discipline preserved; this client does not open local DB.
R6: polling only; fork-not-merge for pull conflicts is in turso_sync.py.

Two transports:
  - FakeTursoTransport: in-memory, batch-atomic, for tests.
  - LibSqlHttpTransport: lazy libsql HTTP driver, typed error when absent.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Protocol, Sequence


class TursoError(RuntimeError):
    """Base error for Turso replica operations."""


class TursoConfigError(TursoError):
    """Turso driver/env is missing (typed, actionable)."""


class TursoReplicationError(TursoError):
    """Replication was refused (allowlist / blob guard)."""


class TursoOwnershipError(TursoError):
    """Sync attempted to open a second writer while DB is owned."""


class TursoSyncError(TursoError):
    """Base error for Turso sync operations (typed diagnostic). Shared base so
    replica-layer collisions/races are also sync-typed."""


class TursoEventCollisionError(TursoSyncError):
    """Event collision: same key maps to different payload. Typed."""


class TursoVersionRaceError(TursoSyncError):
    """Document CAS failed: expected_remote_version mismatch. Typed."""
# ---------------------------------------------------------------------------

# documents (remote replica) — R2: identity + document_json + version, NO asset_registry_json
DOCUMENT_REPLICA_COLUMNS: tuple[str, ...] = (
    "timeline_id",
    "project_id",
    "event_stream_id",
    "name",
    "document_json",
    "version",
    "created_at",
    "updated_at",
)
DOCUMENT_REPLICATED_COLUMNS = DOCUMENT_REPLICA_COLUMNS  # alias for negative test discovery
DOCUMENT_REPLICA_TIMELINE_ID_COL = "timeline_id"

# events (remote replica) — scoped timeline events rows only
EVENT_REPLICA_COLUMNS: tuple[str, ...] = (
    "event_id",
    "timeline_id",
    "project_id",
    "stream_id",
    "seq",
    "kind",
    "payload_json",
    "actor_kind",
    "actor_id",
    "txn_id",
    "idempotency_key",
    "created_at",
)
EVENT_REPLICATED_COLUMNS = EVENT_REPLICA_COLUMNS

# Consolidated allowlist — every column that may cross the wire
ALL_REPLICATED_COLUMNS: frozenset[str] = frozenset(DOCUMENT_REPLICA_COLUMNS + EVENT_REPLICA_COLUMNS)

# Provenance v1 decision (amendment 6): source_* columns are NOT replicated.
# If added later, they will be a new additive turso migration.
REPLICATED_EXCLUDES_SOURCE_PROVENANCE = True

TURSO_ENV_URL = "TURSO_DATABASE_URL"
TURSO_ENV_TOKEN = "TURSO_AUTH_TOKEN"

# ---------------------------------------------------------------------------
# Blob guard — R2 negative tests must match
# ---------------------------------------------------------------------------

_DATA_URI_RE = re.compile(r"data:[a-zA-Z0-9/+\-]+\s*;\s*base64\s*,", re.IGNORECASE)
_LONG_BASE64_RE = re.compile(r"[A-Za-z0-9+/]{800,}={0,2}")


def _contains_blob_payload(value: str) -> bool:
    if _DATA_URI_RE.search(value):
        return True
    # also catch raw long base64 without data: prefix (conservative)
    if _LONG_BASE64_RE.search(value):
        # only treat as blob if surrounding json suggests asset bytes
        # — we check for data: or base64 hints nearby
        if "base64" in value.lower() or "data:" in value.lower():
            return True
        # even without hint, a very long base64 string is suspicious for assets
        # — require explicit refusal path via >1000 contiguous base64
        if len(value) > 2000 and _LONG_BASE64_RE.search(value):
            return True
    return False


def _assert_no_blob_in_payload_json(payload_json: str) -> None:
    if _contains_blob_payload(payload_json):
        raise TursoReplicationError(
            "replication refused: payload contains data-URI/base64/blob content (R2)"
        )
    # also parse and inspect string values for data URIs
    try:
        obj = json.loads(payload_json)
    except Exception:
        return

    def _walk(node: Any) -> None:
        if isinstance(node, str) and ("data:" in node and "base64" in node):
            raise TursoReplicationError(
                "replication refused: payload string contains data-URI/base64 (R2)"
            )
        if isinstance(node, dict):
            for v in node.values():
                _walk(v)
        elif isinstance(node, list):
            for v in node:
                _walk(v)

    _walk(obj)


def _assert_no_asset_registry_payload(payload_json: str) -> None:
    # Be explicit: any payload that contains asset_registry_json key is refused
    if "asset_registry_json" in payload_json:
        raise TursoReplicationError(
            "replication refused: asset_registry_json must not replicate (R2)"
        )


def assert_replication_allowlist() -> frozenset[str]:
    """Return the exhaustive allowlist (for tests)."""
    return ALL_REPLICATED_COLUMNS


# ---------------------------------------------------------------------------
# Transport protocol
# ---------------------------------------------------------------------------


class TursoTransport(Protocol):
    """Narrow batched statement + query seam."""

    def execute_batch(self, statements: list[tuple[str, tuple[Any, ...]]]) -> None:
        """Execute statements as ONE remote transaction (all-or-nothing)."""

    def query(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        """Run a read query and return rows as dicts."""

    def close(self) -> None: ...


# ---------------------------------------------------------------------------
# Fake transport — in-memory, batch-atomic
# ---------------------------------------------------------------------------


class FakeTursoTransport:
    """Scripted in-memory fake for tests; emulates atomic batch semantics."""

    def __init__(self) -> None:
        self.documents: dict[str, dict[str, Any]] = {}
        self.events: dict[str, dict[str, Any]] = {}
        # DDL tracking for replica schema tests — pre-seed replica tables so
        # legacy success paths (Fake without explicit CREATE) stay green while
        # still enforcing DML-before-DDL for other tables / cleared state.
        self.tables: set[str] = {"documents", "events"}
        self.indexes: set[str] = set()
        # timeline_id -> list of events sorted by seq
        self._fail_next_batch = False
        self._fail_message = "injected mid-batch failure"

    def inject_next_batch_failure(self, message: str = "injected mid-batch failure") -> None:
        self._fail_next_batch = True
        self._fail_message = message

    def execute_batch(self, statements: list[tuple[str, tuple[Any, ...]]]) -> None:
        if self._fail_next_batch:
            self._fail_next_batch = False
            raise TursoError(self._fail_message)
        # Sequential interpreter over staged views — each statement sees
        # exactly the effects of prior same-batch statements; ANY raise
        # leaves live state byte-unchanged (Y2); cross-timeline batches
        # roll back ALL staged effects together.
        staged_documents: dict[str, dict[str, Any]] = {k: dict(v) for k, v in self.documents.items()}  # noqa: E501
        staged_events: dict[str, dict[str, Any]] = {k: dict(v) for k, v in self.events.items()}
        staged_tables: set[str] = set(self.tables)
        staged_indexes: set[str] = set(self.indexes)
        for sql, params in statements:
            s = sql.strip().lower()
            if s.startswith("create table"):
                try:
                    rest = sql.strip().split(None, 3)[2]
                    tbl = rest.split("(")[0].strip().strip('"').strip("'")
                    tbl = tbl.split()[0]
                    if tbl.lower() == "if":
                        parts = sql.strip().split()
                        low = [p.lower() for p in parts]
                        if "exists" in low:
                            idx = low.index("exists")
                            tbl = parts[idx + 1].split("(")[0]
                    staged_tables.add(tbl.lower())
                except Exception:
                    staged_tables.add("unknown")
                continue
            if s.startswith("create index") or s.startswith("create unique index"):
                try:
                    parts = sql.strip().split()
                    low = [p.lower() for p in parts]
                    idx_pos = low.index("index")
                    idx_name = parts[idx_pos + 1]
                    staged_indexes.add(idx_name.lower())
                except Exception:
                    staged_indexes.add("unknown")
                continue
            if s.startswith("insert") and "into documents" in s:
                if "documents" not in staged_tables:
                    raise TursoError("no such table: documents (CREATE TABLE required before INSERT)")  # noqa: E501
                cols = list(DOCUMENT_REPLICA_COLUMNS)
                has_where = "where documents.version" in s
                expected: int | None = None
                data_params = params
                if has_where:
                    if len(params) != len(cols) + 1:
                        raise TursoError("document CAS expects version param")
                    expected = int(params[-1])
                    data_params = params[:-1]
                if len(data_params) != len(cols):
                    row = {"timeline_id": data_params[0]}
                    for i, v in enumerate(data_params):
                        if i < len(cols):
                            row[cols[i]] = v
                else:
                    row = {c: v for c, v in zip(cols, data_params)}
                doc_json = str(row.get("document_json", ""))
                if _contains_blob_payload(doc_json) or "asset_registry_json" in doc_json:
                    raise TursoReplicationError(
                        "replication refused: document contains blob/asset_registry (R2)"
                    )
                tid = str(row["timeline_id"])
                existing = staged_documents.get(tid)
                if existing is not None and expected is not None:
                    try:
                        cur_v = int(existing.get("version", 0))
                    except Exception:
                        cur_v = None
                    if cur_v != expected:
                        # CAS miss — skip this document update; guarded events will see pre-update state  # noqa: E501
                        continue
                    existing["name"] = row["name"]
                    existing["document_json"] = row["document_json"]
                    existing["version"] = row["version"]
                    existing["updated_at"] = row["updated_at"]
                elif existing is not None:
                    # Fidelity: plain INSERT (no ON CONFLICT) must raise UNIQUE;
                    # ON CONFLICT upsert is allowed to overwrite.
                    is_upsert = "on conflict" in s
                    if is_upsert:
                        existing["name"] = row["name"]
                        existing["document_json"] = row["document_json"]
                        existing["version"] = row["version"]
                        existing["updated_at"] = row["updated_at"]
                    else:
                        raise TursoError(f"UNIQUE constraint failed: documents.timeline_id={tid!r} (plain insert violates PK)")  # noqa: E501
                else:
                    # New document — CAS expected is ignored (no conflict)
                    staged_documents[tid] = dict(row)
                continue
            elif s.startswith("insert") and "into events" in s:
                if "events" not in staged_tables:
                    raise TursoError("no such table: events (CREATE TABLE required before INSERT)")
                is_guarded = "where exists" in s and "select" in s
                guard_info: tuple[str, int, str, str] | None = None
                cols = list(EVENT_REPLICA_COLUMNS)
                if is_guarded:
                    expected_param_len = len(cols) + 4
                    if len(params) != expected_param_len:
                        raise TursoError(f"guarded event insert expects {expected_param_len} params, got {len(params)}")  # noqa: E501
                    event_params = params[: len(cols)]
                    guard_tid = str(params[len(cols)])
                    guard_version = int(params[len(cols) + 1])
                    guard_doc_json = str(params[len(cols) + 2])
                    guard_name = str(params[len(cols) + 3])
                    guard_info = (guard_tid, guard_version, guard_doc_json, guard_name)
                    row = {c: v for c, v in zip(cols, event_params)}
                else:
                    if len(params) != len(cols):
                        row = {"event_id": params[0]}
                        for i, v in enumerate(params):
                            if i < len(cols):
                                row[cols[i]] = v
                    else:
                        row = {c: v for c, v in zip(cols, params)}
                payload = str(row.get("payload_json", ""))
                _assert_no_blob_in_payload_json(payload)
                _assert_no_asset_registry_payload(payload)
                eid = str(row["event_id"])
                if eid in staged_events:
                    raise TursoError(f"duplicate event_id: {eid!r} violates PK")
                # F2: FK fidelity — plain inserts must reference existing document
                if guard_info is None:
                    evt_tid = str(row.get("timeline_id", ""))
                    if evt_tid not in staged_documents:
                        raise TursoError(f"FOREIGN KEY constraint failed: events.timeline_id={evt_tid!r} references missing documents.timeline_id")  # noqa: E501
                if guard_info is not None:
                    guard_tid, guard_version, guard_doc_json, guard_name = guard_info
                    doc = staged_documents.get(guard_tid)
                    if doc is None:
                        continue
                    try:
                        doc_v = int(doc.get("version", 0))
                    except Exception:
                        doc_v = None  # noqa: E501
                    if doc_v != guard_version or str(doc.get("document_json", "")) != guard_doc_json or str(doc.get("name", "")) != guard_name:  # noqa: E501
                        continue
                staged_events[eid] = row
                continue
            else:
                # Generic DML-before-DDL check: extract target table for INSERT
                # and raise if not pre-existing nor CREATEd earlier in this batch.
                if s.startswith("insert"):
                    try:
                        # naive table extraction after INTO
                        after_into = s.split("into", 1)[1].strip()
                        tbl = after_into.split()[0].strip('"').strip("'").split("(")[0]
                        if tbl.lower() not in staged_tables:
                            raise TursoError(f"no such table: {tbl} (CREATE TABLE required before INSERT)")  # noqa: E501
                    except TursoError:
                        raise
                    except Exception:
                        pass
                raise TursoError(f"fake transport does not support statement: {sql[:80]!r}")
        # All validated — publish atomically.
        self.tables = staged_tables
        self.indexes = staged_indexes
        self.documents = staged_documents
        self.events = staged_events

    def query(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        s = sql.strip().lower()
        if "sqlite_master" in s:
            if "type='table'" in s or 'type="table"' in s:
                return [{"name": t} for t in sorted(self.tables)]
            if "type='index'" in s or 'type="index"' in s:
                return [{"name": i} for i in sorted(self.indexes)]
            rows: list[dict[str, Any]] = []
            for t in sorted(self.tables):
                rows.append({"type": "table", "name": t})
            for i in sorted(self.indexes):
                rows.append({"type": "index", "name": i})
            return rows
        if "select count" in s and "from events" in s:
            tid = params[0] if params else None
            if tid:
                cnt = sum(1 for v in self.events.values() if str(v.get("timeline_id")) == str(tid))
            else:
                cnt = len(self.events)
            return [{"cnt": cnt}]
        if "from documents" in s and "where timeline_id" in s:
            tid = params[0] if params else None
            row = self.documents.get(str(tid)) if tid else None
            return [dict(row)] if row else []
        if "from documents" in s:
            # only support bare documents scan; other shapes are unsupported
            if "select *" not in s and "select" in s:
                raise NotImplementedError(f"fake query unsupported: {sql[:80]!r}")
            return [dict(v) for v in self.documents.values()]
        if "from events" in s:
            if "where timeline_id" in s:
                tid = params[0] if params else None
                rows = [v for v in self.events.values() if str(v.get("timeline_id")) == str(tid)]
                if "order by" in s:
                    # honor ORDER BY <col> DESC/ASC  + LIMIT
                    order_desc = "desc" in s
                    # extract column name after order by
                    try:
                        order_part = s.split("order by", 1)[1].split("limit")[0]
                        col = order_part.strip().split()[0]
                    except Exception:
                        col = "seq"
                    try:
                        rows.sort(key=lambda r: (r.get(col) if r.get(col) is not None else 0), reverse=order_desc)  # noqa: E501
                    except Exception:
                        rows.sort(key=lambda r: int(r.get("seq", 0)), reverse=order_desc)
                    if "limit" in s:
                        try:
                            lim = int(s.split("limit", 1)[1].strip().split()[0])
                            rows = rows[:lim]
                        except Exception:
                            pass
                    else:
                        rows.sort(key=lambda r: int(r.get("seq", 0)), reverse=order_desc)
                else:
                    rows.sort(key=lambda r: int(r.get("seq", 0)))
                return [dict(r) for r in rows]
            # bare events scan requires explicit handling; honor order/limit if present
            if "order by" in s or "where" in s:
                raise NotImplementedError(f"fake query unsupported: {sql[:80]!r}")
            rows = list(self.events.values())
            rows.sort(key=lambda r: (str(r.get("timeline_id")), int(r.get("seq", 0))))
            return [dict(r) for r in rows]
        raise NotImplementedError(f"fake query unsupported: {sql[:80]!r}")
    def close(self) -> None:
        pass


# ---------------------------------------------------------------------------
# libsql HTTP transport — stubbed deployment path (DC4)
# ---------------------------------------------------------------------------


class LibSqlHttpTransport:
    """Lazy libsql-HTTP backed transport.

    Import is deferred to use time; absence raises TursoConfigError with
    an actionable message (driver not installed, env not set).
    """

    def __init__(
        self,
        database_url: str | None = None,
        auth_token: str | None = None,
    ) -> None:
        url = (
            database_url if database_url is not None else os.environ.get(TURSO_ENV_URL, "")
        ).strip()
        token = (
            auth_token if auth_token is not None else os.environ.get(TURSO_ENV_TOKEN, "")
        ).strip()
        if not url:
            raise TursoConfigError(
                f"{TURSO_ENV_URL} is not set — set it to your Turso libsql URL "
                f"(e.g. libsql://your-db-xxx.turso.io) and {TURSO_ENV_TOKEN}"
            )
        if not token:
            raise TursoConfigError(
                f"{TURSO_ENV_TOKEN} is not set — set it to your Turso auth token"
            )
        self._url = url
        self._token = token
        self._client: Any | None = None

    def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        libsql_mod = None
        last_exc: Exception | None = None
        for mod_name in ("libsql", "libsql_experimental"):
            try:
                libsql_mod = __import__(mod_name)
                break
            except ImportError as exc:
                last_exc = exc
                continue
        if libsql_mod is None:
            raise TursoConfigError(
                "libsql driver is not installed — install with: pip install libsql-experimental "  # noqa: E501
                "(provides libsql_experimental; libsql also accepted) and set TURSO_DATABASE_URL / TURSO_AUTH_TOKEN"  # noqa: E501
            ) from last_exc
        # lazy connect; both libsql and libsql_experimental expose libsql.connect(url, authToken=token)  # noqa: E501
        try:
            # try libsql.connect signature
            self._client = libsql_mod.connect(database=self._url, auth_token=self._token)  # type: ignore[attr-defined]  # noqa: E501
        except TypeError:
            try:
                self._client = libsql_mod.connect(self._url, authToken=self._token)  # type: ignore[attr-defined]  # noqa: E501
            except Exception as exc:
                raise TursoConfigError(f"failed to connect to Turso at {self._url}: {exc}") from exc
        except Exception as exc:
            raise TursoConfigError(f"failed to connect to Turso at {self._url}: {exc}") from exc
        return self._client

    def execute_batch(self, statements: list[tuple[str, tuple[Any, ...]]]) -> None:
        client = self._ensure_client()
        # libsql batch via transaction
        try:
            # prefer client.execute_batch if available
            if hasattr(client, "execute_batch"):
                client.execute_batch(statements)  # type: ignore[attr-defined]
                return
            # fallback: manual transaction
            cur = client.cursor()
            cur.execute("BEGIN")
            try:
                for sql, params in statements:
                    cur.execute(sql, params)
                cur.execute("COMMIT")
            except Exception:
                try:
                    cur.execute("ROLLBACK")
                except Exception:
                    pass
                raise
        except TursoConfigError:
            raise
        except Exception as exc:
            raise TursoError(str(exc)) from exc

    def query(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        client = self._ensure_client()
        try:
            cur = client.cursor()
            cur.execute(sql, params)
            cols = [d[0] for d in cur.description] if cur.description else []
            rows = cur.fetchall()
            return [dict(zip(cols, row)) for row in rows]
        except TursoConfigError:
            raise
        except Exception as exc:
            raise TursoError(str(exc)) from exc

    def close(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass  # best-effort close: no diagnostic needed, connection teardown is idempotent
            self._client = None

# ---------------------------------------------------------------------------
# Replica client — NOT an EventLogBackend (W2)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TursoDocumentRow:
    timeline_id: str
    project_id: str
    event_stream_id: str
    name: str
    document_json: str
    version: int
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class TursoEventRow:
    event_id: str
    timeline_id: str
    project_id: str
    stream_id: str
    seq: int
    kind: str
    payload_json: str
    actor_kind: str
    actor_id: str
    txn_id: str
    idempotency_key: str
    created_at: str


class TursoReplicaClient:
    """Push/fetch client over a TursoTransport.

    Serialization maps kernel rows → W1 schema columns using the explicit
    allowlist; blob detection fails closed (R2).
    """

    def __init__(self, transport: TursoTransport) -> None:
        self._transport = transport

    # -- helpers -------------------------------------------------------------
    def _document_upsert_sql(self, expected_remote_version: int | None = None) -> str:
        cols = ", ".join(DOCUMENT_REPLICA_COLUMNS)
        placeholders = ", ".join("?" for _ in DOCUMENT_REPLICA_COLUMNS)
        base = (
            f"INSERT INTO documents ({cols}) VALUES ({placeholders}) "
            "ON CONFLICT(timeline_id) DO UPDATE SET "
            "name=excluded.name, document_json=excluded.document_json, "
            "version=excluded.version, updated_at=excluded.updated_at"
        )
        if expected_remote_version is not None:
            base += " WHERE documents.version = ?"
        return base

    def _event_upsert_sql(self) -> str:
        cols = ", ".join(EVENT_REPLICA_COLUMNS)
        placeholders = ", ".join("?" for _ in EVENT_REPLICA_COLUMNS)
        return f"INSERT INTO events ({cols}) VALUES ({placeholders})"

    def _validate_document(self, row: TursoDocumentRow) -> None:
        if row.document_json and (
            "asset_registry_json" in row.document_json or _contains_blob_payload(row.document_json)
        ):
            raise TursoReplicationError(
                "replication refused: document contains blob/asset_registry (R2)"
            )
        if row.version < 0:
            raise TursoReplicationError(f"document version must be >=0, got {row.version}")

    def _validate_event(self, row: TursoEventRow) -> None:
        _assert_no_blob_in_payload_json(row.payload_json)
        _assert_no_asset_registry_payload(row.payload_json)

    def push_timeline_updates(
        self,
        document: TursoDocumentRow | None,
        events: Sequence[TursoEventRow],
        *,
        require_document: bool = True,
        expected_remote_version: int | None = None,
    ) -> None:
        """Apply document row + event batch as ONE remote unit.

        If ``require_document`` is False and document is None, only events
        are pushed (amendment 3b: event-only transfer when document unchanged).
        If events is empty and document is not None, only document is pushed.
        The transport's execute_batch must be atomic (all-or-nothing).
        When ``expected_remote_version`` is not None, the document upsert
        becomes CAS-guarded (WHERE version = expected); zero rows ⇒ race error.
        Event collisions are probed inside the same logical transaction:
        identical replay is idempotent, divergent payload ⇒ typed collision.
        """
        if document is None and require_document and len(events) == 0:
            raise TursoReplicationError("push_timeline_updates: nothing to push")
        # --- R1: probe event collisions before building statements (same txn view) ---
        # T1: exact-replay candidates are filtered from emission entirely (idempotent skip).
        events_to_push: list[TursoEventRow] = list(events)  # default; may be filtered below
        if events:
            # Build lookup maps from remote state via transport queries.
            # Use the transport's query for real sqlite semantics; fake mirrors it.
            # Collect all remote events for involved timeline_ids to check all three keys.
            # Events all share document timeline_id when document present, else first event's.
            probe_tids = set()
            if document is not None:
                probe_tids.add(document.timeline_id)
            for ev in events:
                probe_tids.add(ev.timeline_id)
            existing_by_id: dict[str, dict[str, Any]] = {}
            existing_by_seq: dict[tuple[str, int], dict[str, Any]] = {}
            existing_by_ik: dict[tuple[str, str], dict[str, Any]] = {}
            for tid in probe_tids:
                try:
                    rows = self._transport.query(
                        "SELECT * FROM events WHERE timeline_id = ?",
                        (tid,),
                    )
                except Exception:
                    rows = []
                for r in rows:
                    eid = str(r.get("event_id", ""))
                    if eid:
                        existing_by_id[eid] = r
                    try:
                        seq = int(r.get("seq", 0))
                    except Exception:
                        seq = r.get("seq")
                    existing_by_seq[(str(r.get("timeline_id")), seq)] = r
                    ik = str(r.get("idempotency_key", ""))
                    if ik:
                        existing_by_ik[(str(r.get("timeline_id")), ik)] = r
            # Also detect duplicate event_id within the batch itself (real PK semantics)
            seen_batch_ids: set[str] = set()
            filtered: list[TursoEventRow] = []
            for ev in events:
                if ev.event_id in seen_batch_ids:
                    raise TursoEventCollisionError(
                        f"event collision key=event_id duplicate within batch event_id={ev.event_id!r}"  # noqa: E501
                    )
                seen_batch_ids.add(ev.event_id)
                # Check each key against existing remote rows
                import hashlib

                def _h(payload: str) -> str:
                    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]

                candidate_checks = [
                    ("event_id", existing_by_id.get(ev.event_id)),
                    (
                        "timeline_seq",
                        existing_by_seq.get((ev.timeline_id, ev.seq)),
                    ),
                    (
                        "timeline_idempotency_key",
                        existing_by_ik.get((ev.timeline_id, ev.idempotency_key)),
                    ),
                ]
                is_exact_replay = False
                for key_kind, existing in candidate_checks:
                    if existing is None:
                        continue
                    # Existing row found — compare identity + payload + kind + timeline identity
                    existing_payload = str(existing.get("payload_json", ""))
                    existing_event_id = str(existing.get("event_id", ""))
                    existing_seq = existing.get("seq")
                    existing_ik = str(existing.get("idempotency_key", ""))
                    existing_kind = str(existing.get("kind", ""))
                    existing_tid = str(existing.get("timeline_id", ""))
                    existing_pid = str(existing.get("project_id", ""))
                    existing_sid = str(existing.get("stream_id", ""))
                    payload_equal = existing_payload == ev.payload_json
                    identity_equal = (
                        existing_event_id == ev.event_id
                        and existing_seq == ev.seq
                        and existing_ik == ev.idempotency_key
                    )
                    kind_equal = existing_kind == ev.kind
                    timeline_identity_equal = (
                        existing_tid == ev.timeline_id
                        and existing_pid == ev.project_id
                        and existing_sid == ev.stream_id
                    )
                    if payload_equal and identity_equal and kind_equal and timeline_identity_equal:
                        is_exact_replay = True
                        continue  # noqa: E501 — exact replay benign for this key
                    raise TursoEventCollisionError(
                        f"event collision key={key_kind} "  # noqa: E501
                        f"candidate event_id={ev.event_id!r} seq={ev.seq} idempotency_key={ev.idempotency_key!r} kind={ev.kind!r} "  # noqa: E501
                        f"existing event_id={existing_event_id!r} seq={existing_seq!r} kind={existing_kind!r} "  # noqa: E501
                        f"candidate_hash={_h(ev.payload_json)} existing_hash={_h(existing_payload)}"  # noqa: E501
                    )
                if is_exact_replay:
                    # T1: skip emission entirely; do not add to maps or push list
                    continue
                existing_by_id[ev.event_id] = {
                    "event_id": ev.event_id,
                    "timeline_id": ev.timeline_id,
                    "seq": ev.seq,
                    "payload_json": ev.payload_json,
                    "idempotency_key": ev.idempotency_key,
                    "kind": ev.kind,
                    "project_id": ev.project_id,
                    "stream_id": ev.stream_id,
                }
                existing_by_seq[(ev.timeline_id, ev.seq)] = existing_by_id[ev.event_id]
                existing_by_ik[(ev.timeline_id, ev.idempotency_key)] = existing_by_id[ev.event_id]
                filtered.append(ev)
            events_to_push = filtered
        statements: list[tuple[str, tuple[Any, ...]]] = []
        if document is not None:
            self._validate_document(document)
            sql = self._document_upsert_sql(expected_remote_version)
            params_list: list[Any] = [
                document.timeline_id,
                document.project_id,
                document.event_stream_id,
                document.name,
                document.document_json,
                document.version,
                document.created_at,
                document.updated_at,
            ]
            if expected_remote_version is not None:
                params_list.append(expected_remote_version)
            params = tuple(params_list)
            statements.append((sql, params))
        elif require_document:
            raise TursoReplicationError(
                "push_timeline_updates: document is required when require_document=True"
            )
        for ev in events_to_push:
            self._validate_event(ev)
            if document is not None and expected_remote_version is not None:
                # Guarded conditional insert: event only lands if document CAS succeeded
                # to the intended CONTENT (version + document_json + name), not just version number.
                # Shape (a) same-version-different-content would otherwise pass a version-only check.  # noqa: E501
                cols = ", ".join(EVENT_REPLICA_COLUMNS)
                placeholders = ", ".join("?" for _ in EVENT_REPLICA_COLUMNS)
                sql = (
                    f"INSERT INTO events ({cols}) SELECT {placeholders} "
                    "WHERE EXISTS (SELECT 1 FROM documents WHERE timeline_id = ? "
                    "AND version = ? AND document_json = ? AND name = ?)"
                )
                base_params = (
                    ev.event_id,
                    ev.timeline_id,
                    ev.project_id,
                    ev.stream_id,
                    ev.seq,
                    ev.kind,
                    ev.payload_json,
                    ev.actor_kind,
                    ev.actor_id,
                    ev.txn_id,
                    ev.idempotency_key,
                    ev.created_at,
                )
                guard_params = (
                    document.timeline_id,
                    document.version,
                    document.document_json,
                    document.name,
                )
                params = base_params + guard_params
            else:
                sql = self._event_upsert_sql()
                params = (
                    ev.event_id,
                    ev.timeline_id,
                    ev.project_id,
                    ev.stream_id,
                    ev.seq,
                    ev.kind,
                    ev.payload_json,
                    ev.actor_kind,
                    ev.actor_id,
                    ev.txn_id,
                    ev.idempotency_key,
                    ev.created_at,
                )
            statements.append((sql, params))
        if not statements:
            return
        self._transport.execute_batch(statements)
        if document is not None and expected_remote_version is not None:
            # Belt-and-braces: guard ensures events only land if document reached intended
            # CONTENT, but we still verify post-batch that the document row matches
            # intended version AND bytes (document_json/name). Version-only equality
            # would miss shape (a) where theirs-v2 and ours-v2 are numerically equal.
            try:
                rows = self._transport.query(
                    "SELECT * FROM documents WHERE timeline_id = ?",
                    (document.timeline_id,),
                )
            except Exception:
                rows = []
            if rows:
                cur_version = rows[0].get("version")
                cur_json = str(rows[0].get("document_json", ""))
                cur_name = str(rows[0].get("name", ""))
                try:
                    cur_v = int(cur_version)  # type: ignore[arg-type]
                except Exception:
                    cur_v = None
                if cur_v != document.version or cur_json != document.document_json or cur_name != document.name:  # noqa: E501
                    raise TursoVersionRaceError(
                        f"document CAS failed timeline_id={document.timeline_id!r} "
                        f"expected_remote_version={expected_remote_version} "
                        f"attempted_version={document.version} remote_version={cur_version!r} "
                        f"content_mismatch={cur_json != document.document_json or cur_name != document.name}"  # noqa: E501
                    )
            else:
                raise TursoVersionRaceError(
                    f"document CAS failed (no row after upsert) timeline_id={document.timeline_id!r} "  # noqa: E501
                    f"expected_remote_version={expected_remote_version}"
                )

    def fetch_remote_head(self, timeline_id: str) -> dict[str, Any] | None:
        rows = self._transport.query(
            "SELECT * FROM documents WHERE timeline_id = ?",
            (timeline_id,),
        )
        if not rows:
            return None
        doc = rows[0]
        ev_rows = self._transport.query(
            "SELECT event_id, seq, payload_json FROM events "
            "WHERE timeline_id = ? ORDER BY seq DESC LIMIT 1",
            (timeline_id,),
        )
        last_event_id = ev_rows[0].get("event_id") if ev_rows else None
        last_hash = None
        if ev_rows:
            payload = ev_rows[0].get("payload_json")
            if payload:
                try:
                    obj = json.loads(str(payload))
                    integ = obj.get("_integrity") if isinstance(obj, dict) else None
                    if isinstance(integ, dict) and integ.get("event_hash"):
                        last_hash = str(integ.get("event_hash"))
                except Exception:
                    last_hash = None
            if last_hash is None:
                # most-recent payload malformed — scan for most recent valid hash (Q9: fork expects hash from good row)  # noqa: E501
                try:
                    all_rows = self._transport.query(
                        "SELECT event_id, seq, payload_json FROM events WHERE timeline_id = ? ORDER BY seq DESC",  # noqa: E501
                        (timeline_id,),
                    )
                except Exception:
                    all_rows = []
                for cand in all_rows:
                    p = cand.get("payload_json")
                    if not p:
                        continue
                    try:
                        o = json.loads(str(p))
                        integ = o.get("_integrity") if isinstance(o, dict) else None
                        if isinstance(integ, dict) and integ.get("event_hash"):
                            last_hash = str(integ.get("event_hash"))
                            break
                    except Exception:
                        continue
        cnt_rows = self._transport.query(
            "SELECT COUNT(*) as cnt FROM events WHERE timeline_id = ?",
            (timeline_id,),
        )
        cnt = int(cnt_rows[0].get("cnt", 0)) if cnt_rows else 0
        version = int(doc.get("version", 0))
        return {
            "timeline_id": timeline_id,
            "document": doc,
            "version": version,
            "event_count": cnt,
            "last_event_id": last_event_id,
            "last_hash": last_hash,
        }
    def fetch_remote_events(
        self,
        timeline_id: str,
        *,
        after: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        rows = self._transport.query(
            "SELECT * FROM events WHERE timeline_id = ? ORDER BY seq ASC",
            (timeline_id,),
        )
        if after is not None:
            idx = next((i for i, r in enumerate(rows) if str(r.get("event_id")) == after), None)
            if idx is None:
                return []
            rows = rows[idx + 1 :]
        if limit is not None:
            rows = rows[:limit]
        return rows

    def close(self) -> None:
        try:
            self._transport.close()
        except Exception:
            pass

# ---------------------------------------------------------------------------
# SQL splitter + replica schema application (Q5)
# ---------------------------------------------------------------------------


def split_sql_statements(sql_text: str) -> list[str]:
    """Split *sql_text* into individual statements (quote/comment-aware).

    Handles ``--`` line comments and string literals with embedded semicolons
    (single and double quoted). ``/* … */`` block comments are also skipped.
    Trailing whitespace and empty statements are dropped.
    """
    statements: list[str] = []
    buf: list[str] = []
    i = 0
    n = len(sql_text)
    in_single = False
    in_double = False
    in_line_comment = False
    in_block_comment = False
    while i < n:
        ch = sql_text[i]
        nxt = sql_text[i + 1] if i + 1 < n else ""
        if in_line_comment:
            if ch == "\n":
                in_line_comment = False
                buf.append(ch)
            # otherwise skip comment chars
            i += 1
            continue
        if in_block_comment:
            if ch == "*" and nxt == "/":
                in_block_comment = False
                i += 2
            else:
                i += 1
            continue
        if in_single:
            buf.append(ch)
            if ch == "'":
                if nxt == "'":
                    # escaped single quote '' inside string
                    buf.append(nxt)
                    i += 2
                    continue
                else:
                    in_single = False
            i += 1
            continue
        if in_double:
            buf.append(ch)
            if ch == '"':
                if nxt == '"':
                    buf.append(nxt)
                    i += 2
                    continue
                else:
                    in_double = False
            i += 1
            continue
        # not in string/comment
        if ch == "-" and nxt == "-":
            in_line_comment = True
            i += 2
            continue
        if ch == "/" and nxt == "*":
            in_block_comment = True
            i += 2
            continue
        if ch == "'":
            in_single = True
            buf.append(ch)
            i += 1
            continue
        if ch == '"':
            in_double = True
            buf.append(ch)
            i += 1
            continue
        if ch == ";":
            stmt = "".join(buf).strip()
            if stmt:
                statements.append(stmt + ";")
            buf = []
            i += 1
            # skip whitespace after semicolon to avoid empty trailing
            while i < n and sql_text[i].isspace():
                # keep newline for readability? not needed
                i += 1
            # we already consumed whitespace, continue; but need to handle that whitespace may contain comment start  # noqa: E501
            # loop will detect comment
            continue
        buf.append(ch)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        # include trailing statement even without semicolon
        if not tail.endswith(";"):
            tail += ";"
        statements.append(tail)
    return statements


def apply_replica_schema(
    transport_or_replica: Any,
    sql_text: str,
) -> list[str]:
    """Split *sql_text* and apply all statements as one atomic batch.

    Accepts either a :class:`TursoTransport` or :class:`TursoReplicaClient`
    (or any object exposing ``execute_batch`` or ``_transport``).
    Returns the split statements for observability. The batch is all-or-nothing
    via the transport's atomic ``execute_batch``.
    """
    statements = split_sql_statements(sql_text)
    if not statements:
        return []
    # resolve underlying transport
    transport: Any = transport_or_replica
    if hasattr(transport_or_replica, "_transport") and hasattr(transport_or_replica._transport, "execute_batch"):  # noqa: E501
        transport = transport_or_replica._transport  # type: ignore[attr-defined]
    if not hasattr(transport, "execute_batch"):
        raise TursoError("apply_replica_schema: transport missing execute_batch")
    batch: list[tuple[str, tuple[Any, ...]]] = [(stmt, ()) for stmt in statements]
    transport.execute_batch(batch)  # type: ignore[attr-defined]
    return statements
