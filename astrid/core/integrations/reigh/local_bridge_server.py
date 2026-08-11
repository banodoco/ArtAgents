"""HTTP surface for the Astrid local read/write bridge."""

from __future__ import annotations

import json
import mimetypes
import os
import re
import time
from email.utils import formatdate
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, ClassVar
from urllib.parse import unquote, urlparse

from astrid.core.foundation.project_paths import validate_project_slug
from astrid.core.integrations.reigh.local_bridge import (
    BridgeTimelineRecord,
    _build_source_summary,
    ensure_bridge_audio_proxy,
    ensure_bridge_video_proxy,
    get_bridge_audio_proxy_status,
    get_bridge_video_proxy_status,
    list_bridge_checkpoints,
    list_bridge_projects,
    list_bridge_timelines,
    load_bridge_sources,
    load_bridge_timeline,
    resolve_bridge_asset,
    resolve_bridge_projects_root,
    save_bridge_registry,
    save_bridge_timeline,
)
from astrid.core.timeline.eventlog.types import EventLogStaleVersionError
from astrid.core.timeline.paths import validate_timeline_slug, validate_timeline_ulid

_RANGE_RE = re.compile(r"^bytes\s*=\s*(\d*)\s*-\s*(\d*)\s*$")
_RANGELESS_FULL_BODY_LIMIT_BYTES = 64 * 1024 * 1024
_RANGELESS_INITIAL_CHUNK_BYTES = 1024 * 1024
_OPEN_ENDED_RANGE_CHUNK_BYTES = 4 * 1024 * 1024
_DIAGNOSTICS_ENABLED = os.environ.get("ASTRID_BRIDGE_DIAGNOSTICS", "0") != "0"


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
        _ALLOWED_METHODS = "GET, HEAD, POST, PUT, OPTIONS"
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

        def _serve_audio_proxy(
            self,
            project_slug: str,
            source_id: str,
            *,
            head_only: bool = False,
        ) -> None:
            proxy = get_bridge_audio_proxy_status(project_slug, source_id, root=projects_root)
            if proxy is None:
                self._send_error(
                    404, "source_not_found", f"source {source_id!r} was not found",
                )
                return

            if proxy.status != "ready":
                self._send_json(200, _serialize_audio_proxy_status(proxy))
                return

            proxy_path = proxy.output_path
            if proxy_path is None or not proxy_path.is_file():
                payload = _serialize_audio_proxy_status(proxy)
                payload["status"] = "missing"
                payload["error"] = "ready proxy file is missing"
                self._send_json(200, payload)
                return

            self._serve_file(
                proxy_path,
                content_type="audio/mp4",
                cache_control="private, no-cache",
                head_only=head_only,
            )

        def _serve_video_proxy(
            self,
            project_slug: str,
            source_id: str,
            *,
            head_only: bool = False,
        ) -> None:
            proxy = get_bridge_video_proxy_status(project_slug, source_id, root=projects_root)
            if proxy is None:
                self._send_error(
                    404, "source_not_found", f"source {source_id!r} was not found",
                )
                return

            if proxy.status != "ready":
                self._send_json(200, _serialize_video_proxy_status(proxy))
                return

            proxy_path = proxy.output_path
            if proxy_path is None or not proxy_path.is_file():
                payload = _serialize_video_proxy_status(proxy)
                payload["status"] = "missing"
                payload["error"] = "ready proxy file is missing"
                self._send_json(200, payload)
                return

            self._serve_file(
                proxy_path,
                content_type="video/mp4",
                cache_control="private, no-cache",
                head_only=head_only,
            )

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
            """Serve a local asset file with full Range support.

            200 — full file body with Accept-Ranges + Content-Type.
            206 — single byte range with Content-Range.
            416 — unsatisfiable range (start >= file size, etc.).
            404 — asset key not in registry, file missing, or HTTP-only.
            """
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
                    404, "asset_not_found",
                    f"asset {asset_key!r} was not found in timeline {timeline_ref!r}",
                )
                return

            local_path, file_size, content_type, etag, last_modified, _was_cached = resolved

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

        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            parts = [part for part in unquote(path).split("/") if part]

            if parts == ["health"]:
                self._send_json(200, {
                    "ok": True,
                    "projects_root": str(projects_root),
                })
                return

            if parts == ["projects"]:
                self._send_json(200, {"projects": list_bridge_projects(projects_root)})
                return

            if len(parts) == 3 and parts[0] == "projects" and parts[2] == "sources":
                project_slug = self._validate_project(parts[1])
                if project_slug is None:
                    return
                sources_payload = load_bridge_sources(project_slug, root=projects_root)
                summaries = {
                    sid: _build_source_summary(entry, sid)
                    for sid, entry in sources_payload.get("sources", {}).items()
                }
                self._send_json(200, {
                    "project": project_slug,
                    "version": sources_payload.get("version"),
                    "sources": summaries,
                })
                return

            if (
                len(parts) == 5
                and parts[0] == "projects"
                and parts[2] == "sources"
                and parts[4] == "audio-proxy"
            ):
                project_slug = self._validate_project(parts[1])
                if project_slug is None:
                    return
                self._serve_audio_proxy(project_slug, parts[3])
                return

            if (
                len(parts) == 5
                and parts[0] == "projects"
                and parts[2] == "sources"
                and parts[4] == "video-proxy"
            ):
                project_slug = self._validate_project(parts[1])
                if project_slug is None:
                    return
                self._serve_video_proxy(project_slug, parts[3])
                return

            if len(parts) == 3 and parts[0] == "projects" and parts[2] == "timelines":
                project_slug = self._validate_project(parts[1])
                if project_slug is None:
                    return
                rows = list_bridge_timelines(project_slug, root=projects_root)
                self._send_json(200, {
                    "project": project_slug,
                    "timelines": [_serialize_timeline_row(row) for row in rows],
                })
                return

            if len(parts) == 4 and parts[0] == "projects" and parts[2] == "timelines":
                project_slug = self._validate_project(parts[1])
                if project_slug is None:
                    return
                timeline_ref = self._validate_timeline_ref(parts[3])
                if timeline_ref is None:
                    return
                payload = load_bridge_timeline(project_slug, timeline_ref, root=projects_root)
                if payload is None:
                    self._send_error(404, "timeline_not_found", f"timeline {timeline_ref!r} was not found")
                    return
                self._send_json(200, payload)
                return

            if (
                len(parts) == 5
                and parts[0] == "projects"
                and parts[2] == "timelines"
                and parts[4] == "checkpoints"
            ):
                project_slug = self._validate_project(parts[1])
                if project_slug is None:
                    return
                timeline_ref = self._validate_timeline_ref(parts[3])
                if timeline_ref is None:
                    return
                checkpoints = list_bridge_checkpoints(project_slug, timeline_ref, root=projects_root)
                if checkpoints is None:
                    self._send_error(404, "timeline_not_found", f"timeline {timeline_ref!r} was not found")
                    return
                self._send_json(200, {"checkpoints": checkpoints})
                return

            # ---- Asset endpoint ----
            if (
                len(parts) == 6
                and parts[0] == "projects"
                and parts[2] == "timelines"
                and parts[4] == "assets"
            ):
                project_slug = self._validate_project(parts[1])
                if project_slug is None:
                    return
                timeline_ref = self._validate_timeline_ref(parts[3])
                if timeline_ref is None:
                    return
                self._serve_asset(project_slug, timeline_ref, parts[5])
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
                project_slug = self._validate_project(parts[1])
                if project_slug is None:
                    return
                timeline_ref = self._validate_timeline_ref(parts[3])
                if timeline_ref is None:
                    return
                self._serve_asset(project_slug, timeline_ref, parts[5], head_only=True)
                return

            if (
                len(parts) == 5
                and parts[0] == "projects"
                and parts[2] == "sources"
                and parts[4] == "audio-proxy"
            ):
                project_slug = self._validate_project(parts[1])
                if project_slug is None:
                    return
                self._serve_audio_proxy(project_slug, parts[3], head_only=True)
                return

            if (
                len(parts) == 5
                and parts[0] == "projects"
                and parts[2] == "sources"
                and parts[4] == "video-proxy"
            ):
                project_slug = self._validate_project(parts[1])
                if project_slug is None:
                    return
                self._serve_video_proxy(project_slug, parts[3], head_only=True)
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
                project_slug = self._validate_project(parts[1])
                if project_slug is None:
                    return
                timeline_ref = self._validate_timeline_ref(parts[3])
                if timeline_ref is None:
                    return
                body = self._read_request_body()
                if body is None:
                    self._send_error(400, "invalid_body", "request body must be valid JSON")
                    return
                config = body.get("config")
                if not isinstance(config, dict):
                    self._send_error(400, "invalid_config", "body must contain a 'config' object")
                    return
                registry = body.get("registry")
                if not isinstance(registry, dict):
                    self._send_error(400, "invalid_registry", "body must contain a 'registry' object")
                    return
                expected_version = body.get("expected_version")
                if not isinstance(expected_version, int):
                    self._send_error(400, "invalid_expected_version", "body must contain an integer 'expected_version'")
                    return
                try:
                    result = save_bridge_timeline(
                        project_slug,
                        timeline_ref,
                        config,
                        registry=registry,
                        expected_version=expected_version,
                        root=projects_root,
                    )
                except EventLogStaleVersionError as exc:
                    backend_head = self._get_head_version(project_slug, timeline_ref)
                    self._send_json(409, {
                        "error": "timeline_version_conflict",
                        "detail": str(exc),
                        "config_version": backend_head,
                    })
                    return
                if result is None:
                    self._send_error(404, "timeline_not_found", f"timeline {timeline_ref!r} was not found")
                    return
                self._send_json(200, result)
                return

            # POST /projects/:project/sources/:sourceId/audio-proxy/ensure
            if (
                len(parts) == 6
                and parts[0] == "projects"
                and parts[2] == "sources"
                and parts[4] == "audio-proxy"
                and parts[5] == "ensure"
            ):
                project_slug = self._validate_project(parts[1])
                if project_slug is None:
                    return
                body = self._read_optional_request_body()
                if body is None:
                    self._send_error(400, "invalid_body", "request body must be valid JSON")
                    return
                background = body.get("background", True)
                if not isinstance(background, bool):
                    self._send_error(400, "invalid_proxy_request", "background must be a boolean when provided")
                    return
                result = ensure_bridge_audio_proxy(
                    project_slug,
                    parts[3],
                    root=projects_root,
                    background=background,
                )
                if result is None:
                    self._send_error(404, "source_not_found", f"source {parts[3]!r} was not found")
                    return
                self._send_json(200, _serialize_audio_proxy_status(result))
                return

            # POST /projects/:project/sources/:sourceId/video-proxy/ensure
            if (
                len(parts) == 6
                and parts[0] == "projects"
                and parts[2] == "sources"
                and parts[4] == "video-proxy"
                and parts[5] == "ensure"
            ):
                project_slug = self._validate_project(parts[1])
                if project_slug is None:
                    return
                body = self._read_optional_request_body()
                if body is None:
                    self._send_error(400, "invalid_body", "request body must be valid JSON")
                    return
                background = body.get("background", True)
                if not isinstance(background, bool):
                    self._send_error(400, "invalid_proxy_request", "background must be a boolean when provided")
                    return
                result = ensure_bridge_video_proxy(
                    project_slug,
                    parts[3],
                    root=projects_root,
                    background=background,
                )
                if result is None:
                    self._send_error(404, "source_not_found", f"source {parts[3]!r} was not found")
                    return
                self._send_json(200, _serialize_video_proxy_status(result))
                return

            self._send_error(404, "not_found", f"unknown POST route: {path}")

        # ------------------------------------------------------------------
        # PUT — replace registry
        # ------------------------------------------------------------------

        def do_PUT(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            parts = [part for part in unquote(path).split("/") if part]

            # PUT /projects/:project/timelines/:timeline/registry
            if (
                len(parts) == 5
                and parts[0] == "projects"
                and parts[2] == "timelines"
                and parts[4] == "registry"
            ):
                project_slug = self._validate_project(parts[1])
                if project_slug is None:
                    return
                timeline_ref = self._validate_timeline_ref(parts[3])
                if timeline_ref is None:
                    return
                body = self._read_request_body()
                if body is None:
                    self._send_error(400, "invalid_body", "request body must be valid JSON")
                    return
                registry = body.get("registry")
                if not isinstance(registry, dict) or not isinstance(registry.get("assets"), dict):
                    self._send_error(400, "invalid_registry", "body must contain a 'registry' object with an 'assets' dict")
                    return
                expected_version = body.get("expected_version")
                if not isinstance(expected_version, int):
                    self._send_error(400, "invalid_expected_version", "body must contain an integer 'expected_version'")
                    return
                # Normalize: ensure all asset entries are dicts with string keys
                normalized: dict[str, dict[str, Any]] = {}
                for key, entry in registry["assets"].items():
                    if not isinstance(key, str) or not isinstance(entry, dict):
                        continue
                    normalized[key] = dict(entry)
                try:
                    registry_payload = save_bridge_registry(
                        project_slug,
                        timeline_ref,
                        {"assets": normalized},
                        expected_version=expected_version,
                        root=projects_root,
                    )
                except EventLogStaleVersionError as exc:
                    backend_head = self._get_head_version(project_slug, timeline_ref)
                    self._send_json(409, {
                        "error": "timeline_version_conflict",
                        "detail": str(exc),
                        "config_version": backend_head,
                    })
                    return
                if registry_payload is None:
                    self._send_error(404, "timeline_not_found", f"timeline {timeline_ref!r} was not found")
                    return
                self._send_json(200, registry_payload)
                return

            self._send_error(404, "not_found", f"unknown PUT route: {path}")

        # ------------------------------------------------------------------
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

        def _get_head_version(self, project_slug: str, timeline_ref: str) -> int:
            """Return the current event-log head version for a timeline, or 0 on failure."""
            from astrid.core.integrations.reigh.local_bridge import find_bridge_timeline
            from astrid.core.timeline.eventlog import LocalFsBackend

            try:
                record = find_bridge_timeline(project_slug, timeline_ref, root=projects_root)
                if record is None:
                    return 0
                backend = LocalFsBackend(
                    timeline_id=record.timeline_id,
                    timeline_home=record.timeline_home,
                )
                return backend.head().version
            except Exception:
                return 0

    return Handler


def _serialize_timeline_row(row: BridgeTimelineRecord) -> dict[str, Any]:
    return {
        "timeline_id": row.timeline_id,
        "timeline_ulid": row.timeline_ulid,
        "slug": row.slug,
        "name": row.name,
        "is_default": row.is_default,
    }


def _serialize_audio_proxy_status(proxy: Any) -> dict[str, Any]:
    payload = {
        "sourceId": proxy.source_id,
        "sourceVersion": proxy.source_version,
        "status": proxy.status,
        "profileVersion": proxy.profile_version,
        "output": proxy.output,
    }
    if proxy.error:
        payload["error"] = proxy.error
    return payload


def _serialize_video_proxy_status(proxy: Any) -> dict[str, Any]:
    payload = {
        "sourceId": proxy.source_id,
        "sourceVersion": proxy.source_version,
        "status": proxy.status,
        "profileVersion": proxy.profile_version,
        "output": proxy.output,
    }
    if proxy.error:
        payload["error"] = proxy.error
    return payload


def _looks_like_uuid(value: str) -> bool:
    parts = value.split("-")
    if len(parts) != 5:
        return False
    return all(parts) and all(all(char in "0123456789abcdefABCDEF" for char in part) for part in parts)
