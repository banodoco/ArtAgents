"""Small, local release-identity surface for the Stage 1 release boundary.

This module deliberately deals in observations, not orchestration.  It reads
the already reviewed component checkouts, records their exact Git/tree and
contract/source observations, and derives the two locally safe identities
which precede migration or publication.  It never pushes, fetches, edits a
checkout, or talks to a remote target.

The implementation is intentionally dependency-free so it can also be used by
the release operator on a clean checkout (``python -m astrid.core.release_identity``).
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import subprocess
import unicodedata
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


SCHEMA_VERSION = "release-identity-v1"
NONE = "NONE"


class ReleaseIdentityError(ValueError):
    """A release identity cannot be produced or verified safely."""


def _nfc(value: Any) -> Any:
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, list):
        return [_nfc(item) for item in value]
    if isinstance(value, tuple):
        return [_nfc(item) for item in value]
    if isinstance(value, dict):
        return {unicodedata.normalize("NFC", str(key)): _nfc(item) for key, item in value.items()}
    return value


def canonical_bytes(value: Any) -> bytes:
    """Return the UTF-8 NFC canonical JSON bytes used by identity formulas."""

    return json.dumps(
        _nfc(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def framed_hash(label: str, value: Any) -> str:
    label_bytes = unicodedata.normalize("NFC", label).encode("utf-8")
    value_bytes = canonical_bytes(value)
    frame = len(label_bytes).to_bytes(8, "big") + label_bytes
    frame += len(value_bytes).to_bytes(8, "big") + value_bytes
    return hashlib.sha256(frame).hexdigest()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git(path: Path, *argv: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(path), *argv], capture_output=True, text=True,
            check=True, timeout=30,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise ReleaseIdentityError(f"git observation failed for {path}: {' '.join(argv)}") from exc
    return result.stdout.rstrip("\n")


def _git_optional(path: Path, *argv: str) -> str:
    try:
        return _git(path, *argv)
    except ReleaseIdentityError:
        return ""


def _git_bytes(path: Path, *argv: str) -> bytes:
    try:
        result = subprocess.run(
            ["git", "-C", str(path), *argv], capture_output=True,
            check=True, timeout=30,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise ReleaseIdentityError(f"git observation failed for {path}: {' '.join(argv)}") from exc
    return result.stdout


def _inventory_digest(path: Path, names: Iterable[str]) -> str:
    """Hash a stable path/blob inventory without reading the working tree."""

    entries = []
    for name in sorted(set(names)):
        try:
            blob = _git(path, "rev-parse", f"HEAD:{name}")
        except ReleaseIdentityError:
            continue
        entries.append({"path": name, "blob": blob})
    return framed_hash("banodoco.release-inventory.v1", entries)


def _tracked_names(path: Path) -> list[str]:
    raw = _git_bytes(path, "ls-tree", "-r", "--name-only", "-z", "HEAD")
    return [item.decode("utf-8") for item in raw.split(b"\0") if item]


def _repo_identity(path: Path) -> str:
    try:
        remote = _git(path, "config", "--get", "remote.origin.url")
    except ReleaseIdentityError:
        remote = ""
    # A remote URL is useful metadata, but it is never used to choose a target.
    # Fall back to a deterministic local identity for disposable repositories.
    return remote or path.name


def _dirty_paths(path: Path) -> list[str]:
    raw = _git(path, "status", "--porcelain=v1", "--untracked-files=all")
    return [line[3:] if len(line) >= 3 else line for line in raw.splitlines() if line]


def _paths_matching(names: Sequence[str], needles: Sequence[str]) -> list[str]:
    return [name for name in names if any(needle in name.lower() for needle in needles)]


def resolve_component(
    component_id: str,
    path: str | os.PathLike[str],
    *,
    source_ref: str | None = None,
    scope_paths: Sequence[str] | None = None,
    epochs: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Observe one reviewed component and return a candidate-component row.

    ``scope_paths`` is an optional reviewed scope.  It is treated as a
    whitelist of tracked paths, never as a directory walk, so generated,
    contract, pack, and capability ledgers retain exact Git identity.
    """

    if not component_id or not isinstance(component_id, str):
        raise ReleaseIdentityError("component_id must be a non-empty string")
    checkout = Path(path).expanduser().resolve()
    if not checkout.is_dir() or not (checkout / ".git").exists():
        raise ReleaseIdentityError(f"candidate component is not a Git checkout: {checkout}")
    names = _tracked_names(checkout)
    scope = sorted(set(scope_paths or names))
    unknown = sorted(set(scope) - set(names))
    if unknown:
        raise ReleaseIdentityError(f"scope paths are not in HEAD for {component_id}: {unknown}")
    dirty = _dirty_paths(checkout)
    head = _git(checkout, "rev-parse", "HEAD")
    tree = _git(checkout, "rev-parse", "HEAD^{tree}")
    contract_paths = _paths_matching(names, ("contract/", "schema", "openapi", "conformance/"))
    generated_paths = _paths_matching(names, ("generated", "/client", "client/"))
    capability_paths = _paths_matching(names, ("capabil", "manifest", "pack/"))
    dependency_paths = _paths_matching(names, ("lock", "requirements", "pyproject.toml", "package.json"))
    fixture_paths = _paths_matching(names, ("fixture", "fixtures"))
    epoch_values = {
        "contract_epoch": NONE,
        "runtime_epoch": NONE,
        "source_epoch": head,
        "migration_epoch": NONE,
        "activation_epoch": NONE,
        "release_epoch": NONE,
    }
    if epochs:
        epoch_values.update({str(k): _nfc(v) for k, v in epochs.items()})
    row = {
        "component_id": component_id,
        "repository_identity": _repo_identity(checkout),
        "source_ref": source_ref or _git_optional(checkout, "symbolic-ref", "--short", "-q", "HEAD") or head,
        "base_oid": head,
        "base_tree_oid": tree,
        "integrated_oid": head,
        "integrated_tree_oid": tree,
        "subtree_sha256": framed_hash("banodoco.component-subtree.v1", [{"path": p, "oid": _git(checkout, "rev-parse", f"HEAD:{p}")} for p in scope]),
        "contract_sha256": _inventory_digest(checkout, contract_paths),
        "generator_ids": generated_paths,
        "dependency_lock_digests": [{"path": p, "sha256": _sha256(_git_bytes(checkout, "show", f"HEAD:{p}"))} for p in dependency_paths],
        "fixture_digests": [{"path": p, "sha256": _sha256(_git_bytes(checkout, "show", f"HEAD:{p}"))} for p in fixture_paths],
        "tool_ids": ["TOOL-GIT"],
        "generator_observation_rows": [{"path": p, "sha256": _sha256(_git_bytes(checkout, "show", f"HEAD:{p}"))} for p in generated_paths],
        "provenance_input_bindings": [],
        "producer_id": "CMD-IDENTITY:pre-live-root",
        "epoch_profile_id": "EP-CRSM",
        "freshness_policy_id": "CURRENT-CLEAN-HEAD",
        "tree_sha256": tree,
        "schema_sha256": _inventory_digest(checkout, contract_paths),
        "capability_ledger_sha256": _inventory_digest(checkout, capability_paths),
        "dirty": bool(dirty),
        "dirty_paths": dirty,
        "epochs": epoch_values,
        "checkout": str(checkout),
    }
    return row


