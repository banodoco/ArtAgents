"""Portable, closed release identity observations for the Stage 1 boundary."""
from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
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
GENERATOR_ROW_FIELDS = ("schema_version", "row_kind", "generator_id", "component_id", "entrypoint_component_id", "entrypoint_path", "entrypoint_sha256", "interpreter_tool_id", "argv_formula_id", "sandbox_policy_id", "generator_definition_sha256", "input_schema_ids", "input_digests", "declared_output_roots", "tool_ids", "output_paths", "output_digests", "tool_rows", "run_ordinal", "argv_carrier", "argv_sha256", "clean_checkout_id", "changed_paths", "undeclared_changed_paths", "started_at", "finished_at", "exit_code", "stop_class", "first_run_receipt_sha256", "second_run_receipt_sha256", "run_receipt_evidence_rows", "provenance_input_bindings", "producer_id")
RECEIPT_ROOT_ENVIRONMENTS = ("ASTRID_RELEASE_RECEIPT_ROOT", "BANODOCO_RELEASE_RECEIPT_ROOT", "RELEASE_RECEIPT_ROOT")

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
    identity = match.group(1) if match else remote.removesuffix(".git")
    return "banodoco-workspace-runtime-oracle" if identity == "banodoco/banodoco-workspace-runtime" else identity

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
    ref = _git_text(root, "symbolic-ref", "-q", "HEAD", optional=True) or head
    identity_bytes = canonical_bytes(git_identity(root)); identity_binding = {"input_id": f"GIT-IDENTITY:{component_id}", "sha256": _sha256_bytes(identity_bytes)}
    return _candidate_shape({"component_id": component_id, "repository_identity": _repo_identity(root), "source_ref": source_ref or ref, "base_oid": head, "base_tree_oid": tree, "integrated_oid": head, "integrated_tree_oid": tree, "subtree_sha256": framed_hash("banodoco.component-subtree.v1", [{"path": p, "oid": _git_text(root, "rev-parse", f"HEAD:{p}")} for p in scope]), "contract_sha256": _inventory_digest(root, contract), "generator_ids": generated, "dependency_lock_digests": [{"path": p, "sha256": _sha256_bytes(_git_bytes(root, "show", f"HEAD:{p}"))} for p in dependency], "fixture_digests": [{"path": p, "sha256": _sha256_bytes(_git_bytes(root, "show", f"HEAD:{p}"))} for p in fixtures], "tool_ids": ["TOOL-GIT"], "generator_observation_rows": [], "provenance_input_bindings": [identity_binding], "producer_id": "PROD-CMD-PACKET:B11.1", "epoch_profile_id": "EP-CRSM", "freshness_policy_id": "CURRENT-CLEAN-HEAD"})

def resolve_reviewed_components(components: Mapping[str, str | os.PathLike[str]], **kwargs: Any) -> list[dict[str, Any]]:
    if len(set(components)) != len(components): raise ReleaseIdentityError("component IDs must be unique")
    return sorted((resolve_component(cid, path, **kwargs) for cid, path in components.items()), key=lambda row: row["component_id"])

def _assert_clean(components: Mapping[str, str | os.PathLike[str]], output: str | os.PathLike[str] | None = None) -> None:
    if output is not None:
        target = Path(output).expanduser().resolve()
        for path in components.values():
            root = Path(path).expanduser().resolve()
            try:
                target.relative_to(root)
            except ValueError:
                continue
            raise ReleaseIdentityError("receipt output may not be inside a component checkout")
    dirty = []
    for cid, path in components.items():
        paths = _dirty_paths(Path(path).expanduser().resolve())
        if paths: dirty.append((cid, paths))
    if dirty: raise ReleaseIdentityError(f"candidate component has uncommitted changes: {dirty}")

def _plan_transition(cid: str, local: str, canonical: str, url: str, ref: str) -> str: return framed_hash("banodoco.local-to-canonical-repository.v1", [cid, local, canonical, url, ref])

