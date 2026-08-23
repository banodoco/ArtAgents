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

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class TursoError(RuntimeError):
    """Base error for Turso replica operations."""


class TursoConfigError(TursoError):
    """Turso driver/env is missing (typed, actionable)."""


class TursoReplicationError(TursoError):
    """Replication was refused (allowlist / blob guard)."""


class TursoOwnershipError(TursoError):
    """Sync attempted to open a second writer while DB is owned."""


# ---------------------------------------------------------------------------
# R2 allowlist — exhaustive column lists (every replicated column named)
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
        # DDL tracking for replica schema tests
        self.tables: set[str] = set()
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
            # simulate failure BEFORE any writes are applied (atomic rollback)
            raise TursoError(self._fail_message)
        # collect intended mutations without applying
        pending_docs: dict[str, dict[str, Any]] = {}
        pending_events: dict[str, dict[str, Any]] = {}
        pending_tables: set[str] = set()
        pending_indexes: set[str] = set()
        # naive parsing: look at statement prefix to know table
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
                    pending_tables.add(tbl.lower())
                except Exception:
                    pending_tables.add("unknown")
                continue
            if s.startswith("create index") or s.startswith("create unique index"):
                try:
                    parts = sql.strip().split()
                    low = [p.lower() for p in parts]
                    idx_pos = low.index("index")
                    idx_name = parts[idx_pos + 1]
                    pending_indexes.add(idx_name.lower())
                except Exception:
                    pending_indexes.add("unknown")
                continue
            if s.startswith("insert") and "into documents" in s:
                cols = list(DOCUMENT_REPLICA_COLUMNS)
                if len(params) != len(cols):
                    row = {"timeline_id": params[0]}
                    for i, v in enumerate(params):
                        if i < len(cols):
                            row[cols[i]] = v
                else:
                    row = {c: v for c, v in zip(cols, params)}
                doc_json = str(row.get("document_json", ""))
                if _contains_blob_payload(doc_json) or "asset_registry_json" in doc_json:
                    raise TursoReplicationError(
                        "replication refused: document contains blob/asset_registry (R2)"
                    )
                pending_docs[str(row["timeline_id"])] = row
            elif s.startswith("insert") and "into events" in s:
                cols = list(EVENT_REPLICA_COLUMNS)
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
                pending_events[str(row["event_id"])] = row
            else:
                raise TursoError(f"fake transport does not support statement: {sql[:80]!r}")
        # All statements validated — now apply atomically
        self.tables.update(pending_tables)
        self.indexes.update(pending_indexes)
        self.documents.update(pending_docs)
        # events: upsert with idempotent ignore (event_id UNIQUE)
        for eid, row in pending_events.items():
            if eid in self.events:
                continue
            tid = str(row.get("timeline_id"))
            seq = row.get("seq")
            ik = row.get("idempotency_key")
            dup = False
            for existing in self.events.values():
                if str(existing.get("timeline_id")) == tid:
                    if existing.get("seq") == seq or existing.get("idempotency_key") == ik:
                        dup = True
                        break
            if dup:
                continue
            self.events[eid] = row

    def query(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        s = sql.strip().lower()
        if "sqlite_master" in s:
            # for schema verification: return tables/indexes
            if "type='table'" in s or 'type="table"' in s:
                return [{"name": t} for t in sorted(self.tables)]
            if "type='index'" in s or 'type="index"' in s:
                return [{"name": i} for i in sorted(self.indexes)]
            # generic master query
            rows: list[dict[str, Any]] = []
            for t in sorted(self.tables):
                rows.append({"type": "table", "name": t})
            for i in sorted(self.indexes):
                rows.append({"type": "index", "name": i})
            return rows
        if "from documents" in s and "where timeline_id" in s:
            tid = params[0] if params else None
            row = self.documents.get(str(tid)) if tid else None
            return [dict(row)] if row else []
        if "from documents" in s:
            return [dict(v) for v in self.documents.values()]
        if "from events" in s and "where timeline_id" in s and "order by seq" in s:
            tid = params[0] if params else None
            rows = [v for v in self.events.values() if str(v.get("timeline_id")) == str(tid)]
            rows.sort(key=lambda r: int(r.get("seq", 0)))
            # handle params like (timeline_id, after_seq) or limit
            return [dict(r) for r in rows]
        if "from events" in s and "where timeline_id" in s:
            tid = params[0] if params else None
            rows = [v for v in self.events.values() if str(v.get("timeline_id")) == str(tid)]
            return [dict(r) for r in rows]
        if "from events" in s:
            rows = list(self.events.values())
            rows.sort(key=lambda r: (str(r.get("timeline_id")), int(r.get("seq", 0))))
            return [dict(r) for r in rows]
        if "select count" in s and "from events" in s:
            tid = params[0] if params else None
            if tid:
                cnt = sum(1 for v in self.events.values() if str(v.get("timeline_id")) == str(tid))
            else:
                cnt = len(self.events)
            return [{"cnt": cnt}]
        return []

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
        try:
            import libsql  # type: ignore[import-not-found]
        except Exception as exc:
            raise TursoConfigError(
                "libsql driver is not installed — install with: pip install libsql-experimental "
                "(or libsql) and set TURSO_DATABASE_URL / TURSO_AUTH_TOKEN"
            ) from exc
        # lazy connect; libsql-experimental exposes libsql.connect(url, authToken=token)
        try:
            # try libsql.connect signature
            self._client = libsql.connect(database=self._url, auth_token=self._token)  # type: ignore[attr-defined]
        except TypeError:
            try:
                self._client = libsql.connect(self._url, authToken=self._token)  # type: ignore[attr-defined]
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
                pass
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

    def _document_upsert_sql(self) -> str:
        cols = ", ".join(DOCUMENT_REPLICA_COLUMNS)
        placeholders = ", ".join("?" for _ in DOCUMENT_REPLICA_COLUMNS)
        # SQLite upsert: INSERT OR REPLACE (Turso supports it)
        return f"INSERT OR REPLACE INTO documents ({cols}) VALUES ({placeholders})"

    def _event_upsert_sql(self) -> str:
        cols = ", ".join(EVENT_REPLICA_COLUMNS)
        placeholders = ", ".join("?" for _ in EVENT_REPLICA_COLUMNS)
        return f"INSERT OR IGNORE INTO events ({cols}) VALUES ({placeholders})"

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

    # -- public --------------------------------------------------------------

    def push_timeline_updates(
        self,
        document: TursoDocumentRow | None,
        events: Sequence[TursoEventRow],
        *,
        require_document: bool = True,
    ) -> None:
        """Apply document row + event batch as ONE remote unit.

        If ``require_document`` is False and document is None, only events
        are pushed (amendment 3b: event-only transfer when document unchanged).
        If events is empty and document is not None, only document is pushed.
        The transport's execute_batch must be atomic (all-or-nothing).
        """
        if document is None and require_document and len(events) == 0:
            raise TursoReplicationError("push_timeline_updates: nothing to push")
        statements: list[tuple[str, tuple[Any, ...]]] = []
        if document is not None:
            self._validate_document(document)
            sql = self._document_upsert_sql()
            params = (
                document.timeline_id,
                document.project_id,
                document.event_stream_id,
                document.name,
                document.document_json,
                document.version,
                document.created_at,
                document.updated_at,
            )
            statements.append((sql, params))
        elif require_document:
            raise TursoReplicationError(
                "push_timeline_updates: document is required when require_document=True"
            )
        for ev in events:
            self._validate_event(ev)
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
        last_event_id = ev_rows[0]["event_id"] if ev_rows else None
        last_payload = ev_rows[0]["payload_json"] if ev_rows else None
        last_hash = None
        if last_payload:
            try:
                obj = json.loads(str(last_payload))
                integ = obj.get("_integrity") if isinstance(obj, dict) else None
                if isinstance(integ, dict):
                    last_hash = integ.get("event_hash")
            except Exception:
                last_hash = None
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
