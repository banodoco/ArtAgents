"""Portable, closed release identity observations for the Stage 1 boundary."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import subprocess
import unicodedata
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urlparse

SCHEMA_VERSION = "release-identity-v1"
NONE = "NONE"
CANDIDATE_COMPONENT_SCHEMA = "candidate-component-row-v1"
PRELIVE_MANIFEST_SCHEMA = "pre-live-manifest-v1"
CANDIDATE_COMPONENT_FIELDS = ("component_id", "repository_identity", "source_ref", "base_oid", "base_tree_oid", "integrated_oid", "integrated_tree_oid", "subtree_sha256", "contract_sha256", "generator_ids", "dependency_lock_digests", "fixture_digests", "tool_ids", "generator_observation_rows", "provenance_input_bindings", "producer_id", "epoch_profile_id", "freshness_policy_id")
PRELIVE_MANIFEST_FIELDS = ("schema_version", "governance_binding", "seed_ids", "evidence_rows", "excluded_ids", "epochs", "manifest_sha256")
CANDIDATE_CORE_FIELDS = ("schema_version", "governance_binding", "component_manifest_sha256", "contract_id", "runtime_build_id", "source_manifest_id", "migration_manifest_id", "selected_realm_id", "trusted_disposition_sha256", "pre_live_evidence_root", "contract_epoch", "runtime_epoch", "source_epoch", "migration_epoch", "activation_epoch", "release_epoch", "component_rows")
REMOTE_TARGET_FIELDS = ("remote_target_id", "target_kind", "component_id", "local_repository_identity", "repository_identity", "canonical_url", "destination_ref_or_prefix", "expected_old_oid", "reviewed_source_oid", "identity_transition_sha256", "repository_provision_receipt_rows")
PRELIVE_SEED_SOURCE = ("CURRENT-PLAN CURRENT-GOAL NORTH-STAR CUSTODY PHASE0-BASELINE GOVERNANCE-AMENDMENT THROUGHPUT-POLICY VALIDATOR-ID ROADMAP-OVERALL ROADMAP-ASTRID-BETA ROADMAP-REIGH ROADMAP-HARDENING ROADMAP-VISION ROADMAP-README CONVERGENCE BUNDLE-MANIFEST EXECUTION-PACKETS EXECUTION-REQUIREMENTS EXECUTION-COVERAGE EXECUTION-VALIDATION-MATRIX EXECUTION-COMMANDS EXECUTION-INTEGRATIONS EXECUTION-COMPONENTS EXECUTION-SCHEMAS-MANIFEST EXECUTION-VECTORS-MANIFEST BUNDLE-B0 RCPT-B0-MATERIALIZE P(B0.1) P(B0.2) P(B0.3) G(K-B0) CONTRACT-ID RUNTIME-BUILD-ID SOURCE-MANIFEST-ID MIGRATION-MANIFEST-ID SELECTED-REALM-ID TRUSTED-DISPOSITION-SHA256 RCPT-REV-C1 RCPT-REV-C2 RCPT-REV-C3 RCPT-REV-C4 G(K-B10) P(B11.1) P(B11.2) REVIEWED-COMPONENTS-B11 REMOTE-TARGET-LOCATORS REMOTE-TARGET-SET").split()
PRELIVE_EXCLUDED_IDS = ("PRELIVE-MANIFEST", "RCPT-PRELIVE-MANIFEST", "PRELIVE-ROOT", "RCPT-IDENTITY-PRELIVE", "CANDIDATE-CORE", "RCPT-IDENTITY-CANDIDATE-CORE")
PRELIVE_SEEDS = tuple(sorted(set(PRELIVE_SEED_SOURCE)))

class ReleaseIdentityError(ValueError):
    """A release identity cannot be produced or verified safely."""

def _nfc(value: Any) -> Any:
    if isinstance(value, str): return unicodedata.normalize("NFC", value)
    if isinstance(value, list): return [_nfc(v) for v in value]
    if isinstance(value, tuple): return [_nfc(v) for v in value]
    if isinstance(value, dict): return {unicodedata.normalize("NFC", str(k)): _nfc(v) for k, v in value.items()}
    return value

def canonical_bytes(value: Any) -> bytes:
    return json.dumps(_nfc(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")

def framed_hash(label: str, value: Any) -> str:
    left, right = unicodedata.normalize("NFC", label).encode("utf-8"), canonical_bytes(value)
    return hashlib.sha256(len(left).to_bytes(8, "big") + left + len(right).to_bytes(8, "big") + right).hexdigest()

def _sha256_bytes(data: bytes) -> str: return hashlib.sha256(data).hexdigest()

def _git(path: Path, *argv: str, text: bool = True, optional: bool = False) -> str | bytes:
    try:
        result = subprocess.run(["git", "-C", str(path), *argv], capture_output=True, text=text, check=True, timeout=30)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        if optional: return "" if text else b""
        raise ReleaseIdentityError(f"git observation failed for {path}: {' '.join(argv)}") from exc
    return result.stdout

def _git_text(path: Path, *argv: str, optional: bool = False) -> str:
    return str(_git(path, *argv, text=True, optional=optional)).rstrip("\n")

def _git_bytes(path: Path, *argv: str) -> bytes: return bytes(_git(path, *argv, text=False))

def _tracked_names(path: Path) -> list[str]:
    return [item.decode("utf-8") for item in _git_bytes(path, "ls-tree", "-r", "--name-only", "-z", "HEAD").split(b"\0") if item]

def _repo_identity(path: Path) -> str:
    remote = _git_text(path, "config", "--get", "remote.origin.url", optional=True)
    if not remote: return path.name
    match = re.search(r"(?:github\.com[:/])([^/ :]+/[^/]+?)(?:\.git)?$", remote)
    return match.group(1) if match else remote.removesuffix(".git")

def git_identity(path: str | os.PathLike[str]) -> dict[str, Any]:
    """Portable worktree/common-dir/detached metadata plus recursive submodules."""
    root = Path(path).expanduser().resolve()
    git_dir = _git_text(root, "rev-parse", "--git-dir")
    common = _git_text(root, "rev-parse", "--git-common-dir")
    ref = _git_text(root, "symbolic-ref", "-q", "--short", "HEAD", optional=True)
    subs = []
    for line in _git_text(root, "submodule", "status", "--recursive", optional=True).splitlines():
        match = re.match(r"^[ +-]?([0-9a-f]{40,64})\s+([^ (]+)", line)
        if match: subs.append({"path": match.group(2), "oid": match.group(1)})
    return {"repository_identity": _repo_identity(root), "head_oid": _git_text(root, "rev-parse", "HEAD"), "head_ref": ref or NONE, "detached": not bool(ref), "git_dir_kind": "worktree" if (root / ".git").is_file() else "directory", "git_dir_relative": os.path.relpath(git_dir, common) if git_dir and common else NONE, "common_dir_relative": ".", "submodules": sorted(subs, key=lambda x: x["path"])}

def _dirty_paths(path: Path, *, exclude: str | os.PathLike[str] | None = None) -> list[str]:
    raw = _git_text(path, "status", "--porcelain=v1", "--untracked-files=all", "--ignored=matching")
    excluded = None
    if exclude:
        try: excluded = Path(exclude).expanduser().resolve().relative_to(path.resolve()).as_posix()
        except ValueError: pass
    found = []
    for line in raw.splitlines():
        if not line: continue
        value = line[3:] if len(line) >= 3 else line
        if value.startswith('"'):
            try: value = json.loads(value)
            except json.JSONDecodeError: pass
        if not excluded or value != excluded: found.append(value)
    return sorted(set(found))

def _inventory_digest(path: Path, names: Iterable[str]) -> str:
    rows = []
    for name in sorted(set(names)):
        oid = _git_text(path, "rev-parse", f"HEAD:{name}", optional=True)
        if oid: rows.append({"path": name, "oid": oid})
    return framed_hash("banodoco.release-inventory.v1", rows)

def _scope(paths: Sequence[str], needles: Sequence[str]) -> list[str]: return [p for p in paths if any(n in p.lower() for n in needles)]

def _candidate_shape(row: Mapping[str, Any]) -> dict[str, Any]:
    if set(row) != set(CANDIDATE_COMPONENT_FIELDS): raise ReleaseIdentityError("candidate-component-row-v1 has unexpected or missing fields")
    return {k: _nfc(row[k]) for k in CANDIDATE_COMPONENT_FIELDS}

def resolve_component(component_id: str, path: str | os.PathLike[str], *, source_ref: str | None = None, scope_paths: Sequence[str] | None = None, epochs: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if not isinstance(component_id, str) or not component_id: raise ReleaseIdentityError("component_id must be a non-empty string")
    root = Path(path).expanduser().resolve()
    if not root.is_dir() or not (root / ".git").exists(): raise ReleaseIdentityError(f"candidate component is not a Git checkout: {root}")
    names = _tracked_names(root); scope = sorted(set(scope_paths or names))
    if set(scope) - set(names): raise ReleaseIdentityError(f"scope paths are not in HEAD for {component_id}")
    head, tree = _git_text(root, "rev-parse", "HEAD"), _git_text(root, "rev-parse", "HEAD^{tree}")
    contract = _scope(names, ("contract/", "schema", "openapi", "conformance/")); generated = _scope(names, ("generated", "/client", "client/")); capabilities = _scope(names, ("capabil", "manifest", "pack/")); dependency = _scope(names, ("lock", "requirements", "pyproject.toml", "package.json")); fixtures = _scope(names, ("fixture", "fixtures"))
    _ = epochs; _ = capabilities
    return _candidate_shape({"component_id": component_id, "repository_identity": _repo_identity(root), "source_ref": source_ref or _git_text(root, "symbolic-ref", "--short", "-q", "HEAD", optional=True) or head, "base_oid": head, "base_tree_oid": tree, "integrated_oid": head, "integrated_tree_oid": tree, "subtree_sha256": framed_hash("banodoco.component-subtree.v1", [{"path": p, "oid": _git_text(root, "rev-parse", f"HEAD:{p}")} for p in scope]), "contract_sha256": _inventory_digest(root, contract), "generator_ids": generated, "dependency_lock_digests": [{"path": p, "sha256": _sha256_bytes(_git_bytes(root, "show", f"HEAD:{p}"))} for p in dependency], "fixture_digests": [{"path": p, "sha256": _sha256_bytes(_git_bytes(root, "show", f"HEAD:{p}"))} for p in fixtures], "tool_ids": ["TOOL-GIT"], "generator_observation_rows": [], "provenance_input_bindings": [], "producer_id": "PROD-CMD-PACKET:B11.1", "epoch_profile_id": "EP-CRSM", "freshness_policy_id": "CURRENT-CLEAN-HEAD"})

def resolve_reviewed_components(components: Mapping[str, str | os.PathLike[str]], **kwargs: Any) -> list[dict[str, Any]]:
    if len(set(components)) != len(components): raise ReleaseIdentityError("component IDs must be unique")
    return sorted((resolve_component(cid, path, **kwargs) for cid, path in components.items()), key=lambda row: row["component_id"])

def _assert_clean(components: Mapping[str, str | os.PathLike[str]], output: str | os.PathLike[str] | None = None) -> None:
    dirty = []
    for cid, path in components.items():
        paths = _dirty_paths(Path(path).expanduser().resolve(), exclude=output)
        if paths: dirty.append((cid, paths))
    if dirty: raise ReleaseIdentityError(f"candidate component has uncommitted changes: {dirty}")

def _plan_transition(cid: str, local: str, canonical: str, url: str, ref: str) -> str: return framed_hash("banodoco.local-to-canonical-repository.v1", [cid, local, canonical, url, ref])

def plan_component_registry() -> list[dict[str, Any]]:
    rows = [("NEUTRAL-RUNTIME", "banodoco-workspace-runtime-oracle", "banodoco/banodoco-workspace-runtime", "https://github.com/banodoco/banodoco-workspace-runtime.git"), ("ASTRID-CLIENT", "peteromallet/Astrid", "peteromallet/Astrid", "https://github.com/peteromallet/Astrid.git")]
    return [_nfc({"remote_target_id": f"REMOTE-TARGET:COMPONENT:{cid}", "target_kind": "component", "component_id": cid, "local_repository_identity": local, "repository_identity": canonical, "canonical_url": url, "destination_ref_or_prefix": "refs/heads/main", "expected_old_oid": NONE, "reviewed_source_oid": NONE, "identity_transition_sha256": _plan_transition(cid, local, canonical, url, "refs/heads/main"), "repository_provision_receipt_rows": NONE}) for cid, local, canonical, url in rows]

PLAN_COMPONENT_REGISTRY = tuple(plan_component_registry())

def plan_publication_row() -> dict[str, Any]: return {"remote_target_id": "REMOTE-TARGET:PUBLICATION", "target_kind": "publication", "component_id": NONE, "local_repository_identity": NONE, "repository_identity": "banodoco/banodoco-workspace-runtime", "canonical_url": "https://github.com/banodoco/banodoco-workspace-runtime.git", "destination_ref_or_prefix": "refs/tags/astrid-stage1-evidence/", "expected_old_oid": NONE, "reviewed_source_oid": NONE, "identity_transition_sha256": NONE, "repository_provision_receipt_rows": NONE}

def component_registry_sha256(rows: Sequence[Mapping[str, Any]] | None = None) -> str: return _sha256_bytes(canonical_bytes(list(rows if rows is not None else plan_component_registry())))

def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != "github.com" or parsed.username or parsed.password or parsed.query or parsed.fragment or not re.fullmatch(r"/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\.git", parsed.path): raise ReleaseIdentityError("canonical URL must be an absolute credential-free HTTPS GitHub URL")

def join_plan_remote_targets(component_rows: Sequence[Mapping[str, Any]], *, strict: bool = True) -> list[dict[str, Any]]:
    rows = [_candidate_shape(r) for r in component_rows]; registry = plan_component_registry(); by_id = {r["component_id"]: r for r in rows}
    if strict and set(by_id) != {r["component_id"] for r in registry}: raise ReleaseIdentityError("plan-owned component registry join is not total")
    result = []
    for target in registry:
        source = by_id.get(target["component_id"])
        if source is None or source["repository_identity"] != target["local_repository_identity"]: raise ReleaseIdentityError("local repository identity does not match plan registry")
        _validate_url(target["canonical_url"])
        if target["identity_transition_sha256"] != _plan_transition(target["component_id"], target["local_repository_identity"], target["repository_identity"], target["canonical_url"], target["destination_ref_or_prefix"]): raise ReleaseIdentityError("plan registry identity transition mismatch")
        item = copy.deepcopy(target); item["reviewed_source_oid"] = source["integrated_oid"]; result.append(item)
    result.append(plan_publication_row()); return result

def build_prelive_manifest(seed_outputs: Mapping[str, bytes | bytearray | Mapping[str, Any] | Sequence[Any]] | None = None, *, metadata: Mapping[str, Any] | None = None) -> dict[str, Any]:
    outputs = seed_outputs or {}; seeds = sorted(set(PRELIVE_SEED_SOURCE)); epochs = dict((metadata or {}).get("epochs", {"contract_epoch": NONE, "runtime_epoch": NONE, "source_epoch": NONE, "migration_epoch": NONE, "activation_epoch": NONE, "release_epoch": NONE})); evidence = []
    for seed in seeds:
        value = outputs.get(seed, {"seed_id": seed}); data = bytes(value) if isinstance(value, (bytes, bytearray)) else canonical_bytes(value); digest = _sha256_bytes(data)
        evidence.append({"path": f"evidence/sha256/{digest[:2]}/{digest}", "sha256": digest, "producer_id": "CMD-PRELIVE-MANIFEST", "token_ids": [seed], "epochs": _nfc(epochs), "media_type": "application/json"})
    evidence.sort(key=lambda r: (r["path"], r["sha256"], r["producer_id"])); manifest = {"schema_version": PRELIVE_MANIFEST_SCHEMA, "governance_binding": "LOCAL-STAGE1-RELEASE", "seed_ids": seeds, "evidence_rows": evidence, "excluded_ids": list(PRELIVE_EXCLUDED_IDS), "epochs": _nfc(epochs)}; manifest["manifest_sha256"] = framed_hash("banodoco.pre-live-manifest.v1", manifest)
    if set(manifest) != set(PRELIVE_MANIFEST_FIELDS): raise ReleaseIdentityError("pre-live manifest schema drift")
    return manifest

def _receipt_digest(receipt: Mapping[str, Any]) -> str: return framed_hash("banodoco.release-receipt.v1", {k: v for k, v in receipt.items() if k not in {"receipt_sha256", "identity"}})

def create_pre_live_identity(components: Mapping[str, str | os.PathLike[str]], *, metadata: Mapping[str, Any] | None = None, output: str | os.PathLike[str] | None = None, seed_outputs: Mapping[str, bytes | bytearray | Mapping[str, Any] | Sequence[Any]] | None = None) -> dict[str, Any]:
    _assert_clean(components, output); rows = resolve_reviewed_components(components); metadata = dict(metadata or {}); manifest = build_prelive_manifest(seed_outputs, metadata=metadata); evidence = []
    for row in rows:
        data = canonical_bytes(row); digest = _sha256_bytes(data); evidence.append({"path": f"evidence/sha256/{digest[:2]}/{digest}", "sha256": digest, "producer_id": "CMD-IDENTITY:pre-live-root", "token_ids": [row["component_id"]], "epochs": metadata.get("epochs", {}), "media_type": "application/json"})
    evidence.sort(key=lambda r: (r["path"], r["sha256"], r["producer_id"])); root_payload = {"component_rows": rows, "evidence_rows": evidence, "manifest_sha256": manifest["manifest_sha256"]}; identity = framed_hash("banodoco.pre-live-evidence-root.v1", root_payload)
    strict = set(r["component_id"] for r in rows) == {"ASTRID-CLIENT", "NEUTRAL-RUNTIME"} and all(r["repository_identity"] in {"peteromallet/Astrid", "banodoco-workspace-runtime-oracle"} for r in rows)
    receipt = {"schema_version": SCHEMA_VERSION, "kind": "pre-live-root", "operation_id": "CMD-IDENTITY:pre-live-root", "identity": identity, "pre_live_manifest": manifest, "evidence_rows": evidence, "component_rows": rows, "remote_target_locators": join_plan_remote_targets(rows) if strict else [], "metadata": _nfc(metadata)}; receipt["receipt_sha256"] = _receipt_digest(receipt); _write_receipt(receipt, output); return receipt

def _component_set(rows: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    result = {}
    for row in rows:
        if set(row) != set(CANDIDATE_COMPONENT_FIELDS): raise ReleaseIdentityError("candidate-component-row-v1 has unexpected or missing fields")
        cid = row["component_id"]
        if not isinstance(cid, str) or cid in result: raise ReleaseIdentityError("candidate component IDs must be unique")
        result[cid] = row
    return result

def create_candidate_core_identity(pre_live: Mapping[str, Any] | str | os.PathLike[str], components: Mapping[str, str | os.PathLike[str]], *, metadata: Mapping[str, Any] | None = None, output: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    source = load_receipt(pre_live) if isinstance(pre_live, (str, os.PathLike)) else dict(pre_live); verify_receipt(source)
    if source.get("kind") != "pre-live-root": raise ReleaseIdentityError("candidate core requires a pre-live-root receipt")
    _assert_clean(components, output); rows = resolve_reviewed_components(components); old, new = _component_set(source.get("component_rows", [])), _component_set(rows)
    if set(old) != set(new): raise ReleaseIdentityError("candidate component set is not a total bijection")
    for cid in sorted(old):
        if canonical_bytes(old[cid]) != canonical_bytes(new[cid]): raise ReleaseIdentityError(f"candidate component field mismatch after pre-live capture: {cid}")
    meta = dict(metadata or {}); manifest = source["pre_live_manifest"]; core = {"schema_version": 1, "governance_binding": meta.get("governance_binding", "LOCAL-STAGE1-RELEASE"), "component_manifest_sha256": framed_hash("banodoco.component-manifest.v1", rows), "contract_id": meta.get("contract_id", framed_hash("banodoco.contract.v1", [r["contract_sha256"] for r in rows])), "runtime_build_id": meta.get("runtime_build_id", framed_hash("banodoco.runtime-build.v1", [r["integrated_oid"] for r in rows])), "source_manifest_id": meta.get("source_manifest_id", framed_hash("banodoco.source-manifest.v1", [r["subtree_sha256"] for r in rows])), "migration_manifest_id": meta.get("migration_manifest_id", NONE), "selected_realm_id": meta.get("selected_realm_id", NONE), "trusted_disposition_sha256": meta.get("trusted_disposition_sha256", NONE), "pre_live_evidence_root": source["identity"], "contract_epoch": meta.get("contract_epoch", NONE), "runtime_epoch": meta.get("runtime_epoch", NONE), "source_epoch": meta.get("source_epoch", NONE), "migration_epoch": meta.get("migration_epoch", NONE), "activation_epoch": meta.get("activation_epoch", NONE), "release_epoch": NONE, "component_rows": rows}; receipt = {"schema_version": SCHEMA_VERSION, "kind": "candidate-core", "operation_id": "CMD-IDENTITY:candidate-core", "identity": framed_hash("banodoco.candidate-core.v1", core), "candidate_core": core, "pre_live_root": source["identity"], "pre_live_manifest_sha256": manifest["manifest_sha256"], "metadata": _nfc(meta)}; receipt["receipt_sha256"] = _receipt_digest(receipt); _write_receipt(receipt, output); return receipt

def _safe_receipt_path(path: str | os.PathLike[str]) -> Path:
    raw = Path(path).expanduser()
    if ".." in raw.parts: raise ReleaseIdentityError("receipt path may not contain '..'")
    target = raw.absolute(); current = Path(target.anchor)
    for part in target.parts[1:-1]:
        current /= part
        if current.exists() and current.is_symlink() and current != Path("/tmp"): raise ReleaseIdentityError("receipt path contains a symlink")
    if target.exists() and target.is_symlink(): raise ReleaseIdentityError("receipt path is a symlink")
    return target

def _write_receipt(receipt: Mapping[str, Any], output: str | os.PathLike[str] | None) -> None:
    if output is None: return
    target = _safe_receipt_path(output); target.parent.mkdir(parents=True, exist_ok=True); data = canonical_bytes(receipt) + b"\n"; target.write_bytes(data)
    if target.read_bytes() != data: raise ReleaseIdentityError("stored receipt bytes changed during write")

def verify_receipt(receipt: Mapping[str, Any]) -> str:
    if receipt.get("schema_version") != SCHEMA_VERSION or receipt.get("receipt_sha256") != _receipt_digest(receipt): raise ReleaseIdentityError("release receipt digest or schema mismatch")
    if receipt.get("kind") == "pre-live-root":
        manifest = receipt.get("pre_live_manifest")
        if not isinstance(manifest, Mapping) or manifest.get("manifest_sha256") != framed_hash("banodoco.pre-live-manifest.v1", {k: manifest[k] for k in manifest if k != "manifest_sha256"}): raise ReleaseIdentityError("pre-live manifest digest mismatch")
        rows = _component_set(receipt.get("component_rows", [])); expected = framed_hash("banodoco.pre-live-evidence-root.v1", {"component_rows": [rows[k] for k in sorted(rows)], "evidence_rows": receipt.get("evidence_rows"), "manifest_sha256": manifest["manifest_sha256"]})
    elif receipt.get("kind") == "candidate-core":
        core = receipt.get("candidate_core")
        if not isinstance(core, Mapping) or set(core) != set(CANDIDATE_CORE_FIELDS): raise ReleaseIdentityError("candidate-core-object-v1 has unexpected or missing fields")
        expected = framed_hash("banodoco.candidate-core.v1", core)
    else: raise ReleaseIdentityError("unknown release receipt kind")
    if expected != receipt.get("identity"): raise ReleaseIdentityError("release identity mismatch")
    return expected

def load_receipt(path: str | os.PathLike[str]) -> dict[str, Any]:
    target = _safe_receipt_path(path)
    try:
        raw = target.read_bytes()
        if not raw.endswith(b"\n"): raise ReleaseIdentityError("receipt is not canonical stored bytes")
        value = json.loads(raw[:-1].decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc: raise ReleaseIdentityError(f"cannot retrieve release receipt: {target}") from exc
    if not isinstance(value, dict) or canonical_bytes(value) + b"\n" != raw: raise ReleaseIdentityError("receipt bytes are not canonical")
    verify_receipt(value); return value

def bind_remote_targets(receipt: Mapping[str, Any], targets: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    verify_receipt(receipt)
    if not isinstance(targets, Sequence) or isinstance(targets, (str, bytes)): raise ReleaseIdentityError("remote targets must be an array")
    result = copy.deepcopy(dict(receipt)); rows = []; seen: set[str] = set()
    if result.get("remote_target_locators") and list(targets) != result["remote_target_locators"]: raise ReleaseIdentityError("remote target rows are not the plan-owned locator join")
    for target in targets:
        # Legacy callers may bind an unplanned, copy-only annotation.  Once a
        # plan-owned locator is present the closed row schema is mandatory.
        if not result.get("remote_target_locators"):
            item = _nfc(dict(target)); tid = item.get("remote_target_id")
            if not isinstance(tid, str) or not tid or tid in seen: raise ReleaseIdentityError("remote target ids must be unique non-empty strings")
            seen.add(tid)
            rows.append(item)
            continue
        if set(target) != set(REMOTE_TARGET_FIELDS): raise ReleaseIdentityError("remote-target-row-v1 has unexpected fields")
        item = _nfc(dict(target)); tid = item["remote_target_id"]
        if not isinstance(tid, str) or not tid or tid in seen: raise ReleaseIdentityError("remote target ids must be unique non-empty strings")
        seen.add(tid)
        if item["target_kind"] in {"component", "publication"}: _validate_url(item["canonical_url"])
        rows.append(item)
    result["remote_targets"] = sorted(rows, key=lambda r: r["remote_target_id"]); result["remote_target_registry_sha256"] = component_registry_sha256(result["remote_targets"][:-1] if len(rows) == 3 else rows); result["receipt_sha256"] = _receipt_digest(result); return result

def _component_args(values: Sequence[str]) -> dict[str, str]:
    result = {}
    for value in values:
        if "=" not in value: raise ReleaseIdentityError("--component values must use COMPONENT_ID=CHECKOUT")
        cid, checkout = value.split("=", 1)
        if not cid or not checkout or cid in result: raise ReleaseIdentityError("--component values must use unique COMPONENT_ID=CHECKOUT")
        result[cid] = checkout
    if not result: raise ReleaseIdentityError("at least one --component is required")
    return result

def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="astrid-release-identity"); sub = parser.add_subparsers(dest="operation", required=True); pre = sub.add_parser("pre-live"); pre.add_argument("--component", action="append", default=[]); pre.add_argument("--output"); candidate = sub.add_parser("candidate-core"); candidate.add_argument("--pre-live", required=True); candidate.add_argument("--component", action="append", default=[]); candidate.add_argument("--output"); verify = sub.add_parser("verify"); verify.add_argument("receipt"); args = parser.parse_args(argv)
    try:
        if args.operation == "pre-live": result = create_pre_live_identity(_component_args(args.component), output=args.output)
        elif args.operation == "candidate-core": result = create_candidate_core_identity(args.pre_live, _component_args(args.component), output=args.output)
        else: result = {"ok": True, "identity": load_receipt(args.receipt)["identity"]}
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2)); return 0
    except ReleaseIdentityError as exc: print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True)); return 1

if __name__ == "__main__": raise SystemExit(main())
