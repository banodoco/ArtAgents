"""Generic human-gate HTTP server — see STAGE.md for the full contract."""


from __future__ import annotations


from astrid.packs._canonical_entrypoint import guard_canonical_entrypoint
guard_canonical_entrypoint('editorial.human_review')
import argparse
import json
import mimetypes
import os
import re
import secrets
import socket
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qs, urlparse

from astrid.packs.training.orchestrators.dataset_build.state import read_review_state, write_review_state


_GEMINI_SCHEMA_KEYS = {
    "type", "properties", "required", "items", "enum", "description",
    "nullable", "format", "minimum", "maximum", "minItems", "maxItems",
    "minLength", "maxLength", "pattern", "anyOf", "oneOf", "allOf",
}


class StaleStateConflict(Exception):
    """Raised when a save was based on an older review_state version."""


def _pick_free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _atomic_write(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(body)
    os.replace(tmp, path)


def _safe_under(root: Path, candidate: Path) -> bool:
    try:
        candidate.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _validate_against_schema(body: dict, schema_path: Path) -> tuple[bool, str]:
    try:
        import jsonschema  # type: ignore
    except ImportError:
        return True, "jsonschema not installed; validation skipped"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    if isinstance(schema, dict):
        schema = schema.get("schema", schema)
    try:
        jsonschema.validate(body, schema)
        return True, ""
    except jsonschema.ValidationError as exc:
        return False, str(exc)


def _read_json_file(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _filter_paginated_data(data_path: Path, query: dict[str, list[str]]) -> dict[str, Any]:
    raw = _read_json_file(data_path)
    items = raw.get("items", raw) if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        items = []
    status = (query.get("status") or [""])[0]
    if status:
        items = [item for item in items if isinstance(item, dict) and item.get("review_status", item.get("status")) == status]
    sampled = (query.get("sampled") or [""])[0]
    if sampled:
        items = [item for item in items if isinstance(item, dict) and _matches_sampled_filter(item, sampled)]
    total = len(items)
    offset = _non_negative_int((query.get("offset") or ["0"])[0], default=0)
    limit = _non_negative_int((query.get("limit") or [str(total)])[0], default=total)
    if limit == 0:
        page_items: list[Any] = []
    else:
        page_items = items[offset:offset + limit]
    return {
        "items": page_items,
        "total": total,
        "offset": offset,
        "limit": limit,
        "status": status or None,
        "sampled": sampled or None,
    }


def _non_negative_int(value: str, *, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(parsed, 0)


def _is_dataset_diff_save(body: Any) -> bool:
    return isinstance(body, dict) and "base_state_version" in body and "revisions" in body


def _apply_dataset_diff_save(state_path: Path, body: dict[str, Any]) -> dict[str, Any]:
    state = read_review_state(state_path)
    base_version = int(body.get("base_state_version", -1))
    current_version = int(state.get("state_version", 0))
    if base_version != current_version:
        raise StaleStateConflict(f"base_state_version {base_version} does not match current state_version {current_version}")
    decisions = dict(state.get("review_decisions") or {})
    for item_id, revision in _iter_revisions(body.get("revisions")):
        existing = dict(decisions.get(item_id) or {})
        decision = _normalize_decision(revision.get("decision", revision.get("review_status", existing.get("decision", "pending"))))
        merged = {
            "item_id": item_id,
            "decision": decision,
            "reject_reason": revision.get("reject_reason", existing.get("reject_reason")),
            "edited_caption": revision.get("edited_caption", existing.get("edited_caption")),
            "reviewed_at": revision.get("reviewed_at") or _now_iso(),
            "reviewer_id": revision.get("reviewer_id", existing.get("reviewer_id", "human_review")),
            "state_version": current_version + 1,
        }
        decisions[item_id] = merged
    state["review_decisions"] = decisions
    return write_review_state(state_path, state)


def _apply_dataset_batch_save(state_path: Path, data_path: Path, body: dict[str, Any]) -> dict[str, Any]:
    item_ids = _batch_item_ids(data_path, body)
    if not item_ids:
        raise ValueError("batch save matched no item_ids")
    decision = _normalize_decision(body.get("decision", body.get("review_status", "pending")))
    revisions = [
        {
            "item_id": item_id,
            "decision": decision,
            "reject_reason": body.get("reject_reason"),
            "edited_caption": body.get("edited_caption"),
            "reviewed_at": body.get("reviewed_at"),
            "reviewer_id": body.get("reviewer_id", "human_review_batch"),
        }
        for item_id in item_ids
    ]
    return _apply_dataset_diff_save(
        state_path,
        {
            "base_state_version": body.get("base_state_version"),
            "revisions": revisions,
        },
    )


def _batch_item_ids(data_path: Path, body: Mapping[str, Any]) -> list[str]:
    item_ids = body.get("item_ids")
    if isinstance(item_ids, list) and item_ids:
        return [str(item_id) for item_id in item_ids if item_id is not None]
    scope = str(body.get("scope", ""))
    if scope != "filtered":
        raise ValueError("batch save requires item_ids or scope='filtered'")
    status = body.get("status")
    filter_config = body.get("filter") if isinstance(body.get("filter"), Mapping) else {}
    if status is None:
        status = filter_config.get("status")
    sampled = body.get("sampled")
    if sampled is None:
        sampled = filter_config.get("sampled")
    items = _items_from_data(data_path)
    if status:
        items = [
            item
            for item in items
            if str(item.get("review_status", item.get("status", ""))) == str(status)
        ]
    if sampled is not None and str(sampled) != "":
        items = [item for item in items if _matches_sampled_filter(item, str(sampled))]
    return [str(item["item_id"]) for item in items if item.get("item_id") is not None]


def _items_from_data(data_path: Path) -> list[dict[str, Any]]:
    raw = _read_json_file(data_path)
    items = raw.get("items", raw) if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        return []
    return [dict(item) for item in items if isinstance(item, dict)]


def _matches_sampled_filter(item: Mapping[str, Any], expected: str) -> bool:
    normalized = str(expected).strip().lower()
    if normalized not in {"true", "false", "1", "0", "yes", "no"}:
        return True
    marker = item.get("review_sampled")
    if isinstance(marker, Mapping):
        sampled = bool(marker.get("sampled", True))
    elif marker is None:
        sampled = True
    else:
        sampled = bool(marker)
    expected_bool = normalized in {"true", "1", "yes"}
    return sampled is expected_bool


def _iter_revisions(revisions: Any):
    if isinstance(revisions, dict):
        for item_id, revision in revisions.items():
            if isinstance(revision, dict):
                yield str(item_id), revision
        return
    if isinstance(revisions, list):
        for revision in revisions:
            if isinstance(revision, dict) and revision.get("item_id") is not None:
                yield str(revision["item_id"]), revision


def _normalize_decision(value: Any) -> str:
    if value in {"accepted", "accept", True}:
        return "accept"
    if value in {"rejected", "reject", False}:
        return "reject"
    return "pending"


def _now_iso() -> str:
    from astrid.core.util.time import utc_now_iso

    return utc_now_iso()


def make_handler_class(*, html_path: Path, data_path: Path, state_path: Path | None,
                       out_path: Path, schema_path: Path | None, mounts: dict[str, Path],
                       token: str, shutdown_event: threading.Event):
    """Closure-based request handler with all config baked in."""

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            # Silence default access log; keep stderr clean
            return

        # ── helpers ────────────────────────────────────────────────────
        def _send(self, status: int, body: bytes = b"", content_type: str = "text/plain", extra_headers: dict | None = None):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for k, v in (extra_headers or {}).items():
                self.send_header(k, v)
            self.end_headers()
            if body:
                self.wfile.write(body)

        def _send_json(self, status: int, payload: dict):
            self._send(status, json.dumps(payload).encode("utf-8"), "application/json")

        def _token_ok(self) -> bool:
            url = urlparse(self.path)
            qs = parse_qs(url.query)
            t = (qs.get("token", [""])[0]) or self.headers.get("X-Session-Token", "")
            return t == token

        def _serve_file(self, path: Path, content_type: str | None = None):
            if not path.is_file():
                self._send(404, b"Not found")
                return
            ctype = content_type or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            data = path.read_bytes()
            # Range request support (mp4 seek)
            range_hdr = self.headers.get("Range", "")
            m = re.match(r"bytes=(\d+)-(\d*)", range_hdr)
            if m:
                start = int(m.group(1))
                end = int(m.group(2)) if m.group(2) else len(data) - 1
                end = min(end, len(data) - 1)
                chunk = data[start:end + 1]
                self.send_response(206)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Range", f"bytes {start}-{end}/{len(data)}")
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Length", str(len(chunk)))
                self.end_headers()
                self.wfile.write(chunk)
                return
            self._send(200, data, ctype, {"Accept-Ranges": "bytes"})

        # ── GET ───────────────────────────────────────────────────────
        def do_GET(self):  # noqa: N802
            url = urlparse(self.path)
            p = url.path

            # / → html_path (file or dir/index.html)
            if p == "/" or p == "":
                target = html_path if html_path.is_file() else (html_path / "index.html")
                self._serve_file(target, "text/html; charset=utf-8")
                return

            # /data.json
            if p == "/data.json":
                if url.query:
                    self._send_json(200, _filter_paginated_data(data_path, parse_qs(url.query)))
                    return
                self._serve_file(data_path, "application/json")
                return

            # /state.json (token required)
            if p == "/state.json":
                if not self._token_ok():
                    self._send(403, b"Forbidden")
                    return
                if state_path and state_path.is_file():
                    self._serve_file(state_path, "application/json")
                else:
                    self._send(404, b"No state file")
                return

            # /<prefix>/... static mounts
            for prefix, root in mounts.items():
                if p == prefix or p.startswith(prefix + "/"):
                    relative = p[len(prefix):].lstrip("/")
                    candidate = (root / relative).resolve()
                    if not _safe_under(root, candidate):
                        self._send(403, b"Forbidden (path escape)")
                        return
                    self._serve_file(candidate)
                    return

            # html_path is a directory → maybe serve from there
            if html_path.is_dir():
                candidate = (html_path / p.lstrip("/")).resolve()
                if _safe_under(html_path, candidate) and candidate.is_file():
                    self._serve_file(candidate)
                    return

            self._send(404, b"Not found")

        # ── POST ──────────────────────────────────────────────────────
        def do_POST(self):  # noqa: N802
            if not self._token_ok():
                self._send_json(403, {"error": "forbidden", "detail": "missing or invalid session token"})
                return

            url = urlparse(self.path)
            length = int(self.headers.get("Content-Length", "0") or 0)
            raw = self.rfile.read(length) if length > 0 else b""

            if url.path == "/save":
                if state_path is None:
                    self._send_json(400, {"error": "no_state", "detail": "--state not configured"})
                    return
                try:
                    body = json.loads(raw.decode("utf-8") or "{}")
                except Exception as exc:
                    self._send_json(400, {"error": "bad_json", "detail": str(exc)})
                    return
                if _is_dataset_diff_save(body):
                    try:
                        updated = _apply_dataset_diff_save(state_path, body)
                    except StaleStateConflict as exc:
                        self._send_json(409, {"error": "stale_state", "detail": str(exc)})
                        return
                    except Exception as exc:  # noqa: BLE001 - return JSON instead of killing handler thread
                        self._send_json(400, {"error": "save_failed", "detail": str(exc)})
                        return
                    self._send_json(200, {"state_version": updated["state_version"], "updated_at": updated["updated_at"]})
                    return
                self._send_json(
                    400,
                    {
                        "error": "diff_required",
                        "detail": "/save requires a JSON object with base_state_version and revisions",
                    },
                )
                return

            if url.path == "/submit-batch":
                if state_path is None:
                    self._send_json(400, {"error": "no_state", "detail": "--state not configured"})
                    return
                try:
                    body = json.loads(raw.decode("utf-8") or "{}")
                except Exception as exc:
                    self._send_json(400, {"error": "bad_json", "detail": str(exc)})
                    return
                if not isinstance(body, dict) or "base_state_version" not in body:
                    self._send_json(
                        400,
                        {
                            "error": "base_state_version_required",
                            "detail": "/submit-batch requires base_state_version",
                        },
                    )
                    return
                try:
                    updated = _apply_dataset_batch_save(state_path, data_path, body)
                except StaleStateConflict as exc:
                    self._send_json(409, {"error": "stale_state", "detail": str(exc)})
                    return
                except Exception as exc:  # noqa: BLE001 - return JSON instead of killing handler thread
                    self._send_json(400, {"error": "batch_failed", "detail": str(exc)})
                    return
                self._send_json(200, {"state_version": updated["state_version"], "updated_at": updated["updated_at"]})
                return

            if url.path == "/submit":
                try:
                    body = json.loads(raw.decode("utf-8") or "{}")
                except Exception as exc:
                    self._send_json(400, {"error": "bad_json", "detail": str(exc)})
                    return
                if schema_path is not None:
                    ok, err = _validate_against_schema(body, schema_path)
                    if not ok:
                        self._send_json(400, {"error": "schema_violation", "detail": err})
                        return
                _atomic_write(out_path, raw)
                self._send(204)
                shutdown_event.set()
                return

            self._send(404, b"Not found")

    return Handler


_OPTIONAL_SENTINELS = {"", "__none__", "none", "None", "null"}


def _optional_path(value: Path | None) -> Path | None:
    if value is None or str(value) in _OPTIONAL_SENTINELS:
        return None
    return value


def _parse_mounts(values: list[str]) -> dict[str, Path]:
    out: dict[str, Path] = {}
    for v in values or []:
        if v in _OPTIONAL_SENTINELS:
            continue
        if "=" not in v:
            raise SystemExit(f"--serve expects PREFIX=DIR, got: {v}")
        prefix, root = v.split("=", 1)
        if not prefix.startswith("/"):
            prefix = "/" + prefix
        out[prefix.rstrip("/")] = Path(root).resolve()
    return out


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--html", type=Path, required=True)
    p.add_argument("--data", type=Path, required=True)
    p.add_argument("--serve", action="append", default=[])
    p.add_argument("--state", type=Path)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--response-schema", type=Path)
    p.add_argument("--port", type=int, default=0)
    p.add_argument("--no-open", action="store_true")
    p.add_argument("--timeout", type=int, default=0)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if not args.html.exists():
        print(f"Error: --html not found: {args.html}", file=sys.stderr)
        return 2
    if not args.data.is_file():
        print(f"Error: --data not found: {args.data}", file=sys.stderr)
        return 2

    args.state = _optional_path(args.state)
    args.response_schema = _optional_path(args.response_schema)
    mounts = _parse_mounts(args.serve)
    args.out.parent.mkdir(parents=True, exist_ok=True)

    port = args.port if args.port else _pick_free_port()
    token = secrets.token_hex(16)
    shutdown_event = threading.Event()

    handler = make_handler_class(
        html_path=args.html.resolve(),
        data_path=args.data.resolve(),
        state_path=args.state.resolve() if args.state else None,
        out_path=args.out.resolve(),
        schema_path=args.response_schema.resolve() if args.response_schema else None,
        mounts=mounts,
        token=token,
        shutdown_event=shutdown_event,
    )

    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    url = f"http://127.0.0.1:{port}/?token={token}"

    print(f"human_review: serving at {url}", flush=True)
    print(f"human_review: token={token}", flush=True)

    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    if not args.no_open:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    start_t = time.time()
    while not shutdown_event.is_set():
        if args.timeout and (time.time() - start_t) >= args.timeout:
            print(f"human_review: timeout after {args.timeout}s without /submit", file=sys.stderr)
            server.shutdown()
            return 3
        time.sleep(0.25)

    server.shutdown()
    print(f"human_review: submit received, wrote {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