def plan_component_registry() -> list[dict[str, Any]]:
    rows = [("NEUTRAL-RUNTIME", "banodoco-workspace-runtime-oracle", "banodoco/banodoco-workspace-runtime", "https://github.com/banodoco/banodoco-workspace-runtime.git"), ("ASTRID-CLIENT", "peteromallet/Astrid", "peteromallet/Astrid", "https://github.com/peteromallet/Astrid.git")]
    return [_nfc({"remote_target_id": f"REMOTE-TARGET:COMPONENT:{cid}", "target_kind": "component", "component_id": cid, "local_repository_identity": local, "repository_identity": canonical, "canonical_url": url, "destination_ref_or_prefix": "refs/heads/main", "expected_old_oid": NONE, "reviewed_source_oid": NONE, "identity_transition_sha256": _plan_transition(cid, local, canonical, url, "refs/heads/main"), "repository_provision_receipt_rows": NONE}) for cid, local, canonical, url in rows]

PLAN_COMPONENT_REGISTRY = tuple(plan_component_registry())

def plan_publication_row() -> dict[str, Any]: return {"remote_target_id": "REMOTE-TARGET:PUBLICATION", "target_kind": "publication", "component_id": NONE, "local_repository_identity": NONE, "repository_identity": "banodoco/banodoco-workspace-runtime", "canonical_url": "https://github.com/banodoco/banodoco-workspace-runtime.git", "destination_ref_or_prefix": "refs/tags/astrid-stage1-evidence/", "expected_old_oid": NONE, "reviewed_source_oid": NONE, "identity_transition_sha256": NONE, "repository_provision_receipt_rows": NONE}

def component_registry_sha256(rows: Sequence[Mapping[str, Any]] | None = None) -> str: return _sha256_bytes(canonical_bytes(list(rows if rows is not None else plan_component_registry())))

def _directory_inventory(root: Path) -> list[dict[str, str]]:
    rows = []
    if not root.is_dir(): raise ReleaseIdentityError("generator staging root is missing")
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink() or not path.is_file(): raise ReleaseIdentityError("generator output contains a non-regular entry")
        data = path.read_bytes(); rows.append({"path": relative, "sha256": _sha256_bytes(data), "byte_length": len(data)})
    return rows

def _clean_git_checkout(source: Path, destination: Path) -> None:
    result = subprocess.run(["git", "clone", "--quiet", "--no-hardlinks", str(source), str(destination)], capture_output=True, text=True, check=False, timeout=60)
    if result.returncode != 0: raise ReleaseIdentityError("B11.1 could not create a clean pinned checkout")
    subprocess.run(["git", "-C", str(destination), "checkout", "--quiet", "--detach", "HEAD"], check=True, timeout=30)

