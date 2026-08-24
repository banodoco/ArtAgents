"""HTTP surface for the Astrid local read/write bridge."""

from __future__ import annotations

import hmac
import json
import mimetypes
import os
import re
import secrets
import time
from collections.abc import Mapping
from email.utils import formatdate
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import unquote, urlparse

from astrid.core.integrations.reigh.bridge_service import (
    BridgeConflictError,
    BridgeError,
    BridgeInternalError,
    BridgeInvalidProjectError,
    BridgeInvalidTimelineError,
    BridgeIssue,
    BridgeProjectNotFoundError,
    BridgeSchemaIncompatibleError,
    BridgeTimelineNotFoundError,
    TimelineSaveRequest,
)
from astrid.core.integrations.reigh.local_bridge import (
    resolve_bridge_projects_root,
)
from astrid.core.receipts.canonical import (
    CanonicalizationError,
    canonical_json,
)

if TYPE_CHECKING:
    from astrid.core.repositories.media import (
        MediaNotFoundError,
        MediaRepository,
    )
    from astrid.core.repositories.projects import (
        ProjectRepository,
    )

# SQL and repository imports are deliberately **not** module-level (m4 plan
# step 30): the bridge save route and every product route resolve through
# the constructor-injected service-backed bridge, and the only raw-SQL /
# kernel-repository use left on this server is the read-only asset-serving
# path (m4 plan step 22), which imports them lazily inside the handler
# methods that serve bytes. Importing this module therefore never imports
# SQLite or a repository implementation, and no handler reaches for a
# legacy authority.

_RANGE_RE = re.compile(r"^bytes\s*=\s*(\d*)\s*-\s*(\d*)\s*$")
_RANGELESS_FULL_BODY_LIMIT_BYTES = 64 * 1024 * 1024
_RANGELESS_INITIAL_CHUNK_BYTES = 1024 * 1024
_OPEN_ENDED_RANGE_CHUNK_BYTES = 4 * 1024 * 1024
_DIAGNOSTICS_ENABLED = os.environ.get("ASTRID_BRIDGE_DIAGNOSTICS", "0") != "0"

TRUST_TOKEN_HEADER = "X-Astrid-Request-Token"
"""Non-simple custom header every mutation must carry (doc 27 §4.7.3).

A foreign browser origin cannot send it without passing the strict CORS
preflight, so this one header is both the custom-header control and the
bearer of the per-boot request token."""

_TRUST_TOKEN_FILENAME = "request-token"
_PRIVATE_DIR_MODE = 0o700
_SECRET_FILE_MODE = 0o600



def _route_schema(projects_root: Path) -> dict[str, Any]:
    """Return the machine-readable discovery document for the bridge."""
    database = str(projects_root / ".astrid" / "astrid.sqlite3")
    return {
        "version": 1,
        "projects_root": str(projects_root),
        "exclusive_ownership": {
            "database": database,
            "owner": "astrid serve",
            "until": "shutdown",
            "implication": (
                "This bridge exclusively owns the project database until "
                "shutdown; use the HTTP routes for reads and writes while it runs."
            ),
        },
        "trust": {
            "host": "the bound loopback literal is required on every request",
            "mutation_header": TRUST_TOKEN_HEADER,
            "token_file": ".astrid/request-token",
            "cors_preflight": "OPTIONS is exempt from the mutation token gate",
        },
        "routes": [
            {"method": "GET", "path": "/health"},
            {"method": "GET", "path": "/routes"},
            {"method": "GET", "path": "/projects"},
            {"method": "GET", "path": "/projects/{project}/timelines"},
            {"method": "GET", "path": "/projects/{project}/timelines/{timeline}"},
            {"method": "POST", "path": "/projects/{project}/timelines/{timeline}/save"},
            {
                "method": "GET|HEAD",
                "path": "/projects/{project}/timelines/{timeline}/assets/{registry_key}",
            },
            {"method": "GET", "path": "/projects/{project}/tasks"},
            {"method": "GET", "path": "/projects/{project}/tasks/{task_id}"},
            {"method": "GET", "path": "/projects/{project}/generations"},
            {"method": "GET", "path": "/projects/{project}/generations/{generation_id}"},
            {
                "method": "GET|HEAD",
                "path": "/projects/{project}/media/{media_id}/content",
            },
            {"method": "POST", "path": "/projects/{project}/tasks"},
            {"method": "POST", "path": "/projects/{project}/tasks/{task_id}/cancel"},
            {"method": "POST", "path": "/queue/claim"},
            {
                "method": "POST",
                "path": "/tasks/{task_id}/attempts/{attempt_no}/heartbeat",
            },
            {
                "method": "POST",
                "path": "/tasks/{task_id}/attempts/{attempt_no}/complete",
            },
            {
                "method": "POST",
                "path": "/tasks/{task_id}/attempts/{attempt_no}/fail",
            },
        ],
        "save": {
            "method": "POST",
            "path": "/projects/{project}/timelines/{timeline}/save",
            "request": {
                "config": "object",
                "registry": "object",
                "expected_version": "integer",
            },
            "response_version_field": "config_version",
        },
        "asset": {
            "methods": ["GET", "HEAD"],
            "path": "/projects/{project}/timelines/{timeline}/assets/{registry_key}",
            "registry_path": "registry.assets.{registry_key}",
            "key_semantics": (
                "registry_key is the key under registry.assets; it is not "
                "the entry's media_id"
            ),
            "range": "single HTTP byte range supported",
        },
    }


def _classify_persisted_registry_locator(locator: str) -> str:
    """Classify a persisted-registry locator: ``http``, ``unsafe``, ``local``.

    A locator is a path reference, never media identity (contract §9):
    ``http``/``https`` values are HTTP-only, and any absolute or
    ``..``-traversing path is unsafe and is never served from disk.
    """
    if locator.startswith("http://") or locator.startswith("https://"):
        return "http"
    candidate = Path(locator)
    if candidate.is_absolute() or any(part == ".." for part in candidate.parts):
        return "unsafe"
    return "local"


class LocalBridgeHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    # Constructor-injected bridge authority (m4 plan step 21, task T22):
    # the repository bridge, its single writer, and the resolved database
    # path are mandatory constructor inputs — the class has no
    # post-construction authority assignment path — and may never be
    # reassigned while the server is serving. Assigning any of them after
    # ``serve_forever`` has started would create a second write authority,
    # so it is rejected at runtime.
    _BRIDGE_AUTHORITY_ATTRIBUTES = frozenset(
        {"bridge", "bridge_writer", "bridge_database_path", "task_bridge"}
    )

    def __init__(
        self,
        server_address: tuple[str, int],
        RequestHandlerClass: type[BaseHTTPRequestHandler],
        *,
        bridge: Any | None,
        bridge_writer: Any | None,
        bridge_database_path: str | Path | None,
    ) -> None:
        """Bind the server and install the bridge authority at construction.

        The repository bridge, its single writer, and the resolved
        database path are **mandatory constructor inputs** (m4 plan step
        21, task T22): the class has no post-construction authority
        assignment path, and the runtime guard below rejects any
        reassignment while the server is serving. An explicit ``None``
        bridge/writer is the deliberate fail-closed configuration used by
        the frozen bridge tests (every read route answers the typed
        ``500 internal`` envelope).
        """
        super().__init__(server_address, RequestHandlerClass)
        self._serving = False
        self.bridge = bridge
        self.bridge_writer = bridge_writer
        self.bridge_database_path = bridge_database_path

    def __setattr__(self, name: str, value: Any) -> None:
        if (
            name in self._BRIDGE_AUTHORITY_ATTRIBUTES
            and getattr(self, "_serving", False)
        ):
            raise AttributeError(
                f"{name!r} is constructor-injected on the bridge server and "
                "cannot be reassigned while the server is serving"
            )
        super().__setattr__(name, value)

    def serve_forever(self, poll_interval: float = 0.5) -> None:
        self._serving = True
        try:
            super().serve_forever(poll_interval)
        finally:
            self._serving = False


def _enforce_private_directory_modes(projects_root: Path) -> None:
    """Best-effort ``0700`` on the managed data directories (doc 27 §4.7.4).

    Application, SQLite, managed-media, and quarantine directories are
    private to the owning user. Missing directories are skipped (they are
    created by the composition root or first use); failures never block
    serving — this is defense in depth, not an authority.
    """
    managed_root = projects_root / ".astrid"
    candidates = (
        projects_root,
        managed_root,
        managed_root / "media",
        managed_root / "media" / ".staging",
    )
    for directory in candidates:
        try:
            if directory.is_dir():
                os.chmod(directory, _PRIVATE_DIR_MODE)
        except OSError:
            continue


def mint_boot_request_token(projects_root: str | Path) -> str:
    """Mint one per-boot request token and deliver it out of band.

    The token is a local request capability (doc 27 §4.7): it is required
    on every mutation and executor-only route, and it is delivered out of
    band through a mode-``0600`` file under the managed root so the app
    and the same-host worker can read it without any HTTP surface.
    """
    token = secrets.token_urlsafe(32)
    managed_root = Path(projects_root) / ".astrid"
    try:
        managed_root.mkdir(parents=True, exist_ok=True)
        os.chmod(managed_root, _PRIVATE_DIR_MODE)
        token_path = managed_root / _TRUST_TOKEN_FILENAME
        token_path.write_text(token, encoding="utf-8")
        os.chmod(token_path, _SECRET_FILE_MODE)
    except OSError:
        # A read-only root cannot host the out-of-band file; the in-memory
        # token still guards every mutation for this process.
        pass
    return token


def create_local_bridge_server(
    *,
    projects_root: str | Path | None = None,
    host: str = "127.0.0.1",
    port: int = 0,
    bridge: Any | None = None,
    writer: Any | None = None,
    database_path: str | Path | None = None,
    task_bridge: Any | None = None,
    request_token: str | None = None,
) -> ThreadingHTTPServer:
    """Create a bridge HTTP server bound to the requested host/port.

    The supported composition root (``astrid.core.gateway.dispatch``,
    ``_dispatch_serve``) injects the repository-backed bridge, its single
    writer, and the resolved database path **through the server
    constructor** (m4 plan step 21): this factory forwards them to
    :class:`LocalBridgeHTTPServer` and never assigns ``server.bridge``
    after construction, so the HTTP server never gains a second authority.
    The *bridge*/*writer*/*database_path* parameters default to ``None``
    only for the frozen bridge-test fixture pattern (``running_server``),
    which exercises the deliberate fail-closed configuration: every read
    route — including asset serving (m4 plan step 22 removed the legacy
    sidecar/FSA asset fallback) — answers the typed ``500 internal``
    envelope.

    Local trust posture (build spec doc 27 §4.7): when *request_token*
    is not supplied, a fresh per-boot token is minted at serve boot,
    delivered out of band via ``<root>/.astrid/request-token``, and
    required on every mutation; ``Host`` is validated against the bound
    loopback literal on every request. The task/executor routes answer
    only when *task_bridge* is composed; without it they fail closed with
    the typed ``500 internal`` envelope.
    """
    resolved_root = resolve_bridge_projects_root(projects_root)
    resolved_token = (
        request_token
        if request_token is not None
        else mint_boot_request_token(resolved_root)
    )
    _enforce_private_directory_modes(Path(resolved_root))
    handler = make_local_bridge_handler(
        projects_root=resolved_root,
        request_token=resolved_token,
        task_bridge=task_bridge,
    )
    server = LocalBridgeHTTPServer(
        (host, port),
        handler,
        bridge=bridge,
        bridge_writer=writer,
        bridge_database_path=database_path,
    )
    server.task_bridge = task_bridge
    server.request_token = resolved_token
    return server


