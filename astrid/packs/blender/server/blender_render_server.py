#!/usr/bin/env python3
"""Blender render HTTP API.

A small, dependency-free (stdlib only) HTTP service that renders Blender scenes
on demand. Lives on a render host (a Hetzner box, a RunPod GPU pod, or any
machine with ``blender`` installed). Designed to be copied alongside
``render_core.py`` and run under systemd or as a background process — it has no
Astrid/Flask dependencies so the host does not need an Astrid install.

Endpoints
---------
``GET  /health``          -> ``{"status":"ok","blender":"<ver>","gpu":<bool>}``
``POST /render``          -> rendered file bytes (image/png or video/mp4)

``POST /render`` accepts a JSON body::

    {
      "scene": {...},          # optional declarative scene spec (see render_core.DEFAULT_SCENE)
      "blend_b64": "...",      # optional base64 .blend file (overrides scene)
      "blend_name": "x.blend", # filename hint when blend_b64 is set
      "settings": {            # optional render settings (see render_core.DEFAULT_SETTINGS)
        "engine": "cycles", "device": "cpu", "samples": 64,
        "resolution": [1280,720], "frames": 1, "fps": 24, "format": "png"
      }
    }

A still (``frames == 1``) returns a PNG. An animation (``frames > 1``) returns an
mp4 (PNG sequence encoded with ffmpeg). Response headers carry ``X-Render-Ms``,
``X-Blender-Engine``, ``X-Blender-Version`` and ``X-Output-Type``.

Auth: if ``BLENDER_RENDER_TOKEN`` is set, requests must send
``Authorization: Bearer <token>``.
"""

from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
import zipfile
import traceback
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

# render_core is a sibling module (stdlib-only); allow running from the server
# directory without an Astrid install.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render_core  # noqa: E402

BLENDER_EXEC = os.environ.get("BLENDER_EXEC", "blender")
FFMPEG_EXEC = os.environ.get("FFMPEG_EXEC", "ffmpeg")
RENDER_TIMEOUT = int(os.environ.get("BLENDER_RENDER_TIMEOUT", "1800"))
MAX_BODY_BYTES = int(os.environ.get("BLENDER_MAX_BODY_MB", "512")) * 1024 * 1024
AUTH_TOKEN = os.environ.get("BLENDER_RENDER_TOKEN", "").strip()
HOST = os.environ.get("BLENDER_RENDER_HOST", "0.0.0.0")
PORT = int(os.environ.get("BLENDER_RENDER_PORT", "8778"))

_RENDER_SEMAPHORE = threading.Semaphore(int(os.environ.get("BLENDER_RENDER_CONCURRENCY", "2")))

# Cache the blender version (cheap, but avoid repeated subprocess spawns).
_BLENDER_VERSION_CACHE: list[str | None] = [None]


def blender_version() -> str | None:
    if _BLENDER_VERSION_CACHE[0] is not None:
        return _BLENDER_VERSION_CACHE[0]
    try:
        out = subprocess.run(
            [BLENDER_EXEC, "--version"], capture_output=True, text=True, timeout=30
        )
        first = (out.stdout or out.stderr).splitlines()[0].strip() if (out.stdout or out.stderr) else ""
        _BLENDER_VERSION_CACHE[0] = first or None
    except Exception:
        _BLENDER_VERSION_CACHE[0] = None
    return _BLENDER_VERSION_CACHE[0]


def has_gpu() -> bool:
    """Best-effort GPU detection (nvidia-smi present)."""
    return shutil.which("nvidia-smi") is not None


def _download(url: str, dest_path: str, timeout: int = 300) -> None:
    """Download ``url`` to ``dest_path`` (streaming)."""
    with urllib.request.urlopen(url, timeout=timeout) as resp, open(dest_path, "wb") as fh:
        shutil.copyfileobj(resp, fh)


def _find_model_file(directory: str) -> str | None:
    """Find a renderable model file (.gltf/.glb/.fbx) under ``directory``."""
    priorities = (".glb", ".gltf", ".fbx")
    found: dict[str, str] = {}
    for root, _dirs, files in os.walk(directory):
        for name in files:
            low = name.lower()
            for ext in priorities:
                if low.endswith(ext):
                    found.setdefault(ext, os.path.join(root, name))
    for ext in priorities:
        if ext in found:
            return found[ext]
    return None