def run_b11_1(component_rows: Sequence[Mapping[str, Any]], generator_definitions: Sequence[Mapping[str, Any]], *, contract_bytes: bytes, schema_manifest_bytes: bytes, output_root: str | os.PathLike[str] | None = None) -> list[dict[str, Any]]:
    """Execute each declared B11.1 generator twice and attach observations.

    Commands are direct argv only.  Each run receives a fresh staging root and
    the complete input bytes; the two byte inventories must match exactly.
    """
    rows = [_candidate_shape(row) for row in component_rows]
    by_component = {row["component_id"]: row for row in rows}
    definitions = sorted((dict(defn) for defn in generator_definitions), key=lambda d: d.get("generator_id", ""))
    if not definitions: raise ReleaseIdentityError("B11.1 requires declared generator definitions")
    observed: dict[str, list[dict[str, Any]]] = {cid: [] for cid in by_component}
    with tempfile.TemporaryDirectory(dir=str(output_root) if output_root else None) as temp:
        base = Path(temp)
        for definition in definitions:
            gid = definition.get("generator_id"); cid = definition.get("component_id")
            if not isinstance(gid, str) or not isinstance(cid, str) or cid not in by_component: raise ReleaseIdentityError("B11.1 generator is not bound to a reviewed component")
            source_checkout = Path(definition.get("checkout", "")).expanduser().resolve()
            entrypoint = source_checkout / str(definition.get("entrypoint_path", ""))
            if not entrypoint.is_file() or entrypoint.is_symlink(): raise ReleaseIdentityError("B11.1 generator entrypoint is not a regular file")
            entrypoint_digest = _sha256_bytes(entrypoint.read_bytes()); inventories = []; receipts = []
            for ordinal in (1, 2):
                run_root = base / gid / str(ordinal); checkout = run_root / "checkout"; _clean_git_checkout(source_checkout, checkout); stage = run_root / "staging"; inputs = run_root / "inputs"; stage.mkdir(parents=True); inputs.mkdir()
                contract_path, schema_path = inputs / "contract.json", inputs / "schema-manifest.json"; contract_path.write_bytes(contract_bytes); schema_path.write_bytes(schema_manifest_bytes)
                executable = str(definition.get("interpreter_path") or definition.get("executable") or "python3")
                argv = [executable, str(entrypoint), "--contract", str(contract_path), "--schema-manifest", str(schema_path), "--output-root", str(stage)]
                before = _dirty_paths(checkout)
                result = subprocess.run(argv, cwd=str(checkout), capture_output=True, check=False, timeout=300, env={"PATH": os.environ.get("PATH", "")})
                after = _dirty_paths(checkout)
                if before != after: raise ReleaseIdentityError("B11.1 generator changed its checkout")
                if result.returncode != 0: raise ReleaseIdentityError(f"B11.1 generator failed: {gid}")
                inventory = _directory_inventory(stage)
                if not inventory: raise ReleaseIdentityError("B11.1 generator produced no output")
                inventories.append(inventory)
                stable_argv = ["<interpreter>", "<component-checkout>/" + str(definition["entrypoint_path"]), "--contract", "<contract-input>", "--schema-manifest", "<schema-manifest-input>", "--output-root", "<staging-output-root>"]
                receipt = {"schema_version": 1, "artifact_kind": "generator-run-receipt", "generator_id": gid, "run_ordinal": ordinal, "argv": stable_argv, "argv_sha256": framed_hash("banodoco.generator-run-argv.v1", stable_argv), "output_rows": inventory, "exit_code": result.returncode}
                receipts.append(receipt)
            if inventories[0] != inventories[1]: raise ReleaseIdentityError("B11.1 generator runs are not byte-identical")
            committed_root = definition.get("committed_output_root")
            if committed_root:
                committed = _directory_inventory(source_checkout / str(committed_root))
                normalized = [{**item, "path": item["path"]} for item in committed]
                if inventories[0] != normalized: raise ReleaseIdentityError("B11.1 staging inventory differs from committed generated-root inventory")
            output_paths = [item["path"] for item in inventories[0]]; output_digests = [item["sha256"] for item in inventories[0]]
            definition_digest = _sha256_bytes(canonical_bytes(definition)); receipt_rows = []
            for receipt in receipts:
                raw = canonical_bytes(receipt); wrapper = {"artifact_id": f"GENERATOR-RUN:{gid}:{receipt['run_ordinal']}", "artifact_kind": "generator-run-receipt", "artifact_schema_id": "evidence-artifact-v1", "media_type": "application/json", "path": f"embedded/generator-runs/{gid}/{receipt['run_ordinal']}.json", "byte_length": len(raw), "content_base64": base64.b64encode(raw).decode("ascii"), "content_sha256": _sha256_bytes(raw)}; wrapper["artifact_sha256"] = _sha256_bytes(canonical_bytes(wrapper)); receipt_rows.append(wrapper)
            observation = {"schema_version": 1, "row_kind": "OBSERVATION", "generator_id": gid, "component_id": cid, "entrypoint_component_id": cid, "entrypoint_path": str(definition["entrypoint_path"]), "entrypoint_sha256": entrypoint_digest, "interpreter_tool_id": definition.get("interpreter_tool_id", "TOOL-PYTHON"), "argv_formula_id": "GENERATOR-ARGV-V1", "sandbox_policy_id": "GENERATOR-READONLY-STAGING-V1", "generator_definition_sha256": definition_digest, "input_schema_ids": list(definition.get("input_schema_ids", [])), "input_digests": [_sha256_bytes(contract_bytes), _sha256_bytes(schema_manifest_bytes)], "declared_output_roots": list(definition.get("declared_output_roots", ["."])), "tool_ids": list(definition.get("tool_ids", ["TOOL-GIT", "TOOL-PYTHON"])), "output_paths": output_paths, "output_digests": output_digests, "tool_rows": list(definition.get("tool_rows", [])), "run_ordinal": NONE, "argv_carrier": NONE, "argv_sha256": NONE, "clean_checkout_id": NONE, "changed_paths": [], "undeclared_changed_paths": [], "started_at": NONE, "finished_at": NONE, "exit_code": NONE, "stop_class": NONE, "first_run_receipt_sha256": _sha256_bytes(canonical_bytes(receipts[0])), "second_run_receipt_sha256": _sha256_bytes(canonical_bytes(receipts[1])), "run_receipt_evidence_rows": receipt_rows, "provenance_input_bindings": [{"input_id": "CONTRACT-ID", "sha256": _sha256_bytes(contract_bytes)}, {"input_id": "EXECUTION-SCHEMAS-MANIFEST", "sha256": _sha256_bytes(schema_manifest_bytes)}, {"input_id": "GENERATOR-DEFINITION", "sha256": definition_digest}], "producer_id": "PROD-CMD-PACKET:B11.1"}
            if set(observation) != set(GENERATOR_ROW_FIELDS): raise ReleaseIdentityError("generator observation schema drift")
            observed[cid].append(observation)
    return [{**row, "generator_observation_rows": sorted(observed.get(row["component_id"], []), key=lambda item: item["generator_id"]), "generator_ids": [item["generator_id"] for item in sorted(observed.get(row["component_id"], []), key=lambda item: item["generator_id"])]} for row in rows]