def make_local_bridge_handler(
    *,
    projects_root: Path,
    request_token: str | None = None,
    task_bridge: Any | None = None,
):
    """Build a request handler bound to one resolved projects root.
    *request_token* enables the local-trust gate (doc 27 §4.7): exact
    ``Host`` matching plus token-checked mutations; ``None`` disables the
    gate entirely (frozen test composition only).
    """


    class Handler(BaseHTTPRequestHandler):
        def log_message(self, _fmt: str, *_args: Any) -> None:
            return

        def handle_one_request(self) -> None:
            self._diag_started_at: float | None = None
            self._diag_response_status: int | None = None
            self._diag_content_range: str | None = None
            self._diag_content_length: str | None = None
            try:
                super().handle_one_request()
            finally:
                self._diag_finish_request()

        def parse_request(self) -> bool:
            parsed = super().parse_request()
            if parsed:
                self._diag_begin_request()
                # Local-trust gate (build spec doc 27 §4.7): exact loopback
                # ``Host`` on every request, per-boot token + non-simple
                # custom header on every mutation. Runs after ``super()``
                # so the request line and headers are parsed; a rejection
                # answers the typed 403 envelope and drops the connection.
                if not self._local_trust_gate():
                    self.close_connection = True
                    return False
            return parsed

        def _local_trust_gate(self) -> bool:
            if request_token is None:
                return True
            command = getattr(self, "command", "") or ""
            expected_host = self._expected_loopback_host()
            host = self.headers.get("Host")
            if host is None or not hmac.compare_digest(
                host.strip().encode("utf-8"),
                expected_host.encode("utf-8"),
            ):
                self._trust_reject(
                    "host header does not match the bound loopback address; "
                    "DNS-rebinding and spoofed hosts are rejected"
                )
                return False
            if command == "OPTIONS":
                # CORS preflight is exempt (doc 27 §4.7.3) from the mutation
                # token, but still has to prove the bound Host just like
                # every other request.
                return True
            if command in ("GET", "HEAD"):
                return True
            token = self.headers.get(TRUST_TOKEN_HEADER)
            if token is None or not hmac.compare_digest(
                token.strip().encode("utf-8"),
                request_token.encode("utf-8"),
            ):
                self._trust_reject(
                    f"mutation requires the {TRUST_TOKEN_HEADER} header "
                    "carrying this boot's request token"
                )
                return False
            return True

        def _expected_loopback_host(self) -> str:
            host, port = self.server.server_address[:2]
            return f"{host}:{port}"

        def _trust_reject(self, detail: str) -> None:
            try:
                self._send_error(403, "forbidden", detail)
            except (BrokenPipeError, ConnectionResetError):
                return

        def send_response(self, code: int, message: str | None = None) -> None:
            self._diag_response_status = code
            super().send_response(code, message)

        def send_header(self, keyword: str, value: str) -> None:
            lower_keyword = keyword.lower()
            if lower_keyword == "content-range":
                self._diag_content_range = value
            elif lower_keyword == "content-length":
                self._diag_content_length = value
            super().send_header(keyword, value)

        def _diag_begin_request(self) -> None:
            if not _DIAGNOSTICS_ENABLED:
                return
            self._diag_started_at = time.perf_counter()
            print(
                "[AstridBridge] request",
                {
                    "method": self.command,
                    "path": self.path,
                    "range": self.headers.get("Range"),
                    "origin": self.headers.get("Origin"),
                    "userAgent": self.headers.get("User-Agent"),
                },
                flush=True,
            )

        def _diag_finish_request(self) -> None:
            if not _DIAGNOSTICS_ENABLED or self._diag_started_at is None:
                return
            duration_ms = (time.perf_counter() - self._diag_started_at) * 1000
            print(
                "[AstridBridge] response",
                {
                    "method": getattr(self, "command", None),
                    "path": getattr(self, "path", None),
                    "status": self._diag_response_status,
                    "contentRange": self._diag_content_range,
                    "bytesServed": self._diag_content_length,
                    "durationMs": round(duration_ms, 2),
                },
                flush=True,
            )

        # ------------------------------------------------------------------
        # CORS / shared headers
        # ------------------------------------------------------------------

        _ALLOWED_ORIGINS: tuple[str, ...] = (
            "http://localhost:2222",
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:2222",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
        )
        _ALLOWED_METHODS = "GET, HEAD, POST, OPTIONS"
        _ALLOWED_HEADERS = (
            "Content-Type, Range, If-None-Match, If-Modified-Since, "
            "Idempotency-Key, X-Astrid-Request-Token"
        )
        _EXPOSED_HEADERS = "Accept-Ranges, Content-Length, Content-Range, Content-Type, ETag, Last-Modified"

        def _set_cors_headers(self) -> None:
            origin = self.headers.get("Origin", "")
            if origin in self._ALLOWED_ORIGINS:
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Access-Control-Allow-Methods", self._ALLOWED_METHODS)
                self.send_header("Access-Control-Allow-Headers", self._ALLOWED_HEADERS)
                self.send_header("Access-Control-Expose-Headers", self._EXPOSED_HEADERS)
                self.send_header("Access-Control-Max-Age", "86400")
                self.send_header("Vary", "Origin")

        def _send_json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self._set_cors_headers()
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _send_error(self, status: int, code: str, detail: str) -> None:
            self._send_json(status, {"error": code, "detail": detail})

        def _serve_asset(
            self,
            project_slug: str,
            timeline_ref: str,
            asset_key: str,
            *,
            head_only: bool = False,
        ) -> None:
            """Serve one asset with the frozen byte-serving semantics (§9).

            There is exactly one supported resolution path (m4 plan step
            22): the asset key resolves from the persisted timeline
            registry through kernel media/location records in the route
            project, the local bytes are verified against the media
            content SHA-256 before streaming, and only verified local
            locations are served. The legacy sidecar/FSA asset fallback
            was removed — a server without the injected repository bridge
            fails closed with the typed ``500 internal`` envelope.
            """
            self._serve_asset_from_persisted_registry(
                project_slug, timeline_ref, asset_key, head_only=head_only
            )

        def _serve_asset_from_persisted_registry(
            self,
            project_slug: str,
            timeline_ref: str,
            asset_key: str,
            *,
            head_only: bool = False,
        ) -> None:
            """Serve one asset through kernel media/location records.

            The registry entry comes from the repository bridge — never
            from a sidecar file or a filesystem scan (contract §9: a
            locator is a locator, never media identity). Resolution:

            1. the entry's registered ``media_id``, or
            2. a matching kernel ``media_locations`` alias (``file``) in
               the route project (m4 plan step 9 project-scoped lookup),

            then the media row's actual local location is verified against
            its content SHA-256 before any byte is streamed (m4 plan step
            22). A cross-project media id or alias is indistinguishable
            from an unknown one (``404 asset_not_found``); HTTP locators
            are never local (``404 asset_not_local``); unsafe locator
            aliases and unverified or missing bytes are never served.
            """
            import sqlite3

            from astrid.core.repositories.media import MediaNotFoundError
            from astrid.core.repositories.projects import ProjectNotFoundError

            try:
                load = self._bridge().load_timeline(project_slug, timeline_ref)
            except BridgeError as exc:
                self._send_bridge_error(exc)
                return

            assets = load.registry.get("assets", {})
            if not isinstance(assets, Mapping):
                self._send_error(
                    404,
                    "asset_not_found",
                    f"asset {asset_key!r} was not found in timeline {timeline_ref!r}",
                )
                return
            entry = assets.get(asset_key)
            if not isinstance(entry, dict):
                self._send_error(
                    404,
                    "asset_not_found",
                    f"asset {asset_key!r} was not found in timeline {timeline_ref!r}",
                )
                return

            raw_media_id = entry.get("media_id")
            media_id_ref = (
                raw_media_id.strip()
                if isinstance(raw_media_id, str) and raw_media_id.strip()
                else None
            )
            raw_locator = entry.get("file")
            locator = raw_locator.strip() if isinstance(raw_locator, str) and raw_locator.strip() else None
            if media_id_ref is None and locator is None:
                self._send_error(
                    404,
                    "asset_not_found",
                    f"asset {asset_key!r} has no media id or file locator",
                )
                return

            if media_id_ref is None:
                assert locator is not None  # the guard above guarantees one ref
                # Safe-path rules for the locator alias (contract §9): an
                # HTTP locator is never local and an absolute or
                # ``..``-traversing alias is never used as a lookup key.
                classification = _classify_persisted_registry_locator(locator)
                if classification == "http":
                    self._send_error(
                        404,
                        "asset_not_local",
                        f"asset {asset_key!r} is not available as a local file",
                    )
                    return
                if classification == "unsafe":
                    self._send_error(
                        404,
                        "asset_not_found",
                        f"asset {asset_key!r} has an unsafe locator: {locator!r}",
                    )
                    return

            try:
                writer = self._bridge_writer()
            except BridgeError as exc:
                self._send_bridge_error(exc)
                return
            try:
                project_id = self._projects_repository().resolve(writer, project_slug)
            except ProjectNotFoundError:
                self._send_error(
                    404,
                    "project_not_found",
                    f"project {project_slug!r} was not found",
                )
                return

            media = self._media_repository()
            try:
                if media_id_ref is not None:
                    with writer.read_only_connection() as conn:
                        conn.row_factory = sqlite3.Row
                        resolved_media_id = media.resolve_media(
                            conn,
                            project_id=project_id,
                            media_id=media_id_ref,
                        )
                else:
                    assert locator is not None  # the guard above guarantees one ref
                    resolved_media_id = self._resolve_locator_alias(
                        media, writer, project_id, locator
                    )
            except MediaNotFoundError:
                self._send_error(
                    404,
                    "asset_not_found",
                    f"asset {asset_key!r} was not found in project {project_slug!r}",
                )
                return

            media_model = media.show(writer, resolved_media_id)
            verified = self._resolve_verified_local_location(media_model)
            if verified is None:
                self._send_error(
                    404,
                    "asset_not_found",
                    f"asset {asset_key!r} has no verified local bytes in project {project_slug!r}",
                )
                return

            local_path, file_size = verified
            stat = local_path.stat()
            content_type, _ = mimetypes.guess_type(str(local_path))
            if content_type is None:
                content_type = "application/octet-stream"
            etag = f'"{stat.st_mtime_ns:x}-{file_size:x}"'
            last_modified = formatdate(stat.st_mtime, usegmt=True)
            self._serve_resolved_asset(
                local_path,
                file_size,
                content_type,
                etag,
                last_modified,
                head_only=head_only,
            )

        def _resolve_locator_alias(
            self,
            media: MediaRepository,
            writer: Any,
            project_id: str,
            locator: str,
        ) -> str:
            """Resolve a registry ``file`` alias to a project-scoped media id.

            The alias is matched against the kernel ``media_locations``
            rows of the route project in both supported realms
            (managed first, then external reference-in-place). A locator
            is a replaceable alias, never media identity; an alias that
            matches no location — including one that belongs to another
            project — raises :class:`MediaNotFoundError`.
            """
            import sqlite3

            from astrid.core.repositories.media import (
                EXTERNAL_LOCAL_REALM,
                MANAGED_LOCAL_REALM,
                MediaNotFoundError,
            )

            last_error: MediaNotFoundError | None = None
            with writer.read_only_connection() as conn:
                conn.row_factory = sqlite3.Row
                for realm in (MANAGED_LOCAL_REALM, EXTERNAL_LOCAL_REALM):
                    try:
                        return media.resolve_media(
                            conn,
                            project_id=project_id,
                            realm=realm,
                            locator=locator,
                        )
                    except MediaNotFoundError as exc:
                        last_error = exc
            if last_error is None:  # pragma: no cover - both realms always run
                raise MediaNotFoundError(media_id=locator)
            raise last_error

        def _serve_media_content(
            self,
            project_slug: str,
            media_id: str,
            *,
            head_only: bool = False,
        ) -> None:
            """Serve one managed-media object by ULID id (doc 27 §4.1).

            The media row must resolve inside the route project — a
            foreign or unknown id is ``404 media_not_found`` with no
            existence leak — and its bytes must verify against the row's
            content SHA-256 at a local location, otherwise
            ``404 media_bytes_missing``. Content-Type comes from the
            stored ``mime_type``; validators are stat-derived; Range /
            ``If-None-Match`` semantics are the shared asset wire rules.
            """
            import sqlite3

            from astrid.core.repositories.media import MediaNotFoundError
            from astrid.core.repositories.projects import ProjectNotFoundError

            try:
                writer = self._bridge_writer()
            except BridgeError as exc:
                self._send_bridge_error(exc)
                return
            try:
                project_id = self._projects_repository().resolve(
                    writer, project_slug
                )
            except ProjectNotFoundError:
                self._send_error(
                    404,
                    "project_not_found",
                    f"project {project_slug!r} was not found",
                )
                return

            media = self._media_repository()
            try:
                with writer.read_only_connection() as conn:
                    conn.row_factory = sqlite3.Row
                    resolved_media_id = media.resolve_media(
                        conn,
                        project_id=project_id,
                        media_id=media_id,
                    )
            except MediaNotFoundError:
                self._send_error(
                    404,
                    "media_not_found",
                    f"media {media_id!r} was not found in project "
                    f"{project_slug!r}",
                )
                return

            media_model = media.show(writer, resolved_media_id)
            verified = self._resolve_verified_local_location(media_model)
            if verified is None:
                self._send_error(
                    404,
                    "media_bytes_missing",
                    f"media {resolved_media_id!r} has no verified local bytes",
                )
                return

            local_path, file_size = verified
            stat = local_path.stat()
            etag = f'"{stat.st_mtime_ns:x}-{file_size:x}"'
            last_modified = formatdate(stat.st_mtime, usegmt=True)
            self._serve_resolved_asset(
                local_path,
                file_size,
                media_model.mime_type,
                etag,
                last_modified,
                head_only=head_only,
            )

        def _projects_repository(self) -> ProjectRepository:
            """Read-only project resolution over the injected single writer.

            Only :meth:`ProjectRepository.resolve` is used (a
            transaction-free read on the writer's read-only connection);
            the event append and receipt services are never touched, so a
            lightweight instance is safe and opens no second authority.
            The repository implementation is imported lazily so importing
            this module never imports a repository (plan step 30).
            """
            from astrid.core.repositories.projects import ProjectRepository

            return ProjectRepository(  # type: ignore[arg-type]
                events=None,
                receipts=None,
            )

        def _media_repository(self) -> MediaRepository:
            """Read-only media/location resolution over the injected writer.

            Only :meth:`MediaRepository.resolve_media` and
            :meth:`MediaRepository.show` are used (transaction-free reads
            on the writer's read-only connection); the event append and
            receipt services are never touched, so a lightweight instance
            is safe and opens no second authority. The repository
            implementation is imported lazily so importing this module
            never imports a repository (plan step 30).
            """
            from astrid.core.repositories.media import MediaRepository

            return MediaRepository(  # type: ignore[arg-type]
                events=None,
                receipts=None,
                projects_root=projects_root,
            )

        def _bridge_writer(self) -> Any:
            """The single repository writer injected at the serve root."""
            writer = getattr(self.server, "bridge_writer", None)
            if writer is None:
                raise BridgeInternalError(
                    "the repository writer is not composed on this server"
                )
            return writer

        def _resolve_verified_local_location(
            self,
            media_model: Any,
        ) -> tuple[Path, int] | None:
            """Return the first location whose bytes match the media hash.

            Managed locations resolve to the frozen digest tree path for
            the media content hash; external locations resolve to their
            registered reference-in-place path. A location is served only
            when it exists and its actual bytes SHA-256 to the media row's
            ``content_hash`` (m4 plan step 22: actual-byte verification
            before streaming).
            """
            from astrid.core.io.media_import import (
                managed_media_path,
                sha256_file_bytes,
            )
            from astrid.core.repositories.media import (
                EXTERNAL_LOCAL_REALM,
                MANAGED_LOCAL_REALM,
            )

            for location in media_model.locations:
                if location.realm == MANAGED_LOCAL_REALM:
                    path = managed_media_path(projects_root, media_model.content_hash)
                elif location.realm == EXTERNAL_LOCAL_REALM:
                    path = Path(location.locator)
                else:
                    continue
                try:
                    if not path.is_file():
                        continue
                    if sha256_file_bytes(path) != media_model.content_hash:
                        continue
                    return path, int(path.stat().st_size)
                except OSError:
                    continue
            return None

        def _serve_resolved_asset(
            self,
            local_path: Path,
            file_size: int,
            content_type: str,
            etag: str,
            last_modified: str,
            *,
            head_only: bool,
        ) -> None:
            """Wire semantics for a resolved local asset: 200/206/304/416/400.

            Single-range grammar only (§9.3): a malformed Range header is a
            400 text/plain, an unsatisfiable range is 416 with
            ``Content-Range: bytes */<size>``, and ``If-None-Match`` matching
            the ETag short-circuits to 304 with validators and cache headers
            but no body. ``HEAD`` mirrors ``GET`` without a body.
            """

            def send_asset_headers(
                *,
                content_length: int,
                content_range: str | None = None,
            ) -> None:
                self._set_cors_headers()
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(content_length))
                if content_range is not None:
                    self.send_header("Content-Range", content_range)
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Cache-Control", "private, no-cache")
                self.send_header("ETag", etag)
                self.send_header("Last-Modified", last_modified)

            def stream_file_range(range_start: int, content_len: int) -> None:
                try:
                    with local_path.open("rb") as fh:
                        fh.seek(range_start)
                        remaining = content_len
                        while remaining > 0:
                            chunk = fh.read(min(65536, remaining))
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                            remaining -= len(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    return

            range_header = self.headers.get("Range")
            if range_header is None:
                if self.headers.get("If-None-Match") == etag:
                    self.send_response(304)
                    self._set_cors_headers()
                    self.send_header("ETag", etag)
                    self.send_header("Last-Modified", last_modified)
                    self.send_header("Cache-Control", "private, no-cache")
                    self.end_headers()
                    return

                if head_only:
                    self.send_response(200)
                    send_asset_headers(content_length=file_size)
                    self.end_headers()
                    return

                if file_size > _RANGELESS_FULL_BODY_LIMIT_BYTES:
                    range_start = 0
                    range_end = min(file_size - 1, _RANGELESS_INITIAL_CHUNK_BYTES - 1)
                    content_len = range_end - range_start + 1

                    self.send_response(206)
                    send_asset_headers(
                        content_length=content_len,
                        content_range=f"bytes {range_start}-{range_end}/{file_size}",
                    )
                    self.end_headers()
                    stream_file_range(range_start, content_len)
                    return

                # ---- 200 full response ----
                self.send_response(200)
                send_asset_headers(content_length=file_size)
                self.end_headers()
                if head_only:
                    return
                stream_file_range(0, file_size)
                return

            # ---- Parse Range header ----
            match = _RANGE_RE.match(range_header)
            if match is None:
                self.send_response(400)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"invalid Range header")
                return

            range_start_str = match.group(1)
            range_end_str = match.group(2)

            if range_start_str == "" and range_end_str == "":
                self.send_response(400)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"empty Range")
                return

            # ---- suffix range: bytes=-N  (last N bytes) ----
            if range_start_str == "" and range_end_str != "":
                suffix_len = int(range_end_str)
                if suffix_len <= 0:
                    self._send_416(
                        file_size,
                        etag=etag,
                        last_modified=last_modified,
                    )
                    return
                range_start = max(0, file_size - suffix_len)
                range_end = file_size - 1
            elif range_start_str != "" and range_end_str == "":
                # ---- open-ended: bytes=N- ----
                range_start = int(range_start_str)
                if file_size > _RANGELESS_FULL_BODY_LIMIT_BYTES:
                    range_end = min(file_size - 1, range_start + _OPEN_ENDED_RANGE_CHUNK_BYTES - 1)
                else:
                    range_end = file_size - 1
            else:
                range_start = int(range_start_str)
                range_end = int(range_end_str)

            # ---- Validate range ----
            if range_start < 0 or range_end < range_start or range_start >= file_size:
                self._send_416(
                    file_size,
                    etag=etag,
                    last_modified=last_modified,
                )
                return

            # Clamp range_end to file_size - 1
            if range_end >= file_size:
                range_end = file_size - 1

            content_len = range_end - range_start + 1

            self.send_response(206)
            send_asset_headers(
                content_length=content_len,
                content_range=f"bytes {range_start}-{range_end}/{file_size}",
            )
            self.end_headers()
            if head_only:
                return

            stream_file_range(range_start, content_len)

        def _send_416(
            self,
            file_size: int,
            *,
            etag: str,
            last_modified: str,
        ) -> None:
            self.send_response(416)
            self._set_cors_headers()
            self.send_header("Content-Range", f"bytes */{file_size}")
            self.send_header("Content-Type", "text/plain")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Cache-Control", "private, no-cache")
            self.send_header("ETag", etag)
            self.send_header("Last-Modified", last_modified)
            self.send_header("Content-Length", "0")
            self.end_headers()

        # ------------------------------------------------------------------
        # Route dispatcher
        # ------------------------------------------------------------------

        def _bridge(self):
            """The repository-backed bridge injected at the serve root.

            Read routes have no filesystem/legacy-authority fallback: when
            the injected service is absent they fail closed with a typed
            500 ``internal`` envelope.
            """
            bridge = getattr(self.server, "bridge", None)
            if bridge is None:
                raise BridgeInternalError(
                    "the repository bridge is not composed on this server"
                )
            return bridge

        def _send_bridge_error(self, error: BridgeError) -> None:
            """Serialize a typed bridge error with its frozen envelope."""
            self._send_json(error.status_code, error.to_dict())

        def _task_bridge(self):
            """The task/executor bridge injected at the serve root.

            Task routes fail closed with the typed ``500 internal``
            envelope when the composition root did not compose one.
            """
            bridge = getattr(self.server, "task_bridge", None)
            if bridge is None:
                raise BridgeInternalError(
                    "the task bridge is not composed on this server"
                )
            return bridge

        def _send_task_error(self, exc: BaseException) -> None:
            """Map kernel/service failures onto the public error surface."""
            from astrid.core.receipts.service import ReceiptMismatchError
            from astrid.core.repositories.tasks import (
                TaskAttemptNotFoundError,
                TaskNotFoundError,
                TaskTransitionError,
                TaskValidationError,
            )

            if isinstance(exc, BridgeError):
                self._send_bridge_error(exc)
                return
            if isinstance(exc, ReceiptMismatchError):
                self._send_error(
                    409,
                    "idempotency_mismatch",
                    "this idempotency key was already committed with "
                    "different canonical request bytes",
                )
                return
            if isinstance(exc, (TaskNotFoundError, TaskAttemptNotFoundError)):
                self._send_error(404, "not_found", str(exc))
                return
            if isinstance(exc, TaskValidationError):
                self._send_error(400, "invalid_body", str(exc))
                return
            if isinstance(exc, TaskTransitionError):
                conflict = BridgeConflictError(
                    str(getattr(exc, "reason", "conflict")),
                    attempt=self._task_bridge()._current_attempt_extra(
                        getattr(exc, "attempt_id", None)
                    ),
                )
                self._send_bridge_error(conflict)
                return
            self._send_error(500, "internal", "unexpected task route failure")

        def _require_idempotency_key(self) -> str | None:
            key = self.headers.get("Idempotency-Key")
            if key is None or not key.strip():
                self._send_error(
                    400,
                    "invalid_body",
                    "the Idempotency-Key header is required for this route",
                )
                return None
            key = key.strip()
            if len(key) > 200 or not all(32 <= ord(c) <= 126 for c in key):
                self._send_error(
                    400,
                    "invalid_body",
                    "Idempotency-Key must be 1-200 printable ASCII chars",
                )
                return None
            return key

        def _read_json_body_capped(
            self, *, max_bytes: int
        ) -> dict[str, Any] | None:
            raw_header = self.headers.get("Content-Length")
            if raw_header is None:
                return None
            try:
                length = int(raw_header)
            except (TypeError, ValueError):
                return None
            if length <= 0 or length > max_bytes:
                return None
            raw = self.rfile.read(length)
            try:
                payload = json.loads(raw.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return None
            return payload if isinstance(payload, dict) else None

        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            parts = [part for part in unquote(path).split("/") if part]

            if parts == ["health"]:
                try:
                    status = self._bridge().health(str(projects_root))
                except BridgeError as exc:
                    self._send_bridge_error(exc)
                    return
                self._send_json(200, status.to_dict())
                return

            if parts == ["routes"]:
                self._send_json(200, _route_schema(projects_root))
                return

            if parts == ["projects"]:
                try:
                    rows = [
                        row.to_dict() for row in self._bridge().list_projects()
                    ]
                except BridgeError as exc:
                    self._send_bridge_error(exc)
                    return
                self._send_json(200, {"projects": rows})
                return

            if len(parts) == 3 and parts[0] == "projects" and parts[2] == "timelines":
                try:
                    rows = [
                        row.to_dict()
                        for row in self._bridge().list_timelines(parts[1])
                    ]
                except (BridgeInvalidProjectError, BridgeProjectNotFoundError) as exc:
                    self._send_bridge_error(exc)
                    return
                self._send_json(200, {"timelines": rows})
                return

            if len(parts) == 4 and parts[0] == "projects" and parts[2] == "timelines":
                try:
                    payload = self._bridge().load_timeline(
                        parts[1], parts[3]
                    ).to_dict()
                except (
                    BridgeInvalidProjectError,
                    BridgeInvalidTimelineError,
                    BridgeProjectNotFoundError,
                    BridgeTimelineNotFoundError,
                ) as exc:
                    self._send_bridge_error(exc)
                    return
                self._send_json(200, payload)
                return

            # ---- Asset endpoint ----
            if (
                len(parts) == 6
                and parts[0] == "projects"
                and parts[2] == "timelines"
                and parts[4] == "assets"
            ):
                self._serve_asset(parts[1], parts[3], parts[5])
                return

            # ---- Task reads (polling surface; doc 27 §4.1) ----
            if (
                len(parts) == 3
                and parts[0] == "projects"
                and parts[2] == "tasks"
            ):
                try:
                    query = urlparse(self.path).query
                    params = dict(
                        part.split("=", 1)
                        for part in query.split("&")
                        if "=" in part
                    )
                    payload = self._task_bridge().list_tasks(
                        slug=parts[1],
                        limit=int(params.get("limit", "50")),
                        offset=int(params.get("offset", "0")),
                    )
                except BridgeError as exc:
                    self._send_bridge_error(exc)
                    return
                except ValueError:
                    self._send_error(400, "invalid_body", "bad paging param")
                    return
                self._send_json(200, payload)
                return

            if (
                len(parts) == 4
                and parts[0] == "projects"
                and parts[2] == "tasks"
            ):
                try:
                    payload = self._task_bridge().task_detail(
                        slug=parts[1], task_id=parts[3]
                    )
                except BridgeError as exc:
                    self._send_bridge_error(exc)
                    return
                self._send_json(200, payload)
                return

            # ---- Gallery reads (doc 27 §4.1) ----
            if (
                len(parts) == 3
                and parts[0] == "projects"
                and parts[2] == "generations"
            ):
                try:
                    query = urlparse(self.path).query
                    params = dict(
                        part.split("=", 1)
                        for part in query.split("&")
                        if "=" in part
                    )
                    starred_raw = params.get("starred")
                    if starred_raw is None:
                        starred = None
                    elif starred_raw.lower() in ("true", "1"):
                        starred = True
                    elif starred_raw.lower() in ("false", "0"):
                        starred = False
                    else:
                        self._send_error(
                            400,
                            "invalid_body",
                            "starred must be true or false",
                        )
                        return
                    payload = self._task_bridge().list_generations(
                        slug=parts[1],
                        limit=int(params.get("limit", "50")),
                        cursor=params.get("cursor"),
                        starred=starred,
                    )
                except BridgeError as exc:
                    self._send_bridge_error(exc)
                    return
                except ValueError:
                    self._send_error(400, "invalid_body", "bad paging param")
                    return
                self._send_json(200, payload)
                return

            if (
                len(parts) == 4
                and parts[0] == "projects"
                and parts[2] == "generations"
            ):
                try:
                    payload = self._task_bridge().generation_detail(
                        slug=parts[1], generation_id=parts[3]
                    )
                except BridgeError as exc:
                    self._send_bridge_error(exc)
                    return
                self._send_json(200, payload)
                return

            # ---- Managed-media content (doc 27 §4.1) ----
            if (
                len(parts) == 5
                and parts[0] == "projects"
                and parts[2] == "media"
                and parts[4] == "content"
            ):
                self._serve_media_content(parts[1], parts[3])
                return

            self._send_error(404, "not_found", f"unknown route: {path}")

        def do_HEAD(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            parts = [part for part in unquote(path).split("/") if part]

            if (
                len(parts) == 6
                and parts[0] == "projects"
                and parts[2] == "timelines"
                and parts[4] == "assets"
            ):
                self._serve_asset(
                    parts[1], parts[3], parts[5], head_only=True
                )
                return

            if (
                len(parts) == 5
                and parts[0] == "projects"
                and parts[2] == "media"
                and parts[4] == "content"
            ):
                self._serve_media_content(
                    parts[1], parts[3], head_only=True
                )
                return

            self.send_response(404)
            self._set_cors_headers()
            self.send_header("Content-Length", "0")
            self.end_headers()

        # ------------------------------------------------------------------
        # OPTIONS (CORS preflight)
        # ------------------------------------------------------------------

        def do_OPTIONS(self) -> None:  # noqa: N802
            self.send_response(204)
            self._set_cors_headers()
            self.send_header("Content-Length", "0")
            self.end_headers()

        # ------------------------------------------------------------------
        # POST — save timeline config
        # ------------------------------------------------------------------

        def do_POST(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            parts = [part for part in unquote(path).split("/") if part]

            # POST /projects/:project/timelines/:timeline/save
            if (
                len(parts) == 5
                and parts[0] == "projects"
                and parts[2] == "timelines"
                and parts[4] == "save"
            ):
                project_slug = parts[1]
                timeline_ref = parts[3]
                body = self._read_request_body()
                if body is None:
                    self._send_error(
                        400, "invalid_body", "request body must be valid JSON"
                    )
                    return
                # Route-level wire validation (contract §6.1): object
                # config/registry and integer-only expected_version map to
                # the frozen 400 envelopes; booleans are not versions.
                try:
                    request = TimelineSaveRequest.parse(body)
                except BridgeError as exc:
                    self._send_bridge_error(exc)
                    return
                # Deep wire-shape schema guard (contract §6.2): beyond
                # "is an object", a non-object registry.assets or a payload
                # that cannot canonicalize inside the kernel bounds is a
                # typed 422 schema_incompatible with issues[], never a
                # connection-close 500 (the incident's failure mode).
                try:
                    _validate_save_payload_schema(request)
                except BridgeSchemaIncompatibleError as exc:
                    self._send_bridge_error(exc)
                    return
                try:
                    bridge = self._bridge()
                    result = bridge.save_timeline(
                        project_slug, timeline_ref, request
                    )
                except BridgeError as exc:
                    self._send_bridge_error(exc)
                    return
                except Exception as _exc:  # noqa: BLE001 - defensive 500
                    self._send_error(
                        500,
                        "internal",
                        "unexpected failure while saving the timeline",
                    )
                    return
                # The committed response is the frozen load shape; internal
                # receipt fields are absent by construction (contract §7).
                self._send_json(200, result.to_dict())
                return

            _MAX_JSON_BODY_BYTES = 1024 * 1024

            # ---- R1: task admission (public or executor child) ----
            if (
                len(parts) == 3
                and parts[0] == "projects"
                and parts[2] == "tasks"
            ):
                key = self._require_idempotency_key()
                if key is None:
                    return
                body = self._read_json_body_capped(
                    max_bytes=_MAX_JSON_BODY_BYTES
                )
                if body is None:
                    self._send_error(
                        400,
                        "invalid_body",
                        "request body must be a JSON object of at most "
                        "1 MiB",
                    )
                    return
                bridge = self._task_bridge()
                try:
                    if "child_admission" in body:
                        status, payload = bridge.admit_child(
                            slug=parts[1], body=body, idempotency_key=key
                        )
                        self._send_json(status, payload)
                        return
                    status, payload = bridge.admit(
                        slug=parts[1], body=body, idempotency_key=key
                    )
                except BridgeError as exc:
                    self._send_bridge_error(exc)
                    return
                except Exception as exc:  # noqa: BLE001 - mapped below
                    self._send_task_error(exc)
                    return
                self._send_json(status, payload)
                return

            # ---- R3: fenced global claim ----
            if parts == ["queue", "claim"]:
                body = self._read_json_body_capped(
                    max_bytes=_MAX_JSON_BODY_BYTES
                )
                if body is None:
                    self._send_error(
                        400, "invalid_body", "request body must be JSON"
                    )
                    return
                try:
                    won = self._task_bridge().claim(
                        executor_id=body.get("executor_id"),
                        capabilities=body.get("capabilities"),
                        lease_seconds=body.get("lease_seconds", 300),
                    )
                except BridgeError as exc:
                    self._send_bridge_error(exc)
                    return
                except Exception as exc:  # noqa: BLE001 - mapped below
                    self._send_task_error(exc)
                    return
                if won is None:
                    self.send_response(204)
                    self._set_cors_headers()
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                self._send_json(200, won)
                return

            # ---- R5/R7/R8: per-attempt routes ----
            if (
                len(parts) == 5
                and parts[0] == "tasks"
                and parts[2] == "attempts"
            ):
                task_id = parts[1]
                verb = parts[4]
                try:
                    attempt_no = int(parts[3])
                except ValueError:
                    self._send_error(
                        400, "invalid_body", "attempt_no must be an integer"
                    )
                    return
                self._dispatch_attempt_route(task_id, attempt_no, verb)
                return

            # ---- R2: cancellation ----
            if (
                len(parts) == 5
                and parts[0] == "projects"
                and parts[2] == "tasks"
                and parts[4] == "cancel"
            ):
                body = self._read_optional_request_body() or {}
                bridge = self._task_bridge()
                try:
                    payload = bridge.cancel(
                        slug=parts[1], task_id=parts[3], body=body
                    )
                except BridgeError as exc:
                    self._send_bridge_error(exc)
                    return
                except Exception as exc:  # noqa: BLE001 - mapped below
                    self._send_task_error(exc)
                    return
                self._send_json(200, payload)
                return

            self._send_error(404, "not_found", f"unknown POST route: {path}")

        def _dispatch_attempt_route(
            self, task_id: str, attempt_no: int, verb: str
        ) -> None:
            """R5 heartbeat / R7 complete / R8 fail (doc 27 §4.1)."""
            if verb == "heartbeat":
                body = self._read_json_body_capped(max_bytes=1024 * 1024)
                if body is None:
                    self._send_error(
                        400, "invalid_body", "request body must be JSON"
                    )
                    return
                attempt_id = body.get("attempt_id")
                lease_id = body.get("lease_id")
                status_version = body.get("status_version")
                for name, value in (
                    ("attempt_id", attempt_id),
                    ("lease_id", lease_id),
                ):
                    if not isinstance(value, str) or not value:
                        self._send_error(
                            400,
                            "invalid_body",
                            f"{name} is required",
                        )
                        return
                if (
                    isinstance(status_version, bool)
                    or not isinstance(status_version, int)
                    or status_version <= 0
                ):
                    self._send_error(
                        400,
                        "invalid_body",
                        "status_version is required",
                    )
                    return
                try:
                    payload = self._task_bridge().heartbeat(
                        task_id=task_id,
                        attempt_no=attempt_no,
                        attempt_id=attempt_id,
                        lease_id=lease_id,
                        expected_status_version=status_version,
                        lease_seconds=body.get("lease_seconds", 300),
                        progress=body.get("progress"),
                    )
                except BridgeError as exc:
                    self._send_bridge_error(exc)
                    return
                except Exception as exc:  # noqa: BLE001 - mapped below
                    self._send_task_error(exc)
                    return
                self._send_json(200, payload)
                return

            if verb == "complete":
                self._handle_complete(task_id, attempt_no)
                return

            if verb == "fail":
                key = self._require_idempotency_key()
                if key is None:
                    return
                body = self._read_json_body_capped(max_bytes=1024 * 1024)
                if body is None:
                    self._send_error(
                        400, "invalid_body", "request body must be JSON"
                    )
                    return
                try:
                    payload = self._task_bridge().fail(
                        task_id=task_id,
                        attempt_no=attempt_no,
                        idempotency_key=key,
                        body=body,
                    )
                except BridgeError as exc:
                    self._send_bridge_error(exc)
                    return
                except Exception as exc:  # noqa: BLE001 - mapped below
                    self._send_task_error(exc)
                    return
                self._send_json(200, payload)
                return

            self._send_error(404, "not_found", f"unknown attempt verb {verb!r}")

        def _handle_complete(self, task_id: str, attempt_no: int) -> None:
            """R7: one multipart request; server hashes and commits (§4.4)."""
            import uuid as _uuid

            from astrid.core.integrations.reigh.multipart import (
                MultipartError,
                parse_multipart,
            )
            from astrid.core.io.media_import import staging_path

            key = self._require_idempotency_key()
            if key is None:
                return
            max_request = int(
                os.environ.get(
                    "ASTRID_BRIDGE_MAX_STAGING_REQUEST_BYTES",
                    str(2 * 1024 * 1024 * 1024),
                )
            )
            content_length = self.headers.get("Content-Length")
            txn_id = _uuid.uuid4().hex
            staging_dir = staging_path(str(projects_root), txn_id)
            try:
                parsed = parse_multipart(
                    self.rfile,
                    content_type=self.headers.get("Content-Type"),
                    content_length=content_length,
                    transfer_encoding=self.headers.get("Transfer-Encoding"),
                    staging_dir=staging_dir,
                    max_body_bytes=max_request,
                )
            except MultipartError as exc:
                status = 413 if exc.wire_code == "payload_too_large" else 400
                self._send_error(status, exc.wire_code, str(exc))
                return
            try:
                manifest = json.loads(parsed.fields.get("manifest", "{}"))
                if not isinstance(manifest, dict):
                    raise ValueError("manifest must be a JSON object")
            except (json.JSONDecodeError, ValueError):
                for staged in parsed.files:
                    staged.path.unlink(missing_ok=True)
                self._send_error(
                    400, "invalid_body", "the manifest part must be JSON"
                )
                return
            fence = {
                "lease_id": manifest.get("lease_id"),
                "status_version": manifest.get("status_version"),
                "attempt_id": manifest.get("attempt_id"),
            }
            output_specs = manifest.get("outputs") or []
            try:
                payload = self._task_bridge().complete(
                    task_id=task_id,
                    attempt_no=attempt_no,
                    idempotency_key=key,
                    fence=fence,
                    output_specs=output_specs,
                    staged_files=parsed.files,
                )
            except BridgeError as exc:
                self._cleanup_staging_dir(staging_dir)
                self._send_bridge_error(exc)
                return
            except Exception as exc:  # noqa: BLE001 - mapped below
                self._cleanup_staging_dir(staging_dir)
                self._send_task_error(exc)
                return
            self._cleanup_staging_dir(staging_dir)
            self._send_json(200, payload)

        @staticmethod
        def _cleanup_staging_dir(staging_dir) -> None:
            import shutil as _shutil

            try:
                _shutil.rmtree(staging_dir, ignore_errors=True)
            except OSError:
                pass


        # Request helpers
        # ------------------------------------------------------------------

        def _read_request_body(self) -> dict[str, Any] | None:
            content_length = self.headers.get("Content-Length")
            if content_length is None:
                return None
            try:
                length = int(content_length)
            except (ValueError, TypeError):
                return None
            if length <= 0:
                return None
            raw = self.rfile.read(length)
            try:
                payload = json.loads(raw.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return None
            return payload if isinstance(payload, dict) else None

        def _read_optional_request_body(self) -> dict[str, Any] | None:
            content_length = self.headers.get("Content-Length")
            if content_length is None:
                return {}
            try:
                length = int(content_length)
            except (ValueError, TypeError):
                return None
            if length <= 0:
                return {}
            raw = self.rfile.read(length)
            try:
                payload = json.loads(raw.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return None
            return payload if isinstance(payload, dict) else None

    return Handler


def _validate_save_payload_schema(request: TimelineSaveRequest) -> None:
    """Route-level schema guard producing the frozen ``422`` envelope.

    The repository treats ``config``/``registry`` as loose editor objects
    (contract §5.2), so the only wire-shape violations beyond "is an
    object" are a non-object ``registry.assets`` and payloads that cannot
    canonicalize within the kernel bounds (NaN/Infinity/oversize). Both map
    to ``422 schema_incompatible`` (contract §6.2) with JSON-pointer-style
    ``issues[]``, mirroring the repository's canonicalization gate so the
    route and the store agree on what is rejectable before any mutation.
    """
    issues: list[BridgeIssue] = []
    assets = request.registry.get("assets", {})
    if not isinstance(assets, Mapping):
        issues.append(
            BridgeIssue(
                pointer="/registry/assets",
                code="schema_incompatible",
                message="registry.assets must be a JSON object",
            )
        )
    for pointer, value in (
        ("/config", request.config),
        ("/registry", request.registry),
    ):
        try:
            canonical_json(dict(value))
        except CanonicalizationError as exc:
            issues.append(
                BridgeIssue(
                    pointer=pointer,
                    code="schema_incompatible",
                    message=str(exc),
                )
            )
    if issues:
        raise BridgeSchemaIncompatibleError(
            "config/registry failed schema validation",
            issues=issues,
        )
