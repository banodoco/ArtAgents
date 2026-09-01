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
RECONFIGURE_ACTION = "run `banodoco-local up --profile astrid`"


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
    from astrid.sdk.workspace_client import _safe_local_path

    try:
        path = _safe_local_path(value, field="source manifest")
    except Exception as exc:
        raise AutoBootstrapError(
            f"configured Astrid source manifest is unsafe; {RECONFIGURE_ACTION}"
        ) from exc
    if not path.is_file():
        raise AutoBootstrapError(
            f"configured Astrid source manifest is missing; {RECONFIGURE_ACTION}"
        )
    return path


def _result(stdout: str) -> Mapping[str, Any]:
    try:
        value = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise AutoBootstrapError(
            f"neutral runtime bootstrap returned invalid JSON; {RECONFIGURE_ACTION}"
        ) from exc
    if not isinstance(value, Mapping):
        raise AutoBootstrapError(
            f"neutral runtime bootstrap returned an invalid result; {RECONFIGURE_ACTION}"
        )
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
        raise AutoBootstrapError(
            f"neutral runtime bootstrap timed out; {RECONFIGURE_ACTION}"
        ) from exc
    except OSError as exc:
        raise AutoBootstrapError(
            f"neutral runtime bootstrap could not be started; {RECONFIGURE_ACTION}"
        ) from exc
    value = _result(completed.stdout.strip())
    if completed.returncode != 0 or value.get("ok") is False:
        raise AutoBootstrapError(
            f"neutral runtime bootstrap was not ready; {RECONFIGURE_ACTION}"
        )
    if str(value.get("status", "")) not in {"started", "reconnected", "restarted"}:
        raise AutoBootstrapError(
            f"neutral runtime bootstrap returned no ready status; {RECONFIGURE_ACTION}"
        )
    for field in ("realm_id", "endpoint", "actor_id"):
        item = value.get(field)
        if not isinstance(item, str) or not item.strip():
            raise AutoBootstrapError(
                f"neutral runtime bootstrap returned no {field}; {RECONFIGURE_ACTION}"
            )
    from astrid.sdk.workspace_client import validate_runtime_endpoint

    try:
        validate_runtime_endpoint(value["endpoint"])
    except Exception as exc:
        raise AutoBootstrapError(
            f"neutral runtime bootstrap returned an unsafe endpoint; {RECONFIGURE_ACTION}"
        ) from exc
    credential_file = value.get("credential_file", "")
    if credential_file:
        if not isinstance(credential_file, str):
            raise AutoBootstrapError(
                f"neutral runtime bootstrap returned an invalid credential path; {RECONFIGURE_ACTION}"
            )
        try:
            from astrid.sdk.workspace_client import _safe_local_path

            credential_path = _safe_local_path(credential_file, field="credential")
        except Exception as exc:
            raise AutoBootstrapError(
                f"neutral runtime bootstrap returned an unsafe credential path; {RECONFIGURE_ACTION}"
            ) from exc
        if not credential_path.is_file():
            raise AutoBootstrapError(
                f"neutral runtime bootstrap returned a missing credential file; {RECONFIGURE_ACTION}"
            )
    return {
        "status": str(value["status"]),
        "realm_id": value["realm_id"].strip(),
        "endpoint": value["endpoint"].strip(),
        "actor_id": value["actor_id"].strip(),
        # The launcher returns only a path to the owner-only credential file;
        # never put the credential value in the subprocess result or logs.
        "credential_file": credential_file,
        "elapsed_ms": round((time.monotonic() - started) * 1000, 1),
    }


__all__ = ["AutoBootstrapError", "ensure_runtime"]