execute_b11_1 = run_b11_1

def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != "github.com" or parsed.username or parsed.password or parsed.query or parsed.fragment or not re.fullmatch(r"/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\.git", parsed.path): raise ReleaseIdentityError("canonical URL must be an absolute credential-free HTTPS GitHub URL")

def _validate_locator(value: Any) -> None:
    if not isinstance(value, str): raise ReleaseIdentityError("remote locator URL must be a string")
    parsed = urlparse(value)
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.query or parsed.fragment or ".." in parsed.path.split("/"):
        raise ReleaseIdentityError("remote locator must be credential-free HTTPS without traversal")

def join_plan_remote_targets(component_rows: Sequence[Mapping[str, Any]], *, strict: bool = True, registry_rows: Sequence[Mapping[str, Any]] | None = None) -> list[dict[str, Any]]:
    rows = [_candidate_shape(r) for r in component_rows]; registry = [dict(r) for r in (registry_rows if registry_rows is not None else plan_component_registry())]
    if registry_rows is not None and _sha256_bytes(canonical_bytes(registry)) != component_registry_sha256(plan_component_registry()): raise ReleaseIdentityError("external plan registry digest mismatch")
    if len(registry) != 2 or len({r.get("remote_target_id") for r in registry}) != len(registry) or len({r.get("component_id") for r in registry}) != len(registry) or {r.get("component_id") for r in registry} != {"ASTRID-CLIENT", "NEUTRAL-RUNTIME"} or any(set(r) != set(REMOTE_TARGET_FIELDS) for r in registry): raise ReleaseIdentityError("plan registry rows are not exact, unique, and cardinality-two")
    by_id = {r["component_id"]: r for r in rows}
    if strict and set(by_id) != {r["component_id"] for r in registry}: raise ReleaseIdentityError("plan-owned component registry join is not total")
    result = []
    for target in registry:
        source = by_id.get(target["component_id"])
        if source is None or source["repository_identity"] != target["local_repository_identity"]: raise ReleaseIdentityError("local repository identity does not match plan registry")
        if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", source["integrated_oid"]): raise ReleaseIdentityError("reviewed_source_oid must be a full Git object ID")
        _validate_url(target["canonical_url"])
        if target["identity_transition_sha256"] != _plan_transition(target["component_id"], target["local_repository_identity"], target["repository_identity"], target["canonical_url"], target["destination_ref_or_prefix"]): raise ReleaseIdentityError("plan registry identity transition mismatch")
        item = copy.deepcopy(target); item["reviewed_source_oid"] = source["integrated_oid"]; result.append(item)
    result.append(plan_publication_row()); return result

