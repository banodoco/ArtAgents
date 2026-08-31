"""Explicit Astrid launcher boundary for the neutral runtime."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Mapping

PROFILE = "astrid"


class AutoBootstrapError(RuntimeError):
    """A bounded, secret-free failure while invoking neutral bootstrap."""


def _configured(name: str) -> str:
    return os.environ.get(name, "").strip()


def _manifest_from_environment() -> Path:
    value = _configured("BANODOCO_LOCAL_SOURCE_MANIFEST")
    if not value:
        raise AutoBootstrapError(
            "Astrid launcher manifest is not configured; run `banodoco-local up --profile astrid`"
        )
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise AutoBootstrapError("configured Astrid source manifest is missing")
    return path


def _result(stdout: str) -> Mapping[str, Any]:
    try:
        value = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise AutoBootstrapError("neutral runtime bootstrap returned invalid JSON") from exc
    if not isinstance(value, Mapping):
        raise AutoBootstrapError("neutral runtime bootstrap returned an invalid result")
    return value


def ensure_runtime() -> Mapping[str, Any]:
    """Invoke the installed launcher once and return its bounded result."""
    manifest = _manifest_from_environment()
    launcher = _configured("BANODOCO_LOCAL_LAUNCHER") or shutil.which("banodoco-local")
    if not launcher:
        raise AutoBootstrapError(
            "installed banodoco-local is unavailable; run `banodoco-local up --profile astrid`"
        )
    command = [launcher, "up", "--profile", PROFILE, "--source-manifest", str(manifest), "--json"]
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=15.0,
        )
    except subprocess.TimeoutExpired as exc:
        raise AutoBootstrapError("neutral runtime bootstrap timed out") from exc
    except OSError as exc:
        raise AutoBootstrapError("neutral runtime bootstrap could not be started") from exc
    value = _result(completed.stdout.strip())
    if completed.returncode != 0 or value.get("ok") is False:
        raise AutoBootstrapError("neutral runtime bootstrap was not ready")
    if str(value.get("status", "")) not in {"started", "reconnected", "restarted"}:
        raise AutoBootstrapError("neutral runtime bootstrap returned no ready status")
    return {
        "status": str(value["status"]),
        "realm_id": str(value.get("realm_id", "")),
        "endpoint": str(value.get("endpoint", "")),
        "actor_id": str(value.get("actor_id", "")),
        # The launcher returns only a path to the owner-only credential file;
        # never put the credential value in the subprocess result or logs.
        "credential_file": str(value.get("credential_file", "")),
        "elapsed_ms": round((time.monotonic() - started) * 1000, 1),
    }


__all__ = ["AutoBootstrapError", "ensure_runtime"]