def _resolve_mesh_in_workdir(mesh_url: str, work_dir: str) -> str:
    """Download ``mesh_url`` into ``work_dir``; extract archives; return model path."""
    parsed = urllib.parse.urlparse(mesh_url)
    url_ext = ""
    path_lower = (parsed.path or "").lower()
    for ext in (".glb", ".gltf", ".fbx", ".zip"):
        if path_lower.endswith(ext):
            url_ext = ext
            break
    if url_ext in ("", ".zip"):
        archive = os.path.join(work_dir, "mesh.zip" if url_ext == ".zip" else "mesh.bin")
        _download(mesh_url, archive)
        if zipfile.is_zipfile(archive):
            with zipfile.ZipFile(archive) as zf:
                zf.extractall(work_dir)
            model = _find_model_file(work_dir)
            if not model:
                raise RuntimeError("downloaded archive contained no .gltf/.glb/.fbx")
            return model
        # not a zip but no recognizable ext — guess glb
        guessed = os.path.join(work_dir, "mesh.glb")
        os.rename(archive, guessed)
        return guessed
    dest = os.path.join(work_dir, "mesh" + url_ext)
    _download(mesh_url, dest)
    return dest


def _run_blender(script_path: str, blend_path: str | None, work_dir: str) -> tuple[int, str, str]:
    argv = [BLENDER_EXEC, "-b", "--factory-startup"]
    if blend_path:
        argv.append(blend_path)
    argv += ["-P", script_path]
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=RENDER_TIMEOUT)
    return proc.returncode, proc.stdout, proc.stderr


def _encode_animation(frame_dir: str, out_path: str, fps: int) -> None:
    pattern = render_core.frame_pattern(frame_dir)
    cmd = render_core.ffmpeg_encode_command(pattern, out_path, fps=fps)
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=RENDER_TIMEOUT)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg encode failed ({proc.returncode}): {proc.stderr[-2000:]}")