def build_prelive_manifest(seed_outputs: Mapping[str, bytes | bytearray | Mapping[str, Any] | Sequence[Any]] | None = None, *, metadata: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if seed_outputs == {}: raise ReleaseIdentityError("PRELIVE-MANIFEST is missing required seed bytes")
    if seed_outputs is None: raise ReleaseIdentityError("PRELIVE-MANIFEST requires actual seed bytes")
    outputs = seed_outputs; seeds = list(PRELIVE_SEEDS); epochs = dict((metadata or {}).get("epochs", {"contract_epoch": NONE, "runtime_epoch": NONE, "source_epoch": NONE, "migration_epoch": NONE, "activation_epoch": NONE, "release_epoch": NONE})); evidence = []
    if set(outputs) != set(seeds): raise ReleaseIdentityError("PRELIVE-MANIFEST seed output set is not exactly 47 seeds")
    for seed in seeds:
        value = outputs[seed]
        if not isinstance(value, (bytes, bytearray)): raise ReleaseIdentityError("PRELIVE seed outputs must be complete bytes")
        data = bytes(value); digest = _sha256_bytes(data)
        evidence.append({"path": f"evidence/sha256/{digest[:2]}/{digest}", "sha256": digest, "producer_id": "CMD-PRELIVE-MANIFEST", "token_ids": [seed], "epochs": _nfc(epochs), "media_type": "application/json"})
    evidence.sort(key=lambda r: (r["path"], r["sha256"], r["producer_id"])); manifest = {"schema_version": PRELIVE_MANIFEST_SCHEMA, "governance_binding": "LOCAL-STAGE1-RELEASE", "seed_ids": seeds, "evidence_rows": evidence, "excluded_ids": list(PRELIVE_EXCLUDED_IDS), "epochs": _nfc(epochs)}; manifest["manifest_sha256"] = framed_hash("banodoco.pre-live-manifest.v1", manifest)
    if set(manifest) != set(PRELIVE_MANIFEST_FIELDS): raise ReleaseIdentityError("pre-live manifest schema drift")
    return manifest

def _seed_payload_wrappers(seed_outputs: Mapping[str, bytes | bytearray]) -> list[dict[str, Any]]:
    if set(seed_outputs) != set(PRELIVE_SEEDS): raise ReleaseIdentityError("PRELIVE seed payload set is not exactly 47 seeds")
    wrappers = []
    for seed in PRELIVE_SEEDS:
        value = seed_outputs[seed]
        if not isinstance(value, (bytes, bytearray)): raise ReleaseIdentityError("PRELIVE seed outputs must be complete bytes")
        content = bytes(value); inner = {"seed_id": seed, "media_type": "application/json", "byte_length": len(content), "content_base64": base64.b64encode(content).decode("ascii"), "content_sha256": _sha256_bytes(content)}
        raw = canonical_bytes(inner); wrappers.append({**inner, "artifact_sha256": _sha256_bytes(raw)})
    return wrappers

def _receipt_digest(receipt: Mapping[str, Any]) -> str: return framed_hash("banodoco.release-receipt.v1", {k: v for k, v in receipt.items() if k not in {"receipt_sha256", "identity"}})

def create_pre_live_identity(components: Mapping[str, str | os.PathLike[str]], *, metadata: Mapping[str, Any] | None = None, output: str | os.PathLike[str] | None = None, seed_outputs: Mapping[str, bytes | bytearray | Mapping[str, Any] | Sequence[Any]] | None = None, generator_definitions: Sequence[Mapping[str, Any]] | None = None, contract_bytes: bytes | None = None, schema_manifest_bytes: bytes | None = None) -> dict[str, Any]:
    _assert_clean(components, output); rows = resolve_reviewed_components(components)
    if generator_definitions is not None:
        if contract_bytes is None or schema_manifest_bytes is None: raise ReleaseIdentityError("B11.1 requires complete contract and schema-manifest bytes")
        rows = run_b11_1(rows, generator_definitions, contract_bytes=contract_bytes, schema_manifest_bytes=schema_manifest_bytes)
    metadata = dict(metadata or {}); planned = set(components) == {"ASTRID-CLIENT", "NEUTRAL-RUNTIME"}
    if seed_outputs is None and planned: raise ReleaseIdentityError("PRELIVE-MANIFEST requires actual bytes for all 47 seeds")
    if seed_outputs is None: seed_outputs = {seed: canonical_bytes({"seed_id": seed}) for seed in PRELIVE_SEEDS}
    manifest = build_prelive_manifest(seed_outputs, metadata=metadata); seed_wrappers = _seed_payload_wrappers(seed_outputs); evidence = []
    for row in rows:
        data = canonical_bytes(row); digest = _sha256_bytes(data); evidence.append({"path": f"evidence/sha256/{digest[:2]}/{digest}", "sha256": digest, "producer_id": "CMD-IDENTITY:pre-live-root", "token_ids": [row["component_id"]], "epochs": metadata.get("epochs", {}), "media_type": "application/json"})
    evidence.sort(key=lambda r: (r["path"], r["sha256"], r["producer_id"])); root_payload = {"component_rows": rows, "evidence_rows": evidence, "manifest_sha256": manifest["manifest_sha256"]}; identity = framed_hash("banodoco.pre-live-evidence-root.v1", root_payload)
    strict = set(r["component_id"] for r in rows) == {"ASTRID-CLIENT", "NEUTRAL-RUNTIME"} and all(r["repository_identity"] in {"peteromallet/Astrid", "banodoco-workspace-runtime-oracle"} for r in rows)
    locators = join_plan_remote_targets(rows) if strict else []
    identity_evidence = []
    for row in rows:
        binding = next((b for b in row["provenance_input_bindings"] if b.get("input_id") == f"GIT-IDENTITY:{row['component_id']}"), None)
        if binding is None: raise ReleaseIdentityError("candidate row lacks schema-legal Git identity evidence binding")
        identity_evidence.append({"artifact_id": binding["input_id"], "media_type": "application/json", "byte_length": len(canonical_bytes(git_identity(Path(components[row['component_id']])))), "content_base64": base64.b64encode(canonical_bytes(git_identity(Path(components[row['component_id']])))).decode("ascii"), "content_sha256": binding["sha256"]})
    receipt = {"schema_version": SCHEMA_VERSION, "kind": "pre-live-root", "operation_id": "CMD-IDENTITY:pre-live-root", "identity": identity, "pre_live_manifest": manifest, "pre_live_seed_payloads": seed_wrappers, "component_identity_evidence": identity_evidence, "evidence_rows": evidence, "component_rows": rows, "plan_registry_enforced": bool(locators), "remote_target_locators": locators, "remote_target_registry_sha256": component_registry_sha256(plan_component_registry()) if locators else NONE, "metadata": _nfc(metadata)}; receipt["receipt_sha256"] = _receipt_digest(receipt); _write_receipt(receipt, output); return receipt

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

def _configured_receipt_root() -> Path | None:
    for name in RECEIPT_ROOT_ENVIRONMENTS:
        value = os.environ.get(name)
        if value:
            return Path(value).expanduser().resolve()
    return None

def _safe_receipt_path(path: str | os.PathLike[str], root: Path | None = None) -> Path:
    raw = Path(path).expanduser()
    if ".." in raw.parts: raise ReleaseIdentityError("receipt path may not contain '..'")
    target_raw = raw.absolute(); target = target_raw.resolve(strict=False); current = Path(target_raw.anchor)
    for part in target.parts[1:-1]:
        current /= part
        if current.exists() and current.is_symlink() and current not in {Path("/tmp"), Path("/var")}: raise ReleaseIdentityError("receipt path contains a symlink")
    if target_raw.exists() and target_raw.is_symlink(): raise ReleaseIdentityError("receipt path is a symlink")
    if root is not None:
        try: target.relative_to(root)
        except ValueError: raise ReleaseIdentityError("receipt path is outside configured receipt root")
    return target

def _write_receipt(receipt: Mapping[str, Any], output: str | os.PathLike[str] | None) -> None:
    if output is None: return
    target = _safe_receipt_path(output, _configured_receipt_root()); target.parent.mkdir(parents=True, exist_ok=True); data = canonical_bytes(receipt) + b"\n"; target.write_bytes(data)
    if target.read_bytes() != data: raise ReleaseIdentityError("stored receipt bytes changed during write")

def verify_receipt(receipt: Mapping[str, Any]) -> str:
    if receipt.get("schema_version") != SCHEMA_VERSION or receipt.get("receipt_sha256") != _receipt_digest(receipt): raise ReleaseIdentityError("release receipt digest or schema mismatch")
    if receipt.get("kind") == "pre-live-root":
        manifest = receipt.get("pre_live_manifest")
        if not isinstance(manifest, Mapping) or set(manifest) != set(PRELIVE_MANIFEST_FIELDS) or manifest.get("schema_version") != PRELIVE_MANIFEST_SCHEMA or manifest.get("seed_ids") != list(PRELIVE_SEEDS) or len(manifest.get("seed_ids", [])) != 47: raise ReleaseIdentityError("PRELIVE-MANIFEST seed/schema projection mismatch")
        evidence = manifest.get("evidence_rows")
        if not isinstance(evidence, list) or len(evidence) != 47: raise ReleaseIdentityError("PRELIVE-MANIFEST evidence cardinality mismatch")
        for row in evidence:
            if set(row) != {"path", "sha256", "producer_id", "token_ids", "epochs", "media_type"} or row.get("producer_id") != "CMD-PRELIVE-MANIFEST" or row.get("media_type") != "application/json" or not isinstance(row.get("token_ids"), list) or len(row["token_ids"]) != 1 or row["token_ids"][0] not in PRELIVE_SEEDS or row.get("path") != f"evidence/sha256/{row.get('sha256','')[:2]}/{row.get('sha256','')}" or not re.fullmatch(r"[0-9a-f]{64}", str(row.get("sha256"))): raise ReleaseIdentityError("PRELIVE-MANIFEST evidence row mismatch")
        if {row["token_ids"][0] for row in evidence} != set(PRELIVE_SEEDS): raise ReleaseIdentityError("PRELIVE-MANIFEST evidence is not a bijection")
        payloads = receipt.get("pre_live_seed_payloads")
        if not isinstance(payloads, list) or len(payloads) != 47 or {p.get("seed_id") for p in payloads if isinstance(p, Mapping)} != set(PRELIVE_SEEDS): raise ReleaseIdentityError("PRELIVE seed payload wrappers are incomplete")
        for payload in payloads:
            if set(payload) != {"seed_id", "media_type", "byte_length", "content_base64", "content_sha256", "artifact_sha256"} or payload.get("media_type") != "application/json": raise ReleaseIdentityError("PRELIVE seed wrapper schema mismatch")
            try: content = base64.b64decode(payload["content_base64"], validate=True)
            except (ValueError, TypeError): raise ReleaseIdentityError("PRELIVE seed wrapper base64 is invalid")
            if payload["byte_length"] != len(content) or payload["content_sha256"] != _sha256_bytes(content): raise ReleaseIdentityError("PRELIVE seed wrapper content digest mismatch")
            if payload["artifact_sha256"] != _sha256_bytes(canonical_bytes({k: payload[k] for k in payload if k != "artifact_sha256"})): raise ReleaseIdentityError("PRELIVE seed wrapper artifact digest mismatch")
            matching = next(row for row in evidence if row["token_ids"] == [payload["seed_id"]])
            if matching["sha256"] != payload["content_sha256"]: raise ReleaseIdentityError("PRELIVE seed wrapper is not bound to manifest evidence")
        identity_evidence = receipt.get("component_identity_evidence")
        rows_for_identity = receipt.get("component_rows", [])
        if not isinstance(identity_evidence, list) or len(identity_evidence) != len(rows_for_identity): raise ReleaseIdentityError("component identity evidence is incomplete")
        for row in rows_for_identity:
            binding = next((b for b in row.get("provenance_input_bindings", []) if b.get("input_id") == f"GIT-IDENTITY:{row.get('component_id')}"), None)
            evidence_item = next((item for item in identity_evidence if item.get("artifact_id") == (binding or {}).get("input_id")), None)
            if binding is None or evidence_item is None or evidence_item.get("content_sha256") != binding.get("sha256"): raise ReleaseIdentityError("component Git identity is not bound by candidate row")
            try: identity_content = base64.b64decode(evidence_item["content_base64"], validate=True)
            except (ValueError, TypeError): raise ReleaseIdentityError("component identity evidence base64 is invalid")
            if _sha256_bytes(identity_content) != binding["sha256"] or evidence_item.get("byte_length") != len(identity_content): raise ReleaseIdentityError("component identity evidence digest mismatch")
        for row in rows_for_identity:
            for observation in row.get("generator_observation_rows", []):
                if set(observation) != set(GENERATOR_ROW_FIELDS): raise ReleaseIdentityError("generator observation schema mismatch")
                wrappers = observation.get("run_receipt_evidence_rows")
                if not isinstance(wrappers, list) or len(wrappers) != 2: raise ReleaseIdentityError("generator receipt evidence is incomplete")
                for wrapper in wrappers:
                    try: raw = base64.b64decode(wrapper["content_base64"], validate=True)
                    except (KeyError, ValueError, TypeError): raise ReleaseIdentityError("generator receipt wrapper base64 is invalid")
                    if wrapper.get("byte_length") != len(raw) or wrapper.get("content_sha256") != _sha256_bytes(raw) or wrapper.get("artifact_sha256") != _sha256_bytes(canonical_bytes({k: wrapper[k] for k in wrapper if k != "artifact_sha256"})): raise ReleaseIdentityError("generator receipt wrapper digest mismatch")
        if manifest.get("manifest_sha256") != framed_hash("banodoco.pre-live-manifest.v1", {k: manifest[k] for k in manifest if k != "manifest_sha256"}): raise ReleaseIdentityError("pre-live manifest digest mismatch")
        rows = _component_set(receipt.get("component_rows", [])); expected = framed_hash("banodoco.pre-live-evidence-root.v1", {"component_rows": [rows[k] for k in sorted(rows)], "evidence_rows": receipt.get("evidence_rows"), "manifest_sha256": manifest["manifest_sha256"]})
        planned_ids = {"ASTRID-CLIENT", "NEUTRAL-RUNTIME"}
        if receipt.get("plan_registry_enforced"):
            locators = receipt.get("remote_target_locators")
            if not isinstance(locators, list) or len(locators) != 3 or receipt.get("remote_target_registry_sha256") != component_registry_sha256(plan_component_registry()): raise ReleaseIdentityError("planned pre-live receipt lacks exact remote locators")
            if locators[-1] != plan_publication_row(): raise ReleaseIdentityError("publication locator is not the plan-owned row")
    elif receipt.get("kind") == "candidate-core":
        core = receipt.get("candidate_core")
        if not isinstance(core, Mapping) or set(core) != set(CANDIDATE_CORE_FIELDS): raise ReleaseIdentityError("candidate-core-object-v1 has unexpected or missing fields")
        expected = framed_hash("banodoco.candidate-core.v1", core)
    else: raise ReleaseIdentityError("unknown release receipt kind")
    if expected != receipt.get("identity"): raise ReleaseIdentityError("release identity mismatch")
    return expected

def load_receipt(path: str | os.PathLike[str]) -> dict[str, Any]:
    target = _safe_receipt_path(path, _configured_receipt_root())
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
            if {r.get("component_id") for r in result.get("component_rows", [])} == {"ASTRID-CLIENT", "NEUTRAL-RUNTIME"}: raise ReleaseIdentityError("planned component receipt requires remote locators")
            item = _nfc(dict(target)); tid = item.get("remote_target_id")
            if not isinstance(tid, str) or not tid or tid in seen: raise ReleaseIdentityError("remote target ids must be unique non-empty strings")
            seen.add(tid)
            if "canonical_url" in item: _validate_locator(item["canonical_url"])
            rows.append(item)
            continue
        if set(target) != set(REMOTE_TARGET_FIELDS): raise ReleaseIdentityError("remote-target-row-v1 has unexpected fields")
        item = _nfc(dict(target)); tid = item["remote_target_id"]
        if not isinstance(tid, str) or not tid or tid in seen: raise ReleaseIdentityError("remote target ids must be unique non-empty strings")
        seen.add(tid)
        if item["target_kind"] in {"component", "publication"}: _validate_url(item["canonical_url"])
        rows.append(item)
    result["remote_targets"] = sorted(rows, key=lambda r: r["remote_target_id"]); result["remote_target_registry_sha256"] = result.get("remote_target_registry_sha256") or (component_registry_sha256(plan_component_registry()) if result.get("remote_target_locators") else component_registry_sha256(rows)); result["receipt_sha256"] = _receipt_digest(result); return result

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
