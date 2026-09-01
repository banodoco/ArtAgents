"""Capture the executable Stage 1 evidence bundle.

``stage1_acceptance`` is deliberately a consumer.  This module is the small
operator-facing layer which runs the named Stage 1 gates, keeps their raw
output, and writes receipts in the consumer's format.  It has an explicit
table of gates rather than a configurable workflow language.

The migration, backup, and rollback rows are intentionally *not* runnable
here.  B12 is a live-data operation with a separate operator and custody
contract.  A later run may supply ``--b12-evidence-dir``; those receipts are
copied byte-for-byte (with their referenced artifacts) and are then verified
by the normal acceptance consumer.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from .stage1_acceptance import (
    CHECK_CATEGORY,
    RECEIPT_SCHEMA,
    REQUIRED_CATEGORIES,
    aggregate,
    sha256_bytes,
    sha256_file,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_CATEGORIES = frozenset({"migration", "backup_restore", "rollback"})
CAPTURE_CATEGORIES = tuple(
    category for category in REQUIRED_CATEGORIES if category not in MIGRATION_CATEGORIES
)
_LIVE_CATEGORIES = frozenset(
    {
        "cold_launch",
        "render",
        "second_client",
        "doctor",
        "security",
        "network",
        "filesystem",
    }
)
_HEX40 = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class GateSpec:
    """One named, fixed gate selection.

    ``selectors`` are repository-relative pytest selectors.  ``kind`` is
    either ``pytest`` or ``s1``; the latter delegates to the existing S1 gate
    and keeps its per-lane logs and JUnit files as evidence.
    """

    category: str
    selectors: tuple[str, ...]
    kind: str = "pytest"
    keyword: str | None = None


# Keep this table boring and reviewable.  The test files are the current Stage
# 1 proof surfaces; changing a selector is a release-evidence change.
GATE_SPECS: tuple[GateSpec, ...] = (
    GateSpec("schema_contracts", ("tests/test_capability_schema.py", "tests/core/rendering/test_contracts.py")),
    GateSpec("authority_census", ("tests/v10/test_authority_lint.py", "tests/stage1/test_zero_shim_final_authority_luna.py")),
    GateSpec("capability_census", ("tests/stage1/test_capability_parity_gate_luna.py",)),
    GateSpec("cold_launch", ("tests/stage1/test_final_cold_launch_matrix_luna.py",)),
    GateSpec("lifecycle", ("tests/integrations/test_stage1_cross_repository_acceptance.py", "tests/stage1/test_runtime_client_cutover.py")),
    GateSpec("ready_capabilities", ("tests/stage1/test_capability_parity_gate_luna.py",)),
    GateSpec("render", ("tests/integrations/test_generic_host_remotion_render.py", "tests/stage1/test_final_render_authority_luna.py")),
    GateSpec("second_client", ("tests/stage1/test_vendored_workspace_client_parity_luna.py", "tests/stage1/test_runtime_client_cutover.py")),
    GateSpec("conformance", ("tests/test_recoverability_conformance.py", "tests/core/rendering/test_conformance.py")),
    GateSpec("minimum_correctness", ("tests/stage1/test_remote_mutation_idempotency_luna.py", "tests/stage1/test_events_runtime_cutover.py")),
    GateSpec("doctor", ("tests/stage1/test_runtime_client_cutover.py",), keyword="doctor"),
    GateSpec("security", ("tests/stage1/test_launcher_credential_contract_luna.py", "tests/stage1/test_client_handshake_boundary_luna.py")),
    GateSpec("network", ("tests/integrations/test_generic_host_external_provider.py",), keyword="network"),
    GateSpec("filesystem", ("tests/stage1/test_zero_shim_timeline_cutover_luna.py", "tests/stage1/test_asset_cache_retired_luna.py")),
    GateSpec("static_scans", ("tests/v10/test_authority_lint.py", "tests/reshape/test_import_cycles.py", "tests/stage1/test_zero_shim_cycles.py")),
    GateSpec("docs", ("tests/stage1/test_docs_runtime_authority.py", "tests/stage1/test_supported_docs_no_retired_pack_guidance_luna.py")),
    GateSpec("isolated_composition", ("tests/stage1/test_generic_host_process_bootstrap_luna.py", "tests/integrations/test_stage1_cross_repository_acceptance.py")),
    # S1 is an existing focused gate and is retained under this category. Its
    # lane-level evidence is copied below; no broad pytest suite is selected.
    GateSpec("minimum_correctness", (), kind="s1"),
)


@dataclass(frozen=True)
class CommandResult:
    argv: tuple[str, ...]
    returncode: int
    passed: int
    failed: int
    skipped: int
    log_path: Path
    junit_path: Path | None
    output_dir: Path | None = None

    @property
    def status(self) -> str:
        return "pass" if self.returncode == 0 and self.passed > 0 and not self.failed and not self.skipped else "fail"


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _safe_slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-") or "gate"


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _parse_junit(path: Path) -> tuple[int, int, int]:
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return 0, 1, 0
    cases = list(root.iter("testcase"))
    passed = failed = skipped = 0
    for case in cases:
        if case.find("skipped") is not None:
            skipped += 1
        elif case.find("failure") is not None or case.find("error") is not None:
            failed += 1
        else:
            passed += 1
    return passed, failed, skipped


def _run_command(
    argv: Sequence[str], *, cwd: Path, log_path: Path, junit_path: Path | None,
    output_dir: Path | None = None,
) -> CommandResult:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        completed = subprocess.run(
            list(argv), cwd=cwd, text=True, capture_output=True, check=False
        )
        output = completed.stdout + completed.stderr
        returncode = completed.returncode
    except (OSError, subprocess.SubprocessError) as exc:
        output = f"capture command could not start: {exc}\n"
        returncode = 127
    log_path.write_text(output, encoding="utf-8")
    if junit_path is not None and junit_path.is_file():
        passed, failed, skipped = _parse_junit(junit_path)
    else:
        # A command which promised JUnit but did not produce it is a failed
        # proof. The log is retained to make the failure diagnosable.
        passed, failed, skipped = (0, 1, 0) if junit_path is not None else (1, 0, 0)
    return CommandResult(tuple(argv), returncode, passed, failed, skipped, log_path, junit_path if junit_path and junit_path.is_file() else None, output_dir)


def _pytest_command(spec: GateSpec, *, python: str, repo_root: Path, junit: Path) -> list[str]:
    argv = [python, "-m", "pytest", *spec.selectors, "-q", "--no-header", "-p", "no:cacheprovider", "--junit-xml", str(junit)]
    if spec.keyword:
        argv.extend(["-k", spec.keyword])
    return argv


def _run_spec(spec: GateSpec, *, evidence_dir: Path, repo_root: Path, python: str) -> CommandResult:
    slug = _safe_slug(spec.category + ("-s1" if spec.kind == "s1" else ""))
    run_dir = evidence_dir / "runs" / slug
    run_dir.mkdir(parents=True, exist_ok=True)
    log_path = run_dir / "combined.log"
    if spec.kind == "s1":
        gate_dir = run_dir / "s1-gate"
        argv = [python, "-m", "scripts.reshape.s1_gate", "--out-dir", str(gate_dir)]
        result = _run_command(argv, cwd=repo_root, log_path=log_path, junit_path=None, output_dir=gate_dir)
        # The S1 summary is the machine result. Count lanes conservatively;
        # the receipt still fails if any lane did not pass.
        summary = gate_dir / "s1-summary.json"
        if summary.is_file():
            try:
                payload = json.loads(summary.read_text(encoding="utf-8"))
                lanes = payload.get("lanes", {})
                result = CommandResult(result.argv, int(payload.get("exit", result.returncode)), sum(int(row.get("passed", 0)) for row in lanes.values()), sum(int(row.get("failed", 0)) for row in lanes.values()), sum(int(row.get("skipped", 0)) for row in lanes.values()), result.log_path, None, gate_dir)
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                pass
        else:
            # A zero exit from a wrapper is not evidence.  The existing S1
            # gate's machine summary is a required artifact and its absence
            # must remain a failed proof.
            result = CommandResult(result.argv, result.returncode or 1, 0, 1, 0, result.log_path, None, gate_dir)
        return result
    junit_path = run_dir / "junit.xml"
    return _run_command(_pytest_command(spec, python=python, repo_root=repo_root, junit=junit_path), cwd=repo_root, log_path=log_path, junit_path=junit_path)


def _copy_artifacts(result: CommandResult, *, evidence_dir: Path, category: str) -> list[dict[str, object]]:
    destination = evidence_dir / "artifacts" / _safe_slug(category)
    destination.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    copied_log = destination / "combined.log"
    shutil.copy2(result.log_path, copied_log)
    paths.append(copied_log)
    if result.junit_path is not None:
        copied_junit = destination / "junit.xml"
        shutil.copy2(result.junit_path, copied_junit)
        paths.append(copied_junit)
    if result.output_dir and result.output_dir.is_dir():
        retained = destination / "s1-gate"
        if retained.exists():
            shutil.rmtree(retained)
        shutil.copytree(result.output_dir, retained, symlinks=False)
        paths.extend(path for path in retained.rglob("*") if path.is_file())
    artifacts: list[dict[str, object]] = []
    for path in sorted(set(paths)):
        artifacts.append({"path": str(path.relative_to(evidence_dir)), "sha256": sha256_file(path), "kind": "gate-output" if path.name != "junit.xml" else "junit"})
    return artifacts


def _write_receipt(
    *, evidence_dir: Path, category: str, command: Sequence[str], result: CommandResult,
    artifacts: Sequence[Mapping[str, object]], extra_observations: Mapping[str, object] | None = None,
) -> Path:
    status = result.status
    observation: dict[str, object] = {
        "evidence_mode": "live" if category in _LIVE_CATEGORIES else "automated",
        "command_status": status,
        "returncode": result.returncode,
        "passed": result.passed,
        "failed": result.failed,
        "skipped": result.skipped,
        "artifacts": len(artifacts),
    }
    if extra_observations:
        observation.update(extra_observations)
    checks = []
    for check_id, check_category in CHECK_CATEGORY.items():
        if check_category != category:
            continue
        checks.append({
            "id": check_id,
            "status": status,
            "observations": {"gate": list(command), "result": "observed" if status == "pass" else "not-proven"},
            "artifacts": list(artifacts),
        })
    payload = {
        "schema": RECEIPT_SCHEMA,
        "receipt_id": f"capture-{_safe_slug(category)}",
        "category": category,
        "status": status,
        "observed_at": _utc_now(),
        "command": list(command),
        "observations": observation,
        "checks": checks,
    }
    path = evidence_dir / "receipts" / f"{_safe_slug(category)}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_canonical(payload))
    return path


def _git_output(repo: Path, argv: Sequence[str]) -> tuple[int, str, str]:
    try:
        completed = subprocess.run(["git", "-C", str(repo), *argv], capture_output=True, text=True, check=False)
    except OSError as exc:
        return 127, "", str(exc)
    return completed.returncode, completed.stdout, completed.stderr


def _static_receipt(evidence_dir: Path, *, category: str, observations: Mapping[str, object], artifact_payload: object, command: Sequence[str], ok: bool = True) -> Path:
    artifact_path = evidence_dir / "artifacts" / "static" / f"{_safe_slug(category)}.json"
    _write(artifact_path, _canonical(artifact_payload))
    artifact = {"path": str(artifact_path.relative_to(evidence_dir)), "sha256": sha256_file(artifact_path), "kind": "derived-static-proof"}
    fake_result = CommandResult(tuple(command), 0 if ok else 1, 1 if ok else 0, 0 if ok else 1, 0, artifact_path, None)
    return _write_receipt(evidence_dir=evidence_dir, category=category, command=command, result=fake_result, artifacts=[artifact], extra_observations=observations)


def _capture_source_identity(evidence_dir: Path, repo_root: Path) -> Path:
    rows: list[dict[str, object]] = []
    errors: list[str] = []
    runtime = repo_root.parent / "banodoco-workspace-runtime-stage1-convergence"
    for name, path in (("astrid", repo_root), ("runtime", runtime)):
        code, commit, stderr = _git_output(path, ["rev-parse", "HEAD"])
        code_tree, tree, tree_err = _git_output(path, ["ls-files", "-s"])
        code_dirty, dirty, dirty_err = _git_output(path, ["diff", "--binary", "--no-ext-diff"])
        commit = commit.strip()
        if code or not _HEX40.fullmatch(commit):
            errors.append(f"{name}: cannot obtain exact commit ({stderr.strip() or 'missing repository'})")
        rows.append({"name": name, "commit": commit, "dirty": bool(dirty.strip()), "dirty_digest": sha256_bytes(dirty.encode()), "tree_digest": sha256_bytes(tree.encode()), "root": name})
        if code_tree:
            errors.append(f"{name}: cannot obtain tracked tree ({tree_err.strip()})")
        if code_dirty:
            errors.append(f"{name}: cannot inspect dirty tree ({dirty_err.strip()})")
    payload = {"repositories": rows, "errors": errors}
    observations = {"repositories": rows, "capture_errors": errors, "evidence_mode": "automated"}
    return _static_receipt(evidence_dir, category="source_identity", observations=observations, artifact_payload=payload, command=["git", "rev-parse", "HEAD"], ok=not errors)


def _hashed_files(repo_root: Path, paths: Iterable[Path]) -> list[dict[str, object]]:
    rows = []
    for path in paths:
        if not path.is_file():
            continue
        rows.append({"name": path.name, "path": str(path.relative_to(repo_root)), "sha256": sha256_file(path)})
    return sorted(rows, key=lambda row: (str(row["name"]), str(row["path"])))


def _capture_digests(evidence_dir: Path, repo_root: Path, category: str, files: Iterable[Path], key: str) -> Path:
    rows = _hashed_files(repo_root, files)
    observations = {key: rows, "evidence_mode": "automated"}
    return _static_receipt(evidence_dir, category=category, observations=observations, artifact_payload=observations, command=["sha256", key], ok=bool(rows))


def _import_b12(evidence_dir: Path, source_dir: Path) -> list[Path]:
    """Copy exact B12 receipts/artifacts into the portable bundle.

    No receipt is synthesized or rewritten.  The source tree is copied as a
    whole so relative artifact references retain their original meaning.
    """
    source_dir = source_dir.expanduser().resolve()
    if not source_dir.is_dir():
        raise ValueError(f"B12 evidence directory is missing: {source_dir}")
    destination = evidence_dir / "b12"
    destination.mkdir(parents=True, exist_ok=True)
    imported: list[Path] = []
    for source in sorted(source_dir.rglob("*")):
        if source.is_symlink():
            raise ValueError(f"B12 evidence contains a symlink; refusing non-portable artifact: {source.relative_to(source_dir)}")
        if not source.is_file() or source.name in {"acceptance.json", "acceptance-report.json"}:
            continue
        relative = source.relative_to(source_dir)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        if target.suffix == ".json":
            try:
                payload = json.loads(target.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError(f"B12 JSON artifact is unreadable: {relative}: {exc}") from exc
            if isinstance(payload, Mapping) and payload.get("schema") == RECEIPT_SCHEMA:
                if payload.get("category") not in MIGRATION_CATEGORIES:
                    target.unlink()
                    continue
                imported.append(target)
    if not imported:
        raise ValueError("B12 evidence directory contains no migration/backup/rollback receipts")
    return imported


def capture_evidence(
    evidence_dir: Path,
    *,
    repo_root: Path = REPO_ROOT,
    python: str = sys.executable,
    categories: Sequence[str] = CAPTURE_CATEGORIES,
    include_s1: bool = True,
    b12_evidence_dir: Path | None = None,
    run_commands: bool = True,
) -> tuple[dict[str, object], int]:
    """Capture selected non-B12 categories, optionally import exact B12 rows.

    ``run_commands=False`` is intended only for focused contract tests where
    the command runner is monkeypatched; it still emits no passing live proof
    by itself.  Production callers should leave it true.
    """
    evidence_dir = evidence_dir.expanduser().resolve()
    repo_root = repo_root.expanduser().resolve()
    evidence_dir.mkdir(parents=True, exist_ok=True)
    selected = tuple(dict.fromkeys(categories))
    unknown = [category for category in selected if category not in CAPTURE_CATEGORIES]
    if unknown:
        raise ValueError(f"unsupported capture categories: {', '.join(unknown)}")
    _capture_source_identity(evidence_dir, repo_root) if "source_identity" in selected else None
    if "dependency_locks" in selected:
        _capture_digests(evidence_dir, repo_root, "dependency_locks", sorted((repo_root / "requirements").glob("*.lock")), "locks")
    if "source_manifests" in selected:
        _capture_digests(evidence_dir, repo_root, "source_manifests", [repo_root / "config" / "astrid-beta-capabilities.json", repo_root / "remotion" / "package-lock.json"], "manifests")
    if run_commands:
        # Run the existing focused S1 gate once.  Its twelve lane outputs are
        # attached to minimum_correctness below; it is a prerequisite, not a
        # second receipt category.
        if include_s1 and "minimum_correctness" in selected:
            s1_spec = next(spec for spec in GATE_SPECS if spec.kind == "s1")
            s1_result = _run_spec(s1_spec, evidence_dir=evidence_dir, repo_root=repo_root, python=python)
            s1_artifacts = _copy_artifacts(s1_result, evidence_dir=evidence_dir, category="minimum_correctness-s1")
            _write_receipt(evidence_dir=evidence_dir, category="minimum_correctness", command=s1_result.argv, result=s1_result, artifacts=s1_artifacts, extra_observations={"gate": "s1_gate"})
        seen: set[str] = set()
        for spec in GATE_SPECS:
            if spec.category not in selected or spec.category in seen:
                continue
            if spec.kind == "s1" or (spec.category == "minimum_correctness" and include_s1):
                continue
            seen.add(spec.category)
            result = _run_spec(spec, evidence_dir=evidence_dir, repo_root=repo_root, python=python)
            artifacts = _copy_artifacts(result, evidence_dir=evidence_dir, category=spec.category)
            _write_receipt(evidence_dir=evidence_dir, category=spec.category, command=result.argv, result=result, artifacts=artifacts)
    if b12_evidence_dir is not None:
        _import_b12(evidence_dir, b12_evidence_dir)
    return aggregate(evidence_dir, evidence_dir.parent / "stage1-acceptance", repo_root=repo_root)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run named Stage 1 gates and capture hash-linked evidence.")
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--categories", help="Comma-separated non-B12 category subset (default: all).")
    parser.add_argument("--b12-evidence-dir", type=Path, help="Exact real B12 migration/backup/rollback evidence directory.")
    parser.add_argument("--no-s1", action="store_true", help="Skip the existing focused s1_gate (for local debugging only).")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    categories = CAPTURE_CATEGORIES if not args.categories else tuple(item.strip() for item in args.categories.split(",") if item.strip())
    try:
        report, exit_code = capture_evidence(args.evidence_dir, repo_root=args.repo_root, python=args.python, categories=categories, include_s1=not args.no_s1, b12_evidence_dir=args.b12_evidence_dir)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"stage1 evidence capture: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"status": report["status"], "ok": report["ok"], "report": str(args.evidence_dir.parent / "stage1-acceptance" / "acceptance.json"), "hash": report["hashes"]["report"]}, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
