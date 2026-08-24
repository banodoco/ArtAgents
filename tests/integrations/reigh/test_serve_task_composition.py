"""Production CLI composition tests for the Reigh editor task bridge."""

from __future__ import annotations

import json
import os
import re
import select
import signal
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def _request_json(
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    body: dict | None = None,
    key: str | None = None,
    authenticate: bool = True,
    version: str | None = "v1",
) -> tuple[int, dict]:
    payload = None if body is None else json.dumps(body).encode("utf-8")
    request = Request(base_url + path, data=payload, method=method)
    if authenticate:
        request.add_header("Authorization", "Bearer production-test-token")
    if version is not None:
        request.add_header("X-Astrid-Bridge-Version", version)
    if payload is not None:
        request.add_header("Content-Type", "application/json")
    if key is not None:
        request.add_header("Idempotency-Key", key)
    try:
        with urlopen(request, timeout=5) as response:  # noqa: S310 - loopback
            return response.status, json.loads(response.read())
    except HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _read_ready_line(process: subprocess.Popen[str]) -> str:
    assert process.stdout is not None
    deadline = time.monotonic() + 15
    observed: list[str] = []
    while time.monotonic() < deadline:
        readable, _, _ = select.select([process.stdout], [], [], 0.2)
        if not readable:
            if process.poll() is not None:
                break
            continue
        line = process.stdout.readline()
        if not line:
            break
        observed.append(line)
        if line.startswith("Astrid ready"):
            return line
    stderr = process.stderr.read() if process.stderr is not None else ""
    raise AssertionError(
        f"serve never became ready; stdout={observed!r}; stderr={stderr!r}"
    )


def test_python_module_serve_composes_authenticated_task_routes(
    tmp_path: Path,
) -> None:
    env = os.environ.copy()
    env["ASTRID_PROJECTS_ROOT"] = str(tmp_path)
    env["ASTRID_BRIDGE_TOKEN"] = "production-test-token"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "astrid",
            "projects",
            "create",
            "bridge-project",
            "--name",
            "Bridge Project",
            "--json",
        ],
        check=True,
        cwd=Path(__file__).parents[3],
        env=env,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "astrid",
            "timelines",
            "create",
            "render-source",
            "--project",
            "bridge-project",
            "--name",
            "Render Source",
            "--config",
            '{"clips":[]}',
            "--json",
        ],
        check=True,
        cwd=Path(__file__).parents[3],
        env=env,
        capture_output=True,
        text=True,
    )
    process = subprocess.Popen(
        [
            sys.executable,
            "-u",
            "-m",
            "astrid",
            "serve",
            "--projects-root",
            str(tmp_path),
            "--port",
            "0",
            "--no-open-editor",
            "--release-mode",
        ],
        cwd=Path(__file__).parents[3],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        ready = _read_ready_line(process)
        match = re.search(r"bridge at (http://[^,]+)", ready)
        assert match is not None, ready
        base_url = match.group(1)

        status, admitted = _request_json(
            base_url,
            "/projects/bridge-project/tasks",
            method="POST",
            key="production-cli-admit-1",
            body={
                "family": "image_upscale",
                "input": {"image_url": "https://example.invalid/input.png"},
            },
        )
        assert status == 201, admitted
        task_id = admitted["task"]["id"]

        status, detail = _request_json(
            base_url, f"/projects/bridge-project/tasks/{task_id}"
        )
        assert status == 200, detail
        assert detail["task"]["task_id"] == task_id
        assert detail["task"]["spec"]["family"] == "image_upscale"

        status, generations = _request_json(
            base_url, "/projects/bridge-project/generations"
        )
        assert status == 200, generations
        assert generations == {"generations": [], "next_cursor": None}

        status, stale_render = _request_json(
            base_url,
            "/projects/bridge-project/tasks",
            method="POST",
            key="production-cli-render-stale",
            body={
                "family": "render_export",
                "input": {
                    "timeline_ref": "render-source",
                    "expected_version": 0,
                    "destination": "download",
                },
            },
        )
        assert status == 409, stale_render
        assert stale_render["error"] == "conflict"
        assert stale_render["config_version"] == 1
        status, after_stale = _request_json(
            base_url, "/projects/bridge-project/tasks"
        )
        assert status == 200, after_stale
        assert [row["task_id"] for row in after_stale["tasks"]] == [task_id]

        status, render = _request_json(
            base_url,
            "/projects/bridge-project/tasks",
            method="POST",
            key="production-cli-render-current",
            body={
                "family": "render_export",
                "input": {
                    "timeline_ref": "render-source",
                    "expected_version": 1,
                    "destination": "download",
                },
            },
        )
        assert status == 201, render
        assert render["task"]["capability"] == "rendering.timeline_visualize"

        # Every new editor route crosses the same release-mode auth and
        # protocol gates before route matching, including byte routes and
        # mutations. An unknown object beneath an authenticated route may
        # be 404, but the same address without credentials must remain 401.
        for method, path, body in (
            ("GET", "/projects/bridge-project/tasks", None),
            ("GET", "/projects/bridge-project/generations", None),
            (
                "GET",
                "/projects/bridge-project/media/missing/content",
                None,
            ),
            (
                "POST",
                f"/projects/bridge-project/tasks/{task_id}/cancel",
                {},
            ),
        ):
            status, unauthorized = _request_json(
                base_url,
                path,
                method=method,
                body=body,
                authenticate=False,
            )
            assert status == 401, (method, path, unauthorized)
            assert unauthorized["error"] == "unauthorized"

        status, incompatible = _request_json(
            base_url,
            "/projects/bridge-project/generations",
            version="v999",
        )
        assert status == 426, incompatible
        assert incompatible["error"] == "protocol_version_mismatch"
    finally:
        if process.poll() is None:
            process.send_signal(signal.SIGTERM)
            process.wait(timeout=10)
        if process.poll() is None:  # pragma: no cover - defensive cleanup
            process.kill()