def do_render(payload: dict[str, Any], work_dir: str) -> dict[str, Any]:
    """Render per ``payload``. Returns a dict with result metadata + output path."""
    settings = render_core.normalize_settings(payload.get("settings"))
    frames = int(settings.get("frames", 1))
    animation = frames > 1
    blend_path: str | None = None
    script_path: str
    script_body = payload.get("script")

    if script_body:
        # Generic render preset (built client-side in astrid.packs.blender.renders).
        # Fill the mesh/output placeholders, download the mesh if one is supplied.
        if frames <= 1:
            frames = 48
            settings["frames"] = 48
        animation = True
        mesh_file = ""
        if payload.get("mesh_url"):
            mesh_file = _resolve_mesh_in_workdir(payload["mesh_url"], work_dir)
        full = script_body.replace("__MESH_FILE__", repr(mesh_file)).replace("__OUTPUT__", repr(work_dir))
        script_path = os.path.join(work_dir, "render_preset.py")
        Path(script_path).write_text(full, encoding="utf-8")
    elif payload.get("blend_b64"):
        blend_name = payload.get("blend_name") or "scene.blend"
        blend_path = os.path.join(work_dir, os.path.basename(blend_name))
        with open(blend_path, "wb") as fh:
            fh.write(base64.b64decode(payload["blend_b64"]))
        script_path = os.path.join(work_dir, "render_settings.py")
        Path(script_path).write_text(
            render_core.build_blend_render_script(settings, work_dir, animation=animation),
            encoding="utf-8",
        )
    else:
        scene = render_core.normalize_scene(payload.get("scene"))
        script_path = os.path.join(work_dir, "render_scene.py")
        out_target = work_dir if animation else os.path.join(work_dir, "out.png")
        Path(script_path).write_text(
            render_core.build_blender_script(scene, settings, out_target, animation=animation),
            encoding="utf-8",
        )

    t0 = time.time()
    rc, stdout, stderr = _run_blender(script_path, blend_path, work_dir)
    render_ms = int((time.time() - t0) * 1000)
    if rc != 0:
        tail = (stderr or stdout)[-3000:]
        raise RuntimeError(f"blender exited {rc}: {tail}")

    if animation:
        out_path = os.path.join(work_dir, "out.mp4")
        # Blender writes frame_0001.png ... into work_dir when animation builds a scene.
        frame_dir = work_dir
        _encode_animation(frame_dir, out_path, int(settings.get("fps", 24)))
        output_type = "video/mp4"
    else:
        out_path = os.path.join(work_dir, "out.png")
        # If the script reported a different path, prefer it.
        reported = None
        for line in (stdout or "").splitlines():
            reported = render_core.parse_output_path(line) or reported
        if reported and os.path.exists(reported):
            out_path = reported
        output_type = "image/png"

    if not os.path.exists(out_path):
        raise RuntimeError(
            f"render produced no output at {out_path}; blender stderr tail: "
            f"{(stderr or '')[-2000:]}"
        )
    return {
        "out_path": out_path,
        "output_type": output_type,
        "render_ms": render_ms,
        "engine": settings.get("engine", "cycles"),
        "frames": frames,
        "animation": animation,
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "BlenderRenderAPI/1.0"

    def log_message(self, fmt, *args):  # noqa: A003 - quiet, structured logging
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    # --- helpers -----------------------------------------------------------
    def _check_auth(self) -> bool:
        if not AUTH_TOKEN:
            return True
        header = self.headers.get("Authorization", "")
        if header.startswith("Bearer "):
            return header[len("Bearer "):].strip() == AUTH_TOKEN
        return False

    def _send_json(self, status: int, obj: dict[str, Any]) -> None:
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error_text(self, status: int, message: str) -> None:
        body = message.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    # --- routes ------------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._send_json(
                HTTPStatus.OK,
                {
                    "status": "ok",
                    "blender": blender_version(),
                    "gpu": has_gpu(),
                    "concurrency": int(os.environ.get("BLENDER_RENDER_CONCURRENCY", "2")),
                },
            )
            return
        if self.path == "/":
            self._send_json(HTTPStatus.OK, {"service": "blender-render-api", "endpoints": ["/health", "/render"]})
            return
        self._send_error_text(HTTPStatus.NOT_FOUND, "not found")

    def do_POST(self) -> None:  # noqa: N802
        if not self._check_auth():
            self._send_error_text(HTTPStatus.UNAUTHORIZED, "unauthorized")
            return
        if self.path != "/render":
            self._send_error_text(HTTPStatus.NOT_FOUND, "not found")
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_BODY_BYTES:
            self._send_error_text(
                HTTPStatus.BAD_REQUEST,
                f"invalid content length (max {MAX_BODY_BYTES} bytes)",
            )
            return
        raw = self._read_exact(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("body must be a JSON object")
        except Exception as exc:
            self._send_error_text(HTTPStatus.BAD_REQUEST, f"invalid JSON: {exc}")
            return

        try:
            with _RENDER_SEMAPHORE:
                with tempfile.TemporaryDirectory(prefix="blender-render-") as work_dir:
                    result = do_render(payload, work_dir)
                    with open(result["out_path"], "rb") as fh:
                        data = fh.read()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", result["output_type"])
            self.send_header("Content-Length", str(len(data)))
            self.send_header("X-Render-Ms", str(result["render_ms"]))
            self.send_header("X-Blender-Engine", str(result["engine"]))
            self.send_header("X-Blender-Version", str(blender_version() or ""))
            self.send_header("X-Output-Type", "animation" if result["animation"] else "still")
            self.send_header("X-Frames", str(result["frames"]))
            self.end_headers()
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                pass
        except subprocess.TimeoutExpired:
            self._send_error_text(HTTPStatus.GATEWAY_TIMEOUT, f"render timed out after {RENDER_TIMEOUT}s")
        except Exception as exc:
            sys.stderr.write("render failed:\n" + traceback.format_exc())
            self._send_error_text(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                f"render failed: {exc}",
            )

    def _read_exact(self, length: int) -> bytes:
        chunks: list[bytes] = []
        remaining = length
        while remaining > 0:
            chunk = self.rfile.read(min(65536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)


def main() -> int:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    sys.stderr.write(
        f"blender-render-api listening on {HOST}:{PORT} "
        f"(blender={BLENDER_EXEC} v{blender_version()}, gpu={has_gpu()}, "
        f"concurrency={int(os.environ.get('BLENDER_RENDER_CONCURRENCY','2'))}, "
        f"auth={'on' if AUTH_TOKEN else 'off'})\n"
    )
    sys.stderr.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
