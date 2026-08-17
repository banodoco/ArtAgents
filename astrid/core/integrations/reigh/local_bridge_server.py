"""HTTP surface for the Astrid local read/write bridge."""

from __future__ import annotations

import json
import mimetypes
import os
import re
import time
from collections.abc import Mapping
from email.utils import formatdate
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, ClassVar
from urllib.parse import unquote, urlparse

from astrid.core.foundation.project_paths import sources_dir, validate_project_slug
from astrid.core.integrations.reigh.bridge_service import (
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
    resolve_bridge_asset,
    resolve_bridge_projects_root,
)
from astrid.core.receipts.canonical import (
    CanonicalizationError,
    canonical_json,
)
from astrid.core.timeline.paths import validate_timeline_slug, validate_timeline_ulid

_RANGE_RE = re.compile(r"^bytes\s*=\s*(\d*)\s*-\s*(\d*)\s*$")
_RANGELESS_FULL_BODY_LIMIT_BYTES = 64 * 1024 * 1024
_RANGELESS_INITIAL_CHUNK_BYTES = 1024 * 1024
_OPEN_ENDED_RANGE_CHUNK_BYTES = 4 * 1024 * 1024
_DIAGNOSTICS_ENABLED = os.environ.get("ASTRID_BRIDGE_DIAGNOSTICS", "0") != "0"


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


def create_local_bridge_server(
    *,
    projects_root: str | Path | None = None,
    host: str = "127.0.0.1",
    port: int = 0,
) -> ThreadingHTTPServer:
    """Create a bridge HTTP server bound to the requested host/port."""
    resolved_root = resolve_bridge_projects_root(projects_root)
    handler = make_local_bridge_handler(projects_root=resolved_root)
    return LocalBridgeHTTPServer((host, port), handler)


