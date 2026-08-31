"""B11.2 remote-target resolution and hermetic provisioning.

Network publication is deliberately not implicit.  Resolution is read-only;
provisioning requires an explicitly supplied local bare remote (used by the
acceptance harness) or an explicitly authorized transport supplied by a later
publication lane.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any, Mapping
from urllib.parse import urlparse

from .release_identity import REMOTE_TARGET_FIELDS, canonical_bytes


class RemoteTargetError(ValueError):
    pass


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _request_digest(method: str, target: Mapping[str, Any], *, idempotency_key: str) -> str:
    return _sha(canonical_bytes({"method": method, "target": dict(target), "idempotency_key": idempotency_key}))


def _ref(target: Mapping[str, Any]) -> str:
    value = target.get("destination_ref_or_prefix")
    if not isinstance(value, str) or not value.startswith("refs/") or ".." in value:
        raise RemoteTargetError("remote target destination must be a full safe ref")
    return value


def _url(target: Mapping[str, Any]) -> None:
    parsed = urlparse(str(target.get("canonical_url", "")))
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.netloc != "github.com":
        raise RemoteTargetError("remote target URL must be credential-free HTTPS GitHub")


def _local_oid(remote: Path, ref: str) -> str | None:
    result = subprocess.run(["git", "--git-dir", str(remote), "show-ref", "--verify", "--hash", ref], text=True, capture_output=True, check=False, timeout=30)
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    if result.returncode not in {1, 128}:
        raise RemoteTargetError(f"local remote probe failed: {result.stderr.strip()}")
    return None


def _network_oid(url: str, ref: str) -> tuple[str | None, int, str]:
    result = subprocess.run(["git", "ls-remote", "--refs", url, ref], text=True, capture_output=True, check=False, timeout=30)
    if result.returncode == 0:
        line = result.stdout.strip().splitlines()
        return (line[0].split()[0] if line else None), 200, result.stdout
    # Git does not expose HTTP status consistently.  Preserve the distinction
    # between an absent ref and an unreachable/unauthorized repository.
    return None, 404 if "not found" in result.stderr.lower() else 503, result.stderr


def resolve_remote_target(target: Mapping[str, Any], *, local_bare_remote: str | Path | None = None) -> dict[str, Any]:
    """Resolve one immutable locator without writing to a network remote."""
    if set(target) != set(REMOTE_TARGET_FIELDS):
        raise RemoteTargetError("remote target locator fields are not exact")
    if target.get("target_kind") == "publication":
        # Publication is a later packet's consumer.  B11.2 carries the
        # plan-owned suffix unchanged and does not invent an OID for it.
        if target.get("reviewed_source_oid") != "NONE":
            raise RemoteTargetError("publication locator cannot carry a reviewed component OID")
        return dict(target)
    _url(target)
    ref = _ref(target)
    expected = target.get("reviewed_source_oid")
    if not isinstance(expected, str) or len(expected) not in {40, 64} or any(c not in "0123456789abcdef" for c in expected):
        raise RemoteTargetError("reviewed source OID must be a full object ID")
    if local_bare_remote is not None:
        remote = Path(local_bare_remote).expanduser().resolve()
        if not remote.is_dir() or not (remote / "HEAD").exists():
            raise RemoteTargetError("local bare remote is not a Git repository")
        actual = _local_oid(remote, ref)
        status = 200 if actual else 404
        response = actual or "ABSENT"
    else:
        actual, status, response = _network_oid(str(target["canonical_url"]), ref)
    # NONE is a create-only discriminator: an existing different ref is a
    # race/conflict, never evidence that the target was absent.
    if actual is not None and actual != expected:
        raise RemoteTargetError(f"remote target ref conflict: expected {expected}, observed {actual}")
    request_key = f"B11.2:{target['remote_target_id']}:{expected}"
    receipt = {
        "method": "GET",
        "status": status,
        "request_sha256": _request_digest("GET", target, idempotency_key=request_key),
        "response_sha256": _sha(str(response).encode()),
        "repository_identity": target["repository_identity"],
        "idempotency_key": request_key,
        "postflight_status": status,
        "postflight_response_sha256": _sha(str(response).encode()),
    }
    # transport is diagnostic metadata inside a receipt; the outer target row
    # remains the closed REMOTE-TARGET row schema.
    result = dict(target)
    result["repository_provision_receipt_rows"] = [receipt]
    return result


def provision_local_bare_target(target: Mapping[str, Any], *, local_bare_remote: str | Path, idempotency_key: str | None = None) -> dict[str, Any]:
    """Conditionally create/update a ref in a disposable bare Git remote."""
    resolved = resolve_remote_target(target, local_bare_remote=local_bare_remote)
    remote = Path(local_bare_remote).expanduser().resolve()
    ref = _ref(target)
    expected = str(target["reviewed_source_oid"])
    actual = _local_oid(remote, ref)
    if actual is not None and actual != expected:
        raise RemoteTargetError("local bare remote changed during provisioning")
    key = idempotency_key or f"B11.2:{target['remote_target_id']}:{expected}"
    if actual is None:
        command = subprocess.run(["git", "--git-dir", str(remote), "update-ref", ref, expected], text=True, capture_output=True, check=False, timeout=30)
        if command.returncode != 0:
            raise RemoteTargetError(f"local bare remote provisioning failed: {command.stderr.strip()}")
        method, status, response = "POST", 201, expected
    else:
        method, status, response = "POST", 200, "already-present"
    receipt = dict(resolved["repository_provision_receipt_rows"][0])
    receipt.update({"method": method, "status": status, "request_sha256": _request_digest(method, target, idempotency_key=key), "response_sha256": _sha(str(response).encode()), "idempotency_key": key, "postflight_status": 200 if _local_oid(remote, ref) == expected else 409, "postflight_response_sha256": _sha(str(_local_oid(remote, ref) or "MISSING").encode())})
    resolved["repository_provision_receipt_rows"] = [receipt]
    return resolved


def resolve_target_set(locators: list[Mapping[str, Any]], *, local_bare_remotes: Mapping[str, str | Path] | None = None, provision: bool = False) -> dict[str, Any]:
    if not locators:
        raise RemoteTargetError("remote target locator set must be non-empty")
    results = []
    for locator in locators:
        if locator.get("target_kind") == "publication":
            results.append(resolve_remote_target(locator))
            continue
        local = (local_bare_remotes or {}).get(str(locator.get("remote_target_id")))
        if provision:
            if local is None:
                raise RemoteTargetError("network provisioning is disabled; supply an explicit local bare remote")
            results.append(provision_local_bare_target(locator, local_bare_remote=local))
        else:
            results.append(resolve_remote_target(locator, local_bare_remote=local))
    return {"schema_version": "remote-target-set-v1", "targets": results}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="astrid-remote-targets")
    parser.add_argument("--locators", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--local-bare", action="append", default=[], metavar="TARGET_ID=PATH")
    parser.add_argument("--provision", action="store_true")
    args = parser.parse_args(argv)
    try:
        locators = json.loads(args.locators.read_text(encoding="utf-8"))
        if isinstance(locators, Mapping):
            locators = locators.get("targets", locators.get("component_registry", []))
        mapping = {}
        for item in args.local_bare:
            if "=" not in item:
                raise RemoteTargetError("--local-bare must be TARGET_ID=PATH")
            key, path = item.split("=", 1); mapping[key] = path
        result = resolve_target_set(list(locators), local_bare_remotes=mapping, provision=args.provision)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, sort_keys=True, indent=2))
        return 0
    except (OSError, json.JSONDecodeError, RemoteTargetError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