def resolve_reviewed_components(components: Mapping[str, str | os.PathLike[str]], **kwargs: Any) -> list[dict[str, Any]]:
    """Resolve a deterministic, component-id-sorted reviewed set."""

    rows = [resolve_component(component_id, path, **kwargs) for component_id, path in components.items()]
    return sorted(rows, key=lambda row: row["component_id"])


def _ensure_clean(rows: Sequence[Mapping[str, Any]]) -> None:
    dirty = [(row.get("component_id"), row.get("dirty_paths", [])) for row in rows if row.get("dirty")]
    if dirty:
        raise ReleaseIdentityError(f"candidate component has uncommitted changes: {dirty}")


def _receipt_digest(receipt: Mapping[str, Any]) -> str:
    body = {key: value for key, value in receipt.items() if key not in {"receipt_sha256", "identity"}}
    return framed_hash("banodoco.release-receipt.v1", body)


def create_pre_live_identity(
    components: Mapping[str, str | os.PathLike[str]],
    *,
    metadata: Mapping[str, Any] | None = None,
    output: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    """Create the local B11.3 pre-live root and its retrieval receipt."""

    rows = resolve_reviewed_components(components)
    _ensure_clean(rows)
    metadata = dict(metadata or {})
    evidence_rows = [
        {"path": f"components/{row['component_id']}", "sha256": row["subtree_sha256"], "producer_id": "CMD-IDENTITY:pre-live-root", "token_ids": [row["component_id"]], "epochs": row["epochs"], "media_type": "application/json"}
        for row in rows
    ]
    evidence_rows.sort(key=lambda row: (row["path"], row["sha256"], row["producer_id"]))
    identity = framed_hash("banodoco.pre-live-evidence-root.v1", evidence_rows)
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "kind": "pre-live-root",
        "operation_id": "CMD-IDENTITY:pre-live-root",
        "identity": identity,
        "epochs": metadata.get("epochs", {"runtime_epoch": NONE, "source_epoch": NONE, "migration_epoch": NONE, "activation_epoch": NONE, "release_epoch": NONE}),
        "seed_ids": sorted(["EXECUTION-COMPONENTS", "CONTRACT-ID", "RUNTIME-BUILD-ID", "SOURCE-MANIFEST-ID", "MIGRATION-MANIFEST-ID", "SELECTED-REALM-ID", "TRUSTED-DISPOSITION-SHA256"]),
        "evidence_rows": evidence_rows,
        "component_rows": rows,
        "metadata": _nfc(metadata),
    }
    receipt["receipt_sha256"] = _receipt_digest(receipt)
    _write_receipt(receipt, output)
    return receipt


