"""HTTP surface for the Astrid local read bridge."""

from __future__ import annotations

import json
import mimetypes
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from astrid.core.foundation.project_paths import validate_project_slug
from astrid.core.integrations.reigh.local_bridge import (
    BridgeTimelineRecord,
    list_bridge_projects,
    list_bridge_timelines,
    load_bridge_timeline,
    resolve_bridge_asset,
    resolve_bridge_projects_root,
)
from astrid.core.timeline.paths import validate_timeline_slug, validate_timeline_ulid

_RANGE_RE = re.compile(r"^bytes\s*=\s*(\d*)\s*-\s*(\d*)\s*$")


def create_local_bridge_server(
    *,
    projects_root: str | Path | None = None,
    host: str = "127.0.0.1",
    port: int = 0,
) -> ThreadingHTTPServer:
    """Create a bridge HTTP server bound to the requested host/port."""
    resolved_root = resolve_bridge_projects_root(projects_root)
    handler = make_local_bridge_handler(projects_root=resolved_root)
    return ThreadingHTTPServer((host, port), handler)


def make_local_bridge_handler(*, projects_root: Path):
    """Build a request handler bound to one resolved projects root."""

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, _fmt: str, *_args: Any) -> None:
            return

        def _send_json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
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

        def _serve_asset(
            self,
            project_slug: str,
            timeline_ref: str,
            asset_key: str,
        ) -> None:
            """Serve a local asset file with full Range support.

            200 — full file body with Accept-Ranges + Content-Type.
            206 — single byte range with Content-Range.
            416 — unsatisfiable range (start >= file size, etc.).
            404 — asset key not in registry, file missing, or HTTP-only.
            """
            resolved = resolve_bridge_asset(
                project_slug, timeline_ref, asset_key, root=projects_root,
            )
            if resolved is None:
                self._send_error(
                    404, "asset_not_found",
                    f"asset {asset_key!r} was not found in timeline {timeline_ref!r}",
                )
                return

            if resolved.source_kind == "http":
                self._send_error(
                    404, "asset_not_local",
                    f"asset {asset_key!r} is an HTTP reference, not a local file",
                )
                return

            local_path = resolved.local_path
            if local_path is None or not local_path.is_file():
                self._send_error(
                    404, "asset_file_missing",
                    f"file for asset {asset_key!r} does not exist on disk",
                )
                return

            file_size = local_path.stat().st_size

            content_type, _ = mimetypes.guess_type(str(local_path))
            if content_type is None:
                content_type = "application/octet-stream"

            range_header = self.headers.get("Range")
            if range_header is None:
                # ---- 200 full response ----
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(file_size))
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                with local_path.open("rb") as fh:
                    while True:
                        chunk = fh.read(65536)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
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
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(content_len))
            self.send_header(
                "Content-Range",
                f"bytes {range_start}-{range_end}/{file_size}",
            )
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()

            with local_path.open("rb") as fh:
                fh.seek(range_start)
                remaining = content_len
                while remaining > 0:
                    chunk = fh.read(min(65536, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)

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


def _serialize_timeline_row(row: BridgeTimelineRecord) -> dict[str, Any]:
    return {
        "timeline_id": row.timeline_id,
        "timeline_ulid": row.timeline_ulid,
        "slug": row.slug,
        "name": row.name,
        "is_default": row.is_default,
    }


def _looks_like_uuid(value: str) -> bool:
    parts = value.split("-")
    if len(parts) != 5:
        return False
    return all(parts) and all(all(char in "0123456789abcdefABCDEF" for char in part) for part in parts)
