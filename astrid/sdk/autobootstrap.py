"""Idempotent handoff from Astrid to the neutral local runtime.

Astrid is a client of the workspace runtime, not a second authority.  The
only work in this module is composing the neutral ``banodoco-local`` command
from an editable source profile and waiting for its bounded JSON result.  The
runtime process owns discovery, credentials, realm state, SQLite, and CAS.

The runtime checkout is intentionally explicit for the beta's editable-source
composition.  A normal launch may therefore be configured with
``BANODOCO_RUNTIME_CHECKOUT`` (or a pre-existing
``BANODOCO_LOCAL_SOURCE_MANIFEST``), but never guesses among sibling
checkouts or starts the neutral Astrid runtime.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Mapping

PROFILE = "astrid"
PROTOCOL_VERSION = "workspace.v1"
SCHEMA_VERSION = "workspace-schema-v1"


class AutoBootstrapError(RuntimeError):
    """A bounded, secret-free failure while invoking neutral bootstrap."""


def _configured(name: str) -> str:
    return os.environ.get(name, "").strip()


def _manifest_from_environment() -> Path | None:
    value = _configured("BANODOCO_LOCAL_SOURCE_MANIFEST")
    if not value:
        return None
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise AutoBootstrapError("configured Astrid source manifest is missing")
    return path


def _manifest_value(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AutoBootstrapError("configured Astrid source manifest is invalid") from exc
    if not isinstance(value, Mapping):
        raise AutoBootstrapError("configured Astrid source manifest must be an object")
    return value


def _checkout_from_environment() -> Path | None:
    for name in ("BANODOCO_RUNTIME_CHECKOUT", "BANODOCO_LOCAL_RUNTIME_CHECKOUT"):
        value = _configured(name)
        if value:
            return Path(value).expanduser().resolve()
    return None


def _source_checkout() -> Path:
    for name in ("BANODOCO_ASTRID_SOURCE_CHECKOUT", "ASTRID_SOURCE_CHECKOUT"):
        value = _configured(name)
        if value:
            return Path(value).expanduser().resolve()

    # Once the neutral launcher has bootstrapped an editable source profile,
    # that profile is the durable discovery record.  Reuse it on a product
    # relaunch even when the original shell no longer exports source paths.
    # This deliberately reads only the named ``astrid`` profile; sibling
    # checkouts are never guessed.
    home = Path(os.environ.get("BANODOCO_LOCAL_HOME") or os.environ.get("HOME", "~")).expanduser()
    catalog_path = home / "Library" / "Application Support" / "Banodoco" / "runtime" / "catalog.json"
    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        catalog = None
    profile = catalog.get("source_profiles", {}).get(PROFILE) if isinstance(catalog, Mapping) else None
    if isinstance(profile, Mapping) and profile.get("source_checkout"):
        return Path(str(profile["source_checkout"])).expanduser().resolve()

    # Editable Astrid checkouts have this module at <checkout>/astrid/sdk.  An
    # installed wheel cannot infer its source checkout and must use the
    # explicit environment setting above.
    candidate = Path(__file__).resolve().parents[2]
    if (candidate / "astrid").is_dir() and (candidate / "pyproject.toml").is_file():
        return candidate
    raise AutoBootstrapError(
        "Astrid source checkout is not configured; set BANODOCO_ASTRID_SOURCE_CHECKOUT"
    )


def _runtime_checkout(manifest: Path | None) -> Path:
    checkout = _checkout_from_environment()
    if checkout is None and manifest is not None:
        raw = _manifest_value(manifest).get("runtime_checkout")
        if raw:
            checkout = Path(str(raw)).expanduser().resolve()
    if checkout is None:
        home = Path(os.environ.get("BANODOCO_LOCAL_HOME") or os.environ.get("HOME", "~")).expanduser()
        catalog_path = home / "Library" / "Application Support" / "Banodoco" / "runtime" / "catalog.json"
        try:
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            catalog = None
        profile = catalog.get("source_profiles", {}).get(PROFILE) if isinstance(catalog, Mapping) else None
        if isinstance(profile, Mapping) and profile.get("runtime_checkout"):
            checkout = Path(str(profile["runtime_checkout"])).expanduser().resolve()
    if checkout is None:
        raise AutoBootstrapError(
            "neutral runtime checkout is not configured; set BANODOCO_RUNTIME_CHECKOUT"
        )
    if not checkout.is_dir() or not (checkout / "banodoco_local").is_dir():
        raise AutoBootstrapError("configured neutral runtime checkout is invalid")
    return checkout


def _write_ephemeral_manifest(*, runtime_checkout: Path, source_checkout: Path) -> Path:
    payload = {
        "profile": PROFILE,
        "runtime_checkout": str(runtime_checkout),
        "source_checkout": str(source_checkout),
        "protocol_version": PROTOCOL_VERSION,
        "schema_version": SCHEMA_VERSION,
    }
    fd, raw_path = tempfile.mkstemp(prefix="astrid-source-profile-", suffix=".json")
    path = Path(raw_path)
    path.chmod(0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return path


def _child_environment(runtime_checkout: Path) -> dict[str, str]:
    environment = dict(os.environ)
    roots = [str(runtime_checkout)]
    client_root = runtime_checkout / "packages" / "python"
    if client_root.is_dir():
        roots.append(str(client_root))
    if environment.get("PYTHONPATH"):
        roots.append(environment["PYTHONPATH"])
    environment["PYTHONPATH"] = os.pathsep.join(roots)

    # RuntimePaths.current_mac reads BANODOCO_LOCAL_HOME first.  Pin it to the
    # same temporary HOME used by Astrid unless the caller deliberately chose a
    # separate neutral support root.
    if not environment.get("BANODOCO_LOCAL_HOME"):
        environment["BANODOCO_LOCAL_HOME"] = str(
            Path(environment.get("HOME", "~")).expanduser().resolve()
        )
    return environment


def _result(stdout: str) -> Mapping[str, Any]:
    try:
        value = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise AutoBootstrapError("neutral runtime bootstrap returned invalid JSON") from exc
    if not isinstance(value, Mapping):
        raise AutoBootstrapError("neutral runtime bootstrap returned an invalid result")
    return value


def ensure_runtime() -> Mapping[str, Any]:
    """Launch or reconnect the configured neutral runtime exactly once.

    The neutral bootstrap's support lock and owner identity are the
    concurrency authority.  Calling this function from multiple Astrid
    processes is therefore safe: one invocation reports ``started`` and the
    others report ``reconnected`` against the same selected realm.
    """

    manifest = _manifest_from_environment()
    runtime_checkout = _runtime_checkout(manifest)
    ephemeral = manifest is None
    if ephemeral:
        source_checkout = _source_checkout()
        manifest = _write_ephemeral_manifest(
            runtime_checkout=runtime_checkout,
            source_checkout=source_checkout,
        )

    command = [
        sys.executable,
        "-m",
        "banodoco_local",
        "up",
        "--profile",
        PROFILE,
        "--source-manifest",
        str(manifest),
        "--json",
    ]
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=str(runtime_checkout),
            env=_child_environment(runtime_checkout),
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
    finally:
        if ephemeral and manifest is not None:
            manifest.unlink(missing_ok=True)

    value = _result(completed.stdout.strip())
    if completed.returncode != 0 or value.get("ok") is False:
        # Runtime errors are intentionally reduced to their stable top-level
        # action.  Paths, credentials, and subprocess diagnostics do not cross
        # the public Astrid error boundary.
        raise AutoBootstrapError("neutral runtime bootstrap was not ready")
    if str(value.get("status", "")) not in {"started", "reconnected", "restarted"}:
        raise AutoBootstrapError("neutral runtime bootstrap returned no ready status")
    return {
        "status": str(value["status"]),
        "realm_id": str(value.get("realm_id", "")),
        "elapsed_ms": round((time.monotonic() - started) * 1000, 1),
    }


__all__ = ["AutoBootstrapError", "ensure_runtime"]