def make_local_bridge_handler(*, projects_root: Path):
    """Build a request handler bound to one resolved projects root."""

    class Handler(BaseHTTPRequestHandler):
        _asset_resolution_cache: ClassVar[dict[tuple[str, str, str], dict[str, Any]]] = {}

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
            return parsed

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
        _ALLOWED_HEADERS = "Content-Type, Range, If-None-Match, If-Modified-Since"
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

        # ------------------------------------------------------------------
        # Asset serving helpers
        # ------------------------------------------------------------------



        def _serve_file(
            self,
            local_path: Path,
            *,
            content_type: str,
            cache_control: str,
            head_only: bool = False,
        ) -> None:
            stat = local_path.stat()
            file_size = stat.st_size
            etag = f'"{stat.st_mtime_ns:x}-{file_size:x}"'
            last_modified = formatdate(stat.st_mtime, usegmt=True)

            def send_file_headers(
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
                self.send_header("Cache-Control", cache_control)
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
                    self.send_header("Cache-Control", cache_control)
                    self.end_headers()
                    return

                self.send_response(200)
                send_file_headers(content_length=file_size)
                self.end_headers()
                if head_only:
                    return
                stream_file_range(0, file_size)
                return

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

            if range_start_str == "":
                suffix_len = int(range_end_str)
                if suffix_len <= 0:
                    self._send_416(file_size)
                    return
                range_start = max(0, file_size - suffix_len)
                range_end = file_size - 1
            elif range_end_str == "":
                range_start = int(range_start_str)
                range_end = file_size - 1
            else:
                range_start = int(range_start_str)
                range_end = int(range_end_str)

            if range_start < 0 or range_end < range_start or range_start >= file_size:
                self._send_416(file_size)
                return

            if range_end >= file_size:
                range_end = file_size - 1

            content_len = range_end - range_start + 1
            self.send_response(206)
            send_file_headers(
                content_length=content_len,
                content_range=f"bytes {range_start}-{range_end}/{file_size}",
            )
            self.end_headers()
            if head_only:
                return
            stream_file_range(range_start, content_len)



        def _resolve_cached_asset(
            self,
            project_slug: str,
            timeline_ref: str,
            asset_key: str,
        ) -> tuple[Path, int, str, str, str, bool] | None:
            """Resolve an asset path once and cache the result per file identity.

            The cache is keyed by (project, timeline, asset_key) and invalidated
            when the underlying file's mtime or size changes. This avoids the
            expensive registry re-sync and timeline lookup on every byte-range
            request for the same asset.
            """
            cache_key = (project_slug, timeline_ref, asset_key)
            cached = self._asset_resolution_cache.get(cache_key)
            if cached is not None:
                local_path = cached["local_path"]
                try:
                    stat = local_path.stat()
                except OSError:
                    self._asset_resolution_cache.pop(cache_key, None)
                    return None
                if stat.st_mtime_ns == cached["mtime_ns"] and stat.st_size == cached["file_size"]:
                    return (
                        local_path,
                        cached["file_size"],
                        cached["content_type"],
                        cached["etag"],
                        cached["last_modified"],
                        True,
                    )
                self._asset_resolution_cache.pop(cache_key, None)

            resolved = resolve_bridge_asset(
                project_slug, timeline_ref, asset_key, root=projects_root, sync_sources=False,
            )
            if resolved is None:
                return None
            if resolved.source_kind == "http":
                return None
            local_path = resolved.local_path
            if local_path is None or not local_path.is_file():
                return None

            stat = local_path.stat()
            file_size = stat.st_size
            content_type, _ = mimetypes.guess_type(str(local_path))
            if content_type is None:
                content_type = "application/octet-stream"
            etag = f'"{stat.st_mtime_ns:x}-{file_size:x}"'
            last_modified = formatdate(stat.st_mtime, usegmt=True)

            self._asset_resolution_cache[cache_key] = {
                "local_path": local_path,
                "file_size": file_size,
                "mtime_ns": stat.st_mtime_ns,
                "content_type": content_type,
                "etag": etag,
                "last_modified": last_modified,
            }
            return local_path, file_size, content_type, etag, last_modified, False

        def _serve_asset(
            self,
            project_slug: str,
            timeline_ref: str,
            asset_key: str,
            *,
            head_only: bool = False,
        ) -> None:
            """Serve one asset with the frozen byte-serving semantics (§9).

            When the repository bridge is composed, the asset key resolves
            only from the persisted timeline registry; otherwise the legacy
            resolution path is kept for read-only compatibility fixtures.
            Both paths share the same wire semantics (200/206/304/416/400,
            HEAD, validators, OPTIONS).
            """
            if getattr(self.server, "bridge", None) is not None:
                self._serve_asset_from_persisted_registry(
                    project_slug, timeline_ref, asset_key, head_only=head_only
                )
                return
            self._serve_asset_legacy(
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
            """Serve an asset resolved from the persisted timeline registry.

            The registry comes from the repository bridge — never from a
            sidecar file or a filesystem scan (contract §9: a locator is a
            locator, never media identity). Safe-path rules reject absolute
            and traversing locators; HTTP locators are never local.
            """
            try:
                load = self._bridge().load_timeline(project_slug, timeline_ref)
            except BridgeError as exc:
                self._send_bridge_error(exc)
                return

            assets = load.registry.get("assets", {})
            entry = assets.get(asset_key)
            if not isinstance(entry, dict):
                self._send_error(
                    404,
                    "asset_not_found",
                    f"asset {asset_key!r} was not found in timeline {timeline_ref!r}",
                )
                return
            locator = entry.get("file")
            if not isinstance(locator, str) or not locator.strip():
                self._send_error(
                    404,
                    "asset_not_found",
                    f"asset {asset_key!r} has no file locator",
                )
                return
            locator = locator.strip()

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

            local_path = self._resolve_persisted_registry_local_path(
                project_slug, locator
            )
            if local_path is None:
                self._send_error(
                    404,
                    "asset_not_found",
                    f"asset {asset_key!r} was not found on disk",
                )
                return

            stat = local_path.stat()
            file_size = stat.st_size
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

        def _resolve_persisted_registry_local_path(
            self, project_slug: str, locator: str
        ) -> Path | None:
            """Resolve a safe relative locator under the project sources dir."""
            sources_root = sources_dir(project_slug, root=projects_root).resolve()
            candidate = (sources_root / locator).resolve()
            if not candidate.is_relative_to(sources_root):
                return None
            if not candidate.is_file():
                return None
            return candidate

        def _serve_asset_legacy(
            self,
            project_slug: str,
            timeline_ref: str,
            asset_key: str,
            *,
            head_only: bool = False,
        ) -> None:
            """Legacy resolution path for read-only compatibility fixtures."""
            project_slug = self._validate_project(project_slug)
            if project_slug is None:
                return
            timeline_ref = self._validate_timeline_ref(timeline_ref)
            if timeline_ref is None:
                return

            resolved = self._resolve_cached_asset(project_slug, timeline_ref, asset_key)
            if resolved is None:
                unresolved = resolve_bridge_asset(
                    project_slug,
                    timeline_ref,
                    asset_key,
                    root=projects_root,
                    sync_sources=False,
                )
                if unresolved is not None and unresolved.source_kind == "http":
                    self._send_error(
                        404,
                        "asset_not_local",
                        f"asset {asset_key!r} is not available as a local file",
                    )
                    return
                self._send_error(
                    404,
                    "asset_not_found",
                    f"asset {asset_key!r} was not found in timeline {timeline_ref!r}",
                )
                return

            local_path, file_size, content_type, etag, last_modified, _was_cached = resolved
            self._serve_resolved_asset(
                local_path,
                file_size,
                content_type,
                etag,
                last_modified,
                head_only=head_only,
            )

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
                    self._send_416(file_size)
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
                self._send_416(file_size)
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

        def _send_416(self, file_size: int) -> None:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{file_size}")
            self.send_header("Content-Type", "text/plain")
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

        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            parts = [part for part in unquote(path).split("/") if part]

            if parts == ["health"]:
                status = self._bridge().health(str(projects_root))
                self._send_json(200, status.to_dict())
                return

            if parts == ["projects"]:
                rows = [
                    row.to_dict() for row in self._bridge().list_projects()
                ]
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
                except Exception as exc:  # noqa: BLE001 - defensive 500
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

            self._send_error(404, "not_found", f"unknown POST route: {path}")

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

        def _validate_project(self, raw_project: str) -> str | None:
            try:
                project_slug = validate_project_slug(raw_project)
            except Exception:
                self._send_error(400, "invalid_project", f"invalid project slug: {raw_project!r}")
                return None

            if not (projects_root / project_slug / "project.json").is_file():
                self._send_error(404, "project_not_found", f"project {project_slug!r} was not found")
                return None
            return project_slug

        def _validate_timeline_ref(self, raw_timeline: str) -> str | None:
            try:
                validate_timeline_ulid(raw_timeline)
                return raw_timeline
            except Exception:
                pass

            try:
                validate_timeline_slug(raw_timeline)
                return raw_timeline
            except Exception:
                pass

            if _looks_like_uuid(raw_timeline):
                return raw_timeline

            self._send_error(400, "invalid_timeline", f"invalid timeline selector: {raw_timeline!r}")
            return None

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


def _looks_like_uuid(value: str) -> bool:
    parts = value.split("-")
    if len(parts) != 5:
        return False
    return all(parts) and all(all(char in "0123456789abcdefABCDEF" for char in part) for part in parts)