def create_candidate_core_identity(
    pre_live: Mapping[str, Any] | str | os.PathLike[str],
    components: Mapping[str, str | os.PathLike[str]],
    *,
    metadata: Mapping[str, Any] | None = None,
    output: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    """Create the local B11.4 candidate-core identity."""

    source = load_receipt(pre_live) if isinstance(pre_live, (str, os.PathLike)) else dict(pre_live)
    verify_receipt(source)
    if source.get("kind") != "pre-live-root":
        raise ReleaseIdentityError("candidate core requires a pre-live-root receipt")
    rows = resolve_reviewed_components(components)
    _ensure_clean(rows)
    old_rows = {row["component_id"]: row for row in source.get("component_rows", [])}
    for row in rows:
        prior = old_rows.get(row["component_id"])
        if not prior or prior.get("integrated_oid") != row["integrated_oid"] or prior.get("integrated_tree_oid") != row["integrated_tree_oid"]:
            raise ReleaseIdentityError(f"candidate component changed after pre-live capture: {row['component_id']}")
    metadata = dict(metadata or {})
    values = {
        "schema_version": 1,
        "governance_binding": metadata.get("governance_binding", "LOCAL-STAGE1-RELEASE"),
        "component_manifest_sha256": framed_hash("banodoco.component-manifest.v1", rows),
        "contract_id": metadata.get("contract_id", framed_hash("banodoco.contract.v1", [row["contract_sha256"] for row in rows])),
        "runtime_build_id": metadata.get("runtime_build_id", framed_hash("banodoco.runtime-build.v1", [row["integrated_oid"] for row in rows])),
        "source_manifest_id": metadata.get("source_manifest_id", framed_hash("banodoco.source-manifest.v1", [row["subtree_sha256"] for row in rows])),
        "migration_manifest_id": metadata.get("migration_manifest_id", NONE),
        "selected_realm_id": metadata.get("selected_realm_id", NONE),
        "trusted_disposition_sha256": metadata.get("trusted_disposition_sha256", NONE),
        "pre_live_evidence_root": source["identity"],
        "contract_epoch": metadata.get("contract_epoch", NONE),
        "runtime_epoch": metadata.get("runtime_epoch", NONE),
        "source_epoch": metadata.get("source_epoch", NONE),
        "migration_epoch": metadata.get("migration_epoch", NONE),
        "activation_epoch": metadata.get("activation_epoch", NONE),
        "release_epoch": NONE,
        "component_rows": rows,
    }
    identity = framed_hash("banodoco.candidate-core.v1", values)
    receipt = {"schema_version": SCHEMA_VERSION, "kind": "candidate-core", "operation_id": "CMD-IDENTITY:candidate-core", "identity": identity, "candidate_core": values, "pre_live_root": source["identity"], "metadata": _nfc(metadata)}
    receipt["receipt_sha256"] = _receipt_digest(receipt)
    _write_receipt(receipt, output)
    return receipt


def _write_receipt(receipt: Mapping[str, Any], output: str | os.PathLike[str] | None) -> None:
    if output is None:
        return
    target = Path(output).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(canonical_bytes(receipt) + b"\n")


def load_receipt(path: str | os.PathLike[str]) -> dict[str, Any]:
    target = Path(path).expanduser().resolve()
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReleaseIdentityError(f"cannot retrieve release receipt: {target}") from exc
    if not isinstance(value, dict):
        raise ReleaseIdentityError("release receipt must be a JSON object")
    verify_receipt(value)
    return value


def verify_receipt(receipt: Mapping[str, Any]) -> str:
    """Verify receipt integrity and recompute its semantic identity."""

    if receipt.get("schema_version") != SCHEMA_VERSION:
        raise ReleaseIdentityError("unsupported release receipt schema")
    if receipt.get("receipt_sha256") != _receipt_digest(receipt):
        raise ReleaseIdentityError("release receipt digest mismatch")
    kind = receipt.get("kind")
    if kind == "pre-live-root":
        rows = receipt.get("evidence_rows")
        expected = framed_hash("banodoco.pre-live-evidence-root.v1", rows)
    elif kind == "candidate-core":
        expected = framed_hash("banodoco.candidate-core.v1", receipt.get("candidate_core"))
    else:
        raise ReleaseIdentityError(f"unknown release receipt kind: {kind!r}")
    if receipt.get("identity") != expected:
        raise ReleaseIdentityError("release identity mismatch")
    return expected


def bind_remote_targets(receipt: Mapping[str, Any], targets: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Return a target-bound copy without contacting or mutating any target.

    This is the locally safe half of B11.1.  Remote lookup, authorization, and
    push remain deliberately outside this API.
    """

    verify_receipt(receipt)
    if not isinstance(targets, Sequence):
        raise ReleaseIdentityError("remote targets must be an array")
    seen: set[str] = set()
    checked = []
    for target in targets:
        if not isinstance(target, Mapping):
            raise ReleaseIdentityError("remote target rows must be objects")
        target_id = target.get("remote_target_id")
        if not isinstance(target_id, str) or not target_id or target_id in seen:
            raise ReleaseIdentityError("remote target ids must be unique non-empty strings")
        seen.add(target_id)
        checked.append(_nfc(dict(target)))
    checked.sort(key=lambda row: row["remote_target_id"])
    result = copy.deepcopy(dict(receipt))
    result["remote_targets"] = checked
    result["remote_target_registry_sha256"] = framed_hash("banodoco.remote-target-registry.v1", checked)
    # Binding is an observation projection, so it has its own receipt digest;
    # the original semantic identity remains unchanged.
    result["receipt_sha256"] = _receipt_digest(result)
    return result


def _component_args(values: Sequence[str]) -> dict[str, str]:
    result = {}
    for value in values:
        if "=" not in value:
            raise ReleaseIdentityError("--component values must use COMPONENT_ID=CHECKOUT")
        component, checkout = value.split("=", 1)
        if not component or not checkout:
            raise ReleaseIdentityError("--component values must use COMPONENT_ID=CHECKOUT")
        result[component] = checkout
    if not result:
        raise ReleaseIdentityError("at least one --component is required")
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="astrid-release-identity")
    sub = parser.add_subparsers(dest="operation", required=True)
    pre = sub.add_parser("pre-live", help="capture B11.3 pre-live identity")
    pre.add_argument("--component", action="append", default=[])
    pre.add_argument("--output")
    candidate = sub.add_parser("candidate-core", help="capture B11.4 candidate-core identity")
    candidate.add_argument("--pre-live", required=True)
    candidate.add_argument("--component", action="append", default=[])
    candidate.add_argument("--output")
    verify = sub.add_parser("verify", help="retrieve and verify a receipt")
    verify.add_argument("receipt")
    args = parser.parse_args(argv)
    try:
        if args.operation == "pre-live":
            result = create_pre_live_identity(_component_args(args.component), output=args.output)
        elif args.operation == "candidate-core":
            result = create_candidate_core_identity(args.pre_live, _component_args(args.component), output=args.output)
        else:
            result = {"ok": True, "identity": load_receipt(args.receipt)["identity"]}
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    except ReleaseIdentityError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
