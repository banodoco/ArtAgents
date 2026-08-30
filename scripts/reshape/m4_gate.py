"""m4 finalizer admission gate (plan Step 33 / task T37).

The m4 gate is the final admission boundary for the bridge, SDK, and CLI
domains sprint. It composes already-focused lanes rather than changing any
runtime semantics:

- **retained focused lanes** (whole test files, never individual nodes) for
  contracts, application composition, the exclusive-owner lock, SDK services,
  CLI surface/help, bridge/provider, media/task/run/pack conformance,
  crash/contention, secrets, the platform matrix, and the authority lint;
- **authority lint** over the live tree (kernel-to-pack imports,
  pack-to-pack imports, writers outside the kernel store, legacy
  authorities on supported entry paths, schema ownership, forbidden
  vocabulary, and declared-table/index rules), with the two
  manifest-declared nested-mount parser edges (timelines→shots,
  media→references) recorded as documented composition exemptions — any
  other error fails closed;
- **forbidden drift rejection**: schema/catalog composition drift (the frozen
  23-table catalog: kernel 14 + timeline 1 + shots 4 + references 3 +
  Runaway 1),
  product surface drift (exactly five top-level families, two
  manifest-declared nested mounts, no ``timelines copy`` route), SDK surface
  drift (no public raw runner promises), and sentinel-secret persistence in
  retained evidence;
- **feasibility admission**: a present, parseable, accepted
  (``admitted: true``) megaplan feasibility record is required before the
  gate can succeed — a missing or rejected admission fails closed;
- **Python 3.11/3.12 matrix**: the primary interpreter must be CPython
  3.11 or 3.12; when a secondary interpreter is discoverable (``python3.12``
  first, then ``python3.13``), a cheap matrix lane runs under it. CI's
  matrix job is the authoritative 3.12 execution;
- **Reigh editor lane**: retained disposition evidence only (SD1) — the
  external compatibility report is referenced and validated when present but
  is never an input to gate success.

Evidence: every lane keeps a log and JUnit XML under ``out/m4-gate/latest``
(gitignored, same convention as ``out/s1-gate/latest``), and the gate retains
one schema-versioned admission document at ``artifacts/m4/finalizer-
admission.json`` that is re-read and re-validated before exit 0 (fail
closed on absent, truncated, or malformed retained evidence).

Usage::

    python3 scripts/reshape/m4_gate.py [--out PATH] [--feasibility PATH]
        [--python PY] [--python-secondary PY] [--selectors a,b]
        [--check-only]

Exit status is 0 only when the feasibility admission is present and
accepted, the authority lint is clean, no forbidden drift is found, every
focused lane passed, any executed secondary-matrix lane passed, and the
retained admission document was written and re-validated.
"""

from __future__ import annotations

import argparse
import ast
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

GATE_SCHEMA = "astrid.m4_finalizer_admission.v1"
DEFAULT_OUT = REPO_ROOT / "artifacts" / "m4" / "finalizer-admission.json"
DEFAULT_EVIDENCE_DIR = REPO_ROOT / "out" / "m4-gate" / "latest"
DEFAULT_FEASIBILITY = (
    REPO_ROOT
    / ".megaplan"
    / "plans"
    / "m4-bridge-sdk-and-cli-domains-20260818-0642"
    / "task_feasibility.json"
)

BASELINE_SCHEMA = "astrid.m4_baseline.v1"
DISPOSITION_SCHEMA = "astrid.reigh_external_gate_disposition.v1"

# Sentinel value the secrets lane proves never persists or prints (frozen by
# tests/core/util/test_secrets.py). The gate additionally scans every
# retained m4 evidence artifact for it.
SENTINEL = "astrid-sentinel-secret-7f3c9d"

# Frozen composition: kernel 14 + timeline 1 + shots 4 + references 3 + runaway 1.
FROZEN_TABLE_COUNT = 23
"""The frozen standard composition total (core + declared pack tables)."""
FROZEN_CORE_TABLE_COUNT = 14
FROZEN_PACK_TABLES: dict[str, frozenset[str]] = {
    "timeline": frozenset({"timelines"}),
    "shots": frozenset(
        {"shots", "shot_items", "generations", "generation_variants"}
    ),
    "references": frozenset(
        {"project_references", "media_references", "reference_links"}
    ),
    "runaway": frozenset({"runaway_transitions"}),
}
FROZEN_STANDARD_PACKS = ("timeline", "shots", "references", "runaway")

# Frozen product surface (m4 plan step 24 / sense check SC25).
FROZEN_PRODUCT_FAMILIES = ("projects", "media", "tasks", "runs", "timelines")
FROZEN_EXCLUDED_CENSUS = frozenset({"serve", "doctor", "run"})
FROZEN_MANIFEST_MOUNTS: dict[str, tuple[str, ...]] = {
    "timelines": ("timelines",),
    "shots": ("timelines", "shots"),
    "references": ("media", "references"),
}
FROZEN_NESTED_FAMILIES = frozenset({"shots", "references"})
FROZEN_PRODUCT_TIMELINE_VERBS = frozenset(
    {"create", "list", "show", "save", "archive", "history", "diff"}
)

# Frozen SDK surface: the curated public exports keep lazy discovery, typed
# invoke, generate, render, and event reads; the raw runner seams are
# deliberately absent from ``__all__`` (m4 plan step 19 / task T20).
FROZEN_SDK_REQUIRED_EXPORTS = frozenset(
    {
        "AstridClient",
        "discover",
        "get_capability",
        "invoke",
        "generate",
        "render",
        "read_events",
        "subscribe_events",
    }
)
FROZEN_SDK_FORBIDDEN_EXPORTS = frozenset({"run_executor", "run_orchestrator"})

# Primary interpreter must be a supported matrix CPython (3.11 or 3.12).
PRIMARY_PYTHON_ALLOWED = ((3, 11), (3, 12))

# Documented product-CLI composition edges (m4 plan steps 26/27, tasks
# T29/T30): the nested-mount family parsers embed the manifest-declared
# nested parser exactly as ``astrid/core/gateway/dispatch.py`` is the one
# application-composition root. These are static, manifest-declared edges
# (``REQUIRED_MANIFEST_MOUNTS`` / ``FAMILY_PARSER_MODULES``), never dynamic
# discovery, and the imported modules are pure argparse builders with no
# SQL or repository logic. The gate records them as accepted exemptions;
# any other authority-lint error fails closed. (The static lint module
# itself is outside T37's write set, so the exemption is enforced here.)
CLI_MOUNT_IMPORT_EXEMPTIONS: frozenset[tuple[str, str]] = frozenset(
    {
        # The shots pack parser embedded beneath the timelines family.
        ("astrid/packs/timeline/cli.py", "astrid.packs.shots"),
        ("astrid/packs/timeline/cli.py", "astrid.packs.shots.cli"),
        # The references pack parser embedded beneath the media family.
        ("astrid/core/cli/domain_media.py", "astrid.packs.references"),
        ("astrid/core/cli/domain_media.py", "astrid.packs.references.cli"),
    }
)

_IMPORT_ERROR_RE = re.compile(
    r"^(?P<rel>[^:]+): (?:kernel-to-pack|pack-to-pack) import "
    r"'(?P<module>[^']+)'"
)

# The focused m4 gate lanes (plan Step 33): whole test files only.
LANES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("contracts", ("tests/v10/test_m4_contracts.py", "tests/sdk/test_domain_contracts.py")),
    (
        "composition",
        ("tests/v10/test_standard_application.py", "tests/v10/test_pack_factoring.py"),
    ),
    ("owner_lock", ("tests/v10/test_writer_authority.py",)),
    (
        "services",
        (
            "tests/sdk/test_projects.py",
            "tests/sdk/test_timelines.py",
            "tests/sdk/test_media.py",
            "tests/sdk/test_tasks.py",
            "tests/sdk/test_runs.py",
            "tests/sdk/test_references.py",
            "tests/sdk/test_shots.py",
        ),
    ),
    (
        "cli",
        (
            "tests/v10/test_domain_cli_surface.py",
            "tests/v10/test_domain_cli_projects_timelines.py",
            "tests/v10/test_domain_cli_media_references.py",
            "tests/v10/test_domain_cli_tasks_runs.py",
            "tests/test_cli_registration_conformance.py",
            "tests/test_canonical_aliases.py",
            "tests/test_canonical_entrypoint.py",
        ),
    ),
    (
        "bridge",
        (
            "tests/integrations/reigh/test_repository_provider.py",
            "tests/v10/test_shared_service_authority.py",
        ),
    ),
    (
        "media_conformance",
        ("tests/v10/test_media_pipeline.py", "tests/v10/test_media_repository.py"),
    ),
    (
        "task_run_conformance",
        (
            "tests/v10/test_task_lifecycle.py",
            "tests/v10/test_multi_task_journey.py",
        ),
    ),
    (
        "pack_conformance",
        (
            "tests/v10/test_reference_conformance.py",
            "tests/v10/test_shot_conformance.py",
        ),
    ),
    (
        "crash_contention",
        ("tests/v10/test_crash_atomicity.py", "tests/v10/test_contention.py"),
    ),
    (
        "secrets",
        (
            "tests/core/util/test_secrets.py",
            "tests/core/test_credentials_scope.py",
            "tests/packs/rendering/test_sprite_sheet.py",
        ),
    ),
    (
        "platform",
        (
            "tests/test_platform_contract.py",
            "tests/test_sdk_public_surface.py",
            "tests/sdk/test_zero_secret_smoke.py",
        ),
    ),
    ("authority_lint", ("tests/v10/test_authority_lint.py",)),
)

# Cheap secondary-matrix smoke (contracts + authority lint + platform): run
# under a secondary interpreter when one is discoverable.
SECONDARY_MATRIX_SELECTORS: tuple[str, ...] = (
    "tests/v10/test_m4_contracts.py",
    "tests/v10/test_authority_lint.py",
    "tests/test_platform_contract.py",
    "tests/sdk/test_domain_contracts.py",
)

_VERSION_RE = re.compile(r"(\d+)\.(\d+)(?:\.(\d+))?")


def _utc_timestamp() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _git_sha(repo_root: Path) -> str:
    """Return the repository HEAD SHA, or raise on a non-git checkout."""
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "cannot resolve git HEAD SHA "
            f"(exit {completed.returncode}): {completed.stderr.strip()}"
        )
    return completed.stdout.strip()


def _write_atomic(path: Path, payload: dict[str, object]) -> None:
    """Write atomically so a hard kill never leaves a truncation."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp_path, path)


def _parse_junit(junit_path: Path) -> tuple[int, int, int]:
    """Return ``(passed, failed, skipped)`` from a JUnit XML file."""
    tree = ET.parse(junit_path)
    root = tree.getroot()
    suite = root if root.tag == "testsuite" else root.find("testsuite")
    if suite is None:
        return 0, 0, 0
    tests = int(suite.get("tests", 0))
    failures = int(suite.get("failures", 0))
    errors = int(suite.get("errors", 0))
    skipped = int(suite.get("skipped", 0))
    return tests - failures - errors - skipped, failures + errors, skipped


def _lane_status(passed: int, failed: int, skipped: int) -> str:
    if failed > 0:
        return "fail"
    if passed == 0 and skipped > 0:
        return "skip"
    return "pass"


@dataclass(frozen=True)
class LaneResult:
    """Durable outcome of one gate lane run, including evidence paths."""

    name: str
    selectors: tuple[str, ...]
    passed: int
    failed: int
    skipped: int
    status: str
    returncode: int
    duration_seconds: float
    log: str
    junit: str

    def as_dict(self) -> dict[str, object]:
        return {
            "selectors": list(self.selectors),
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "status": self.status,
            "returncode": self.returncode,
            "duration_seconds": round(self.duration_seconds, 3),
            "log": self.log,
            "junit": self.junit,
        }


def _run_lane(
    name: str,
    selectors: tuple[str, ...],
    *,
    python: str,
    repo_root: Path,
    evidence_dir: Path,
) -> LaneResult:
    """Run one lane's pytest selection and record its durable evidence."""
    junit_path = evidence_dir / f"{name}-junit.xml"
    log_path = evidence_dir / f"{name}.log"
    argv = [
        python,
        "-m",
        "pytest",
        *selectors,
        "-q",
        "--no-header",
        "-p",
        "no:cacheprovider",
        "--junit-xml",
        str(junit_path),
    ]
    started = time.monotonic()
    completed = subprocess.run(
        argv,
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    duration_seconds = time.monotonic() - started
    log_path.write_text(
        completed.stdout + completed.stderr, encoding="utf-8"
    )
    if junit_path.exists():
        passed, failed, skipped = _parse_junit(junit_path)
    else:
        if completed.returncode == 0:
            passed, failed, skipped = 1, 0, 0
        else:
            passed, failed, skipped = 0, 1, 0
    return LaneResult(
        name=name,
        selectors=selectors,
        passed=passed,
        failed=failed,
        skipped=skipped,
        status=_lane_status(passed, failed, skipped),
        returncode=completed.returncode,
        duration_seconds=duration_seconds,
        log=str(log_path.relative_to(repo_root)),
        junit=str(junit_path.relative_to(repo_root)),
    )


def _interpreter_version(python: str) -> tuple[int, int, int] | None:
    """Return ``(major, minor, patch)`` for an interpreter, or ``None``."""
    try:
        completed = subprocess.run(
            [python, "--version"],
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    raw = completed.stdout.strip() or completed.stderr.strip()
    match = _VERSION_RE.search(raw)
    if match is None:
        return None
    return (int(match.group(1)), int(match.group(2)), int(match.group(3) or 0))


def _interpreter_has_pytest(python: str) -> bool:
    """Whether *python* can run pytest (the matrix lane's harness)."""
    try:
        completed = subprocess.run(
            [python, "-m", "pytest", "--version"],
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return completed.returncode == 0


def _discover_secondary() -> str | None:
    """Discover a secondary interpreter: ``python3.12`` then ``python3.13``.

    pyenv shims for non-active versions are not directly executable, so a
    shim that fails its version probe is resolved to the real binary under
    ``<pyenv>/versions/*/bin`` when one exists.
    """
    for name in ("python3.12", "python3.13"):
        resolved = shutil.which(name)
        if resolved is not None and _interpreter_version(resolved) is not None:
            return resolved
        for version_root in (
            Path.home() / ".pyenv" / "versions",
            Path("/root/.pyenv/versions"),
        ):
            if not version_root.is_dir():
                continue
            for version_dir in sorted(version_root.iterdir(), reverse=True):
                candidate = version_dir / "bin" / name
                if candidate.is_file() and _interpreter_version(str(candidate)) is not None:
                    return str(candidate)
    return None


# ---------------------------------------------------------------------------
# Feasibility admission (fail closed on missing or rejected admission)
# ---------------------------------------------------------------------------


def _check_feasibility(path: Path) -> tuple[dict[str, object], list[str]]:
    """Require a present, parseable, accepted feasibility admission.

    Returns ``(record, problems)``; problems are non-empty (fail closed)
    when the admission is absent, malformed, or not accepted.
    """
    problems: list[str] = []
    record: dict[str, object] = {"path": str(path)}
    if not path.is_file():
        problems.append(
            f"feasibility admission absent at {path}; "
            "gate success requires a present accepted admission"
        )
        record["present"] = False
        return record, problems
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        problems.append(f"feasibility admission unreadable at {path}: {exc}")
        record["present"] = True
        record["parseable"] = False
        return record, problems
    if not isinstance(data, dict):
        problems.append(f"feasibility admission at {path} is not a JSON object")
        record["present"] = True
        record["parseable"] = False
        return record, problems
    record["present"] = True
    record["parseable"] = True
    record["schema_version"] = data.get("schema_version")
    record["plan_hash"] = data.get("plan_hash")
    record["task_contract_hash"] = data.get("task_contract_hash")
    record["task_count"] = data.get("task_count")
    admitted = data.get("admitted")
    if not isinstance(admitted, bool) or not admitted:
        problems.append(
            f"feasibility admission at {path} is not accepted "
            f"(admitted={admitted!r})"
        )
        record["admitted"] = admitted
        return record, problems
    record["admitted"] = True
    record["accepted"] = True
    return record, problems


# ---------------------------------------------------------------------------
# Authority lint and forbidden drift checks (fail closed)
# ---------------------------------------------------------------------------


def _classify_authority_errors(
    errors: Sequence[str],
) -> tuple[list[str], list[str]]:
    """Split lint errors into violations vs documented CLI-mount exemptions.

    Returns ``(violations, exemptions)``; only *violations* fail the gate.
    """
    violations: list[str] = []
    exemptions: list[str] = []
    for error in errors:
        match = _IMPORT_ERROR_RE.match(error)
        if match and (match.group("rel"), match.group("module")) in (
            CLI_MOUNT_IMPORT_EXEMPTIONS
        ):
            exemptions.append(error)
        else:
            violations.append(error)
    return violations, exemptions


def _run_authority_lint() -> tuple[bool, list[str], list[str]]:
    """Run the deterministic live-tree authority lint.

    Returns ``(ok, violations, exemptions)`` where *exemptions* are the
    exactly-two documented nested-mount parser composition edges.
    """
    from scripts.reshape.authority_lint import run_authority_lint

    report = run_authority_lint(REPO_ROOT)
    violations, exemptions = _classify_authority_errors(report.errors)
    return not violations, violations, exemptions


def _check_schema_composition() -> tuple[bool, list[str], dict[str, object]]:
    """Reject schema/catalog drift from the frozen 23-table composition."""
    violations: list[str] = []
    from astrid.core.migrations.catalog import CORE_TABLES, FORBIDDEN_TABLES
    from astrid.core.schema_packs.manifest import load_schema_pack_manifest
    from astrid.packs import STANDARD_SCHEMA_PACKS, build_standard_registry

    core_count = len(CORE_TABLES)
    if core_count != FROZEN_CORE_TABLE_COUNT:
        violations.append(
            f"core catalog drift: {core_count} kernel tables != "
            f"{FROZEN_CORE_TABLE_COUNT}"
        )

    packs_root = REPO_ROOT / "astrid" / "packs"
    declared: dict[str, str] = {}
    manifest_pack_ids: list[str] = []
    for pack_dir in sorted(p for p in packs_root.iterdir() if p.is_dir()):
        manifest_path = pack_dir / "schema-pack.yaml"
        if not manifest_path.is_file():
            continue
        manifest = load_schema_pack_manifest(manifest_path)
        manifest_pack_ids.append(manifest.id)
        declared.update(
            {
                table: manifest.id
                for migration in manifest.migrations
                for table in migration.tables
            }
        )
    if tuple(sorted(manifest_pack_ids)) != tuple(sorted(STANDARD_SCHEMA_PACKS)):
        violations.append(
            f"schema-pack drift: found packs {sorted(manifest_pack_ids)} != "
            f"standard {sorted(STANDARD_SCHEMA_PACKS)}"
        )
    for pack_id, expected in FROZEN_PACK_TABLES.items():
        actual = frozenset(
            table for table, owner in declared.items() if owner == pack_id
        )
        if actual != expected:
            violations.append(
                f"pack {pack_id!r} table drift: {sorted(actual)} != {sorted(expected)}"
            )
    total = len(CORE_TABLES) + len(declared)
    if total != FROZEN_TABLE_COUNT:
        violations.append(
            f"composition table count {total} != frozen {FROZEN_TABLE_COUNT}"
        )
    forbidden_hit = sorted(set(declared) & set(FORBIDDEN_TABLES))
    if forbidden_hit:
        violations.append(
            f"forbidden table(s) declared: {forbidden_hit}"
        )

    registry_ok = True
    registry_error = ""
    try:
        registry = build_standard_registry()
        pack_ids = set(registry.packs)
        if pack_ids - {"core"} != set(STANDARD_SCHEMA_PACKS):
            violations.append(
                f"standard registry pack ids {sorted(pack_ids)} != "
                f"{sorted(STANDARD_SCHEMA_PACKS)} plus core vocabulary"
            )
    except Exception as exc:  # noqa: BLE001 - registry construction failed
        registry_ok = False
        registry_error = f"{type(exc).__name__}: {exc}"
        violations.append(f"standard registry failed to freeze: {registry_error}")

    record: dict[str, object] = {
        "core_table_count": core_count,
        "pack_tables": {
            pack: sorted(table for table, owner in declared.items() if owner == pack)
            for pack in sorted(FROZEN_PACK_TABLES)
        },
        "pack_ids": sorted(manifest_pack_ids),
        "total_table_count": total,
        "registry_frozen": registry_ok,
        "registry_error": registry_error,
    }
    return not violations, violations, record


def _check_cli_surface() -> tuple[bool, list[str], dict[str, object]]:
    """Reject product surface drift from the frozen five-family registry."""
    violations: list[str] = []
    from astrid.core.cli import domain_product as product

    if product.PRODUCT_FAMILIES != FROZEN_PRODUCT_FAMILIES:
        violations.append(
            f"product families {product.PRODUCT_FAMILIES} != {FROZEN_PRODUCT_FAMILIES}"
        )
    if set(product.EXCLUDED_FROM_PRODUCT_CENSUS) != FROZEN_EXCLUDED_CENSUS:
        violations.append(
            "excluded-from-census set drift: "
            f"{sorted(product.EXCLUDED_FROM_PRODUCT_CENSUS)}"
        )
    if dict(product.REQUIRED_MANIFEST_MOUNTS) != FROZEN_MANIFEST_MOUNTS:
        violations.append(
            f"manifest mounts {dict(product.REQUIRED_MANIFEST_MOUNTS)} != "
            f"{FROZEN_MANIFEST_MOUNTS}"
        )
    if set(product.NESTED_FAMILIES) != FROZEN_NESTED_FAMILIES:
        violations.append(
            f"nested families {sorted(product.NESTED_FAMILIES)} != "
            f"{sorted(FROZEN_NESTED_FAMILIES)}"
        )
    top_level = set(product.product_top_level_commands())
    if top_level != set(FROZEN_PRODUCT_FAMILIES):
        violations.append(
            f"top-level product commands {sorted(top_level)} != "
            f"{sorted(FROZEN_PRODUCT_FAMILIES)}"
        )
    try:
        mounts = product.build_product_mounts()
    except Exception as exc:  # noqa: BLE001 - registry validation failed
        violations.append(f"product mount registry failed to build: {exc}")
        mounts = ()
    if len(mounts) != 7:
        violations.append(
            f"product mount count {len(mounts)} != frozen 7 "
            "(five families + shots + references)"
        )
    mount_tokens = [mount.mount_token for mount in mounts]
    if "shots" in top_level or "references" in top_level:
        violations.append("top-level shots/references family present")
    if len(mount_tokens) != len(set(mount_tokens)):
        violations.append("duplicate product mount tokens")
    expected_tokens = {
        "projects",
        "media",
        "tasks",
        "runs",
        "timelines",
        "timelines shots",
        "media references",
    }
    if set(mount_tokens) != expected_tokens:
        violations.append(
            f"product mount tokens {sorted(mount_tokens)} != "
            f"{sorted(expected_tokens)}"
        )

    # ``timelines copy`` is reserved for m6: it must not be a product verb.
    dispatch_src = (REPO_ROOT / "astrid/core/gateway/dispatch.py").read_text(
        encoding="utf-8"
    )
    verbs: set[str] = set()
    try:
        tree = ast.parse(dispatch_src)
        for node in tree.body:
            targets: list[ast.expr] = []
            value: ast.expr | None = None
            if isinstance(node, ast.Assign):
                targets = list(node.targets)
                value = node.value
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                targets = [node.target]
                value = node.value
            if not any(
                isinstance(target, ast.Name)
                and target.id == "_PRODUCT_TIMELINE_VERBS"
                for target in targets
            ):
                continue
            if isinstance(value, ast.Call) and value.args:
                verbs = set(ast.literal_eval(value.args[0]))
    except (ValueError, SyntaxError) as exc:  # pragma: no cover - parse issue
        violations.append(f"cannot parse product timeline verbs: {exc}")
    if verbs != FROZEN_PRODUCT_TIMELINE_VERBS:
        violations.append(
            f"product timeline verbs {sorted(verbs)} != "
            f"{sorted(FROZEN_PRODUCT_TIMELINE_VERBS)}"
        )
    if "copy" in verbs:
        violations.append("forbidden 'timelines copy' product route present")

    record: dict[str, object] = {
        "product_families": list(product.PRODUCT_FAMILIES),
        "nested_families": sorted(product.NESTED_FAMILIES),
        "mounts": mount_tokens,
        "product_timeline_verbs": sorted(verbs),
    }
    return not violations, violations, record


def _check_sdk_surface() -> tuple[bool, list[str], dict[str, object]]:
    """Reject public SDK surface drift (curated exports, no raw runners).

    The curated exports are a **set-based/API-based** contract: membership
    of the frozen required names and absence of the forbidden raw runner
    seams is what the gate enforces. Ordering is not a compatibility or
    gate requirement (task T20 / plan step 19), so any sequence of names is
    accepted and the sequence type is recorded as informational only.
    """
    violations: list[str] = []
    import astrid.sdk as sdk

    exports = sdk.__all__
    if not isinstance(exports, (list, tuple)):
        violations.append(
            "astrid.sdk.__all__ must be a sequence of export names "
            f"(got {type(exports).__name__})"
        )
    export_set = set(exports)
    missing = sorted(FROZEN_SDK_REQUIRED_EXPORTS - export_set)
    if missing:
        violations.append(f"public SDK exports missing: {missing}")
    forbidden = sorted(FROZEN_SDK_FORBIDDEN_EXPORTS & export_set)
    if forbidden:
        violations.append(
            f"forbidden public raw runner exports present: {forbidden}"
        )
    record: dict[str, object] = {
        "export_count": len(exports),
        "exports": list(exports),
        "is_list": isinstance(exports, list),
    }
    return not violations, violations, record


def _check_secret_scan(
    evidence_dir: Path, exclude_paths: Sequence[Path] = ()
) -> tuple[bool, list[str], dict[str, object]]:
    """Scan retained m4 evidence for the sentinel secret (never persists).

    The gate's own admission output is excluded from the scan: it is the
    gate's non-secret scan metadata, not evidence under test. The scan is
    also described in retained evidence **without persisting the sentinel
    literal** — a redacted label plus a SHA-256 fingerprint of the sentinel
    are recorded instead, so a later gate run can never re-detect the
    sentinel in evidence the gate itself wrote (no self-poisoning).
    """
    violations: list[str] = []
    scanned: list[str] = []
    excluded = tuple(path.resolve() for path in exclude_paths)
    roots = [REPO_ROOT / "artifacts" / "m4"]
    if evidence_dir.is_dir():
        roots.append(evidence_dir)
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix not in (".json", ".log", ".xml", ".txt"):
                continue
            resolved = path.resolve()
            if any(
                resolved == excluded_path or excluded_path in resolved.parents
                for excluded_path in excluded
            ):
                continue
            try:
                body = path.read_text(encoding="utf-8", errors="replace")
            except OSError:  # pragma: no cover - unreadable evidence
                continue
            scanned.append(str(path.relative_to(REPO_ROOT)))
            if SENTINEL in body:
                violations.append(
                    f"sentinel secret persisted in {path.relative_to(REPO_ROOT)}"
                )
    record: dict[str, object] = {
        "scanned_files": len(scanned),
        "sentinel": "<redacted; the literal sentinel is never persisted in "
        "retained gate evidence>",
        "sentinel_sha256_prefix": hashlib.sha256(SENTINEL.encode("utf-8")).hexdigest()[
            :16
        ],
    }
    return not violations, violations, record


# ---------------------------------------------------------------------------
# Retained evidence references (reporting-only)
# ---------------------------------------------------------------------------


def _check_baseline_reference() -> dict[str, object]:
    """Reference the retained pre-change baseline (reporting-only)."""
    baseline_path = REPO_ROOT / "artifacts" / "m4" / "baseline.json"
    if not baseline_path.is_file():
        return {
            "present": False,
            "reason": "artifacts/m4/baseline.json absent; the T1 baseline "
            "contract governs it, not gate success",
        }
    try:
        data = json.loads(baseline_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {"present": True, "parseable": False, "reason": str(exc)}
    if not isinstance(data, dict):
        return {"present": True, "parseable": False, "reason": "not an object"}
    ok = bool(data.get("ok")) and data.get("schema") == BASELINE_SCHEMA
    return {
        "present": True,
        "parseable": True,
        "schema": data.get("schema"),
        "ok": ok,
        "git_sha": (data.get("repo") or {}).get("git_sha"),
    }


def _check_reigh_disposition() -> dict[str, object]:
    """Reference the retained Reigh disposition (SD1, reporting-only)."""
    disposition_path = (
        REPO_ROOT / "artifacts" / "m4" / "reigh-external-gate-disposition.json"
    )
    if not disposition_path.is_file():
        return {
            "present": False,
            "reason": "artifacts/m4/reigh-external-gate-disposition.json "
            "absent; the T24 disposition lane owns that evidence",
        }
    try:
        data = json.loads(disposition_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {"present": True, "parseable": False, "reason": str(exc)}
    if not isinstance(data, dict):
        return {"present": True, "parseable": False, "reason": "not an object"}
    authority = data.get("authority")
    schema_ok = (
        data.get("schema") == DISPOSITION_SCHEMA
        and isinstance(authority, dict)
        and authority.get("decision") == "DENIED"
    )
    return {
        "present": True,
        "parseable": True,
        "schema_ok": schema_ok,
        "schema": data.get("schema"),
        "overall_status": data.get("overall_status"),
        "authority_decision": (authority or {}).get("decision"),
    }


# ---------------------------------------------------------------------------
# Admission document
# ---------------------------------------------------------------------------


def _build_admission(
    *,
    git_sha: str,
    started_at: str,
    finished_at: str,
    duration_seconds: float,
    feasibility: dict[str, object],
    feasibility_problems: Sequence[str],
    python_matrix: dict[str, object],
    lanes: Mapping[str, LaneResult],
    lane_subset: Sequence[str],
    authority_lint: dict[str, object],
    drift: dict[str, object],
    retained_reference: dict[str, object],
    problems: Sequence[str],
    out: Path,
) -> dict[str, object]:
    """Compose the schema-versioned finalizer admission document."""
    ok = (
        not problems
        and feasibility.get("accepted") is True
        and authority_lint["ok"] is True
        and drift["ok"] is True
        and all(result.status != "fail" for result in lanes.values())
    )
    secondary = python_matrix.get("secondary")
    secondary_status = secondary.get("status") if isinstance(secondary, dict) else None
    if secondary_status == "fail":
        ok = False
    try:
        admission_path = str(out.relative_to(REPO_ROOT))
    except ValueError:
        # The admission may be written outside the repo (e.g. a probe path);
        # record the absolute path instead of crashing the gate.
        admission_path = str(out)
    document: dict[str, object] = {
        "schema": GATE_SCHEMA,
        "timestamp": {
            "started_at": started_at,
            "finished_at": finished_at,
        },
        "repo": {
            "root": str(REPO_ROOT),
            "git_sha": git_sha,
            "git_short_sha": git_sha[:12],
        },
        "feasibility": feasibility,
        "feasibility_problems": list(feasibility_problems),
        "python_matrix": python_matrix,
        "lanes": {
            name: result.as_dict() for name, result in sorted(lanes.items())
        },
        "lane_subset": list(lane_subset) if lane_subset else [],
        "authority_lint": authority_lint,
        "drift": drift,
        "retained_reference": retained_reference,
        "problems": list(problems),
        "ok": ok,
        "exit": 0 if ok else 1,
        "duration_seconds": round(duration_seconds, 3),
        "admission_path": admission_path,
    }
    return document


def _validate_admission(data: object) -> list[str]:
    """Validate a parsed admission document; return a list of problems."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["admission is not a JSON object"]
    if data.get("schema") != GATE_SCHEMA:
        errors.append(
            f"admission schema {data.get('schema')!r} != {GATE_SCHEMA!r}"
        )
    feasibility = data.get("feasibility")
    if not isinstance(feasibility, dict):
        errors.append("admission missing feasibility")
    elif feasibility.get("accepted") is not True:
        errors.append("admission feasibility not accepted")
    if not isinstance(data.get("python_matrix"), dict):
        errors.append("admission missing python_matrix")
    lanes = data.get("lanes")
    if not isinstance(lanes, dict):
        errors.append("admission missing lanes")
    else:
        subset = data.get("lane_subset")
        expected = (
            tuple(subset) if isinstance(subset, list) and subset else tuple(
                name for name, _ in LANES
            )
        )
        for name in expected:
            entry = lanes.get(name)
            if not isinstance(entry, dict):
                errors.append(f"admission missing lane {name!r}")
                continue
            if entry.get("status") not in ("pass", "fail", "skip"):
                errors.append(f"lane {name!r} has no valid status")
    authority = data.get("authority_lint")
    if not isinstance(authority, dict) or not isinstance(authority.get("ok"), bool):
        errors.append("admission missing authority_lint.ok")
    drift = data.get("drift")
    if not isinstance(drift, dict) or not isinstance(drift.get("ok"), bool):
        errors.append("admission missing drift.ok")
    if not isinstance(data.get("ok"), bool):
        errors.append("admission missing boolean ok")
    if not isinstance(data.get("timestamp"), dict) or not data.get("timestamp", {}).get(
        "finished_at"
    ):
        errors.append("admission missing timestamp.finished_at")
    return errors


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def run_gate(
    *,
    out: Path | None = None,
    feasibility_path: Path | None = None,
    python: str | None = None,
    python_secondary: str | None = None,
    evidence_dir: Path | None = None,
    selectors: Sequence[str] | None = None,
) -> tuple[dict[str, object], int]:
    """Run the m4 gate and retain the schema-validated admission evidence."""
    out_path = (out or DEFAULT_OUT).expanduser().resolve()
    feasibility = (feasibility_path or DEFAULT_FEASIBILITY).expanduser().resolve()
    evidence = (evidence_dir or DEFAULT_EVIDENCE_DIR).expanduser().resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    primary = python or sys.executable

    started_at = _utc_timestamp()
    started = time.monotonic()
    problems: list[str] = []

    try:
        git_sha = _git_sha(REPO_ROOT)
    except RuntimeError as exc:
        git_sha = "<unavailable>"
        problems.append(str(exc))

    # --- Python matrix -----------------------------------------------------
    primary_version = _interpreter_version(primary)
    python_matrix: dict[str, object] = {
        "matrix_targets": ["3.11", "3.12"],
        "primary": {
            "executable": primary,
            "version": (
                ".".join(str(p) for p in primary_version)
                if primary_version
                else "<unknown>"
            ),
        },
        "secondary": {},
    }
    if primary_version is None:
        problems.append(f"cannot resolve primary interpreter version for {primary!r}")
    elif (primary_version[0], primary_version[1]) not in PRIMARY_PYTHON_ALLOWED:
        problems.append(
            f"primary interpreter {primary} is CPython "
            f"{primary_version[0]}.{primary_version[1]}; the frozen matrix "
            "requires CPython 3.11 or 3.12"
        )

    # --- Feasibility admission (fail closed) -------------------------------
    feasibility_record, feasibility_problems = _check_feasibility(feasibility)
    for problem in feasibility_problems:
        print(f"ERROR: {problem}", file=sys.stderr)

    # --- Authority lint + drift checks --------------------------------------
    authority_ok, authority_errors, authority_exemptions = _run_authority_lint()
    for error in authority_errors:
        print(f"AUTHORITY LINT: {error}", file=sys.stderr)
    authority_record: dict[str, object] = {
        "ok": authority_ok,
        "errors": list(authority_errors),
        "exemptions": list(authority_exemptions),
        "exemption_note": (
            "the recorded exemptions are the two manifest-declared "
            "nested-mount parser composition edges (timelines->shots, "
            "media->references), mirroring the dispatch.py composition root"
        ),
    }

    schema_ok, schema_violations, schema_record = _check_schema_composition()
    cli_ok, cli_violations, cli_record = _check_cli_surface()
    sdk_ok, sdk_violations, sdk_record = _check_sdk_surface()
    secret_ok, secret_violations, secret_record = _check_secret_scan(
        evidence, exclude_paths=(out_path,)
    )
    drift_violations = (
        schema_violations + cli_violations + sdk_violations + secret_violations
    )
    drift: dict[str, object] = {
        "ok": schema_ok and cli_ok and sdk_ok and secret_ok,
        "violations": list(drift_violations),
        "checks": {
            "schema_composition": schema_record,
            "cli_surface": cli_record,
            "sdk_surface": sdk_record,
            "secrets": secret_record,
        },
    }
    for violation in drift_violations:
        print(f"DRIFT: {violation}", file=sys.stderr)

    # --- Focused lanes (primary interpreter) -------------------------------
    lane_names = selectors or [name for name, _ in LANES]
    lane_map = {name: selectors for name, selectors in LANES}
    unknown = [name for name in lane_names if name not in lane_map]
    if unknown:
        problems.append(
            f"unknown gate lane(s) {', '.join(unknown)!r}; "
            f"choose from {', '.join(lane_map)}"
        )
        lane_names = [name for name in lane_names if name in lane_map]

    results: dict[str, LaneResult] = {}
    for name in lane_names:
        lane_selectors = lane_map[name]
        print(f"=== lane {name}: {' '.join(lane_selectors)} ===")
        result = _run_lane(
            name,
            lane_selectors,
            python=primary,
            repo_root=REPO_ROOT,
            evidence_dir=evidence,
        )
        results[name] = result
        print(
            f"=== lane {name}: {result.status} "
            f"({result.passed} passed, {result.failed} failed, "
            f"{result.skipped} skipped) in {result.duration_seconds:.2f}s "
            f"(exit {result.returncode}) ==="
        )

    # --- Secondary matrix interpreter (reporting if unavailable) -----------
    secondary = python_secondary or _discover_secondary()
    if secondary is None:
        python_matrix["secondary"] = {
            "status": "unavailable",
            "reason": (
                "no python3.12/python3.13 secondary interpreter on PATH; "
                "the CI matrix job is the authoritative 3.12 execution"
            ),
        }
    elif not _interpreter_has_pytest(secondary):
        secondary_version = _interpreter_version(secondary)
        python_matrix["secondary"] = {
            "status": "unavailable",
            "executable": secondary,
            "version": (
                ".".join(str(p) for p in secondary_version)
                if secondary_version
                else "<unknown>"
            ),
            "reason": (
                "secondary interpreter found but the pinned dev extra "
                "(pytest) is not installed for it; the CI matrix job is "
                "the authoritative 3.11/3.12 execution"
            ),
        }
    else:
        secondary_version = _interpreter_version(secondary)
        secondary_record: dict[str, object] = {
            "executable": secondary,
            "version": (
                ".".join(str(p) for p in secondary_version)
                if secondary_version
                else "<unknown>"
            ),
        }
        print(
            f"=== lane matrix_secondary: {' '.join(SECONDARY_MATRIX_SELECTORS)} ==="
        )
        secondary_result = _run_lane(
            "matrix_secondary",
            SECONDARY_MATRIX_SELECTORS,
            python=secondary,
            repo_root=REPO_ROOT,
            evidence_dir=evidence,
        )
        secondary_record["status"] = secondary_result.status
        secondary_record["result"] = secondary_result.as_dict()
        python_matrix["secondary"] = secondary_record
        print(
            f"=== lane matrix_secondary: {secondary_result.status} "
            f"({secondary_result.passed} passed, {secondary_result.failed} "
            f"failed, {secondary_result.skipped} skipped) in "
            f"{secondary_result.duration_seconds:.2f}s "
            f"(exit {secondary_result.returncode}) ==="
        )

    # --- Retained evidence references (reporting-only) ---------------------
    retained_reference: dict[str, object] = {
        "baseline": _check_baseline_reference(),
        "reigh_disposition": _check_reigh_disposition(),
        "note": (
            "baseline and Reigh disposition are retained evidence; Reigh "
            "compatibility is reporting-only (SD1) and never an admission input"
        ),
    }

    duration_seconds = time.monotonic() - started
    document = _build_admission(
        git_sha=git_sha,
        started_at=started_at,
        finished_at=_utc_timestamp(),
        duration_seconds=duration_seconds,
        feasibility=feasibility_record,
        feasibility_problems=feasibility_problems,
        python_matrix=python_matrix,
        lanes=results,
        lane_subset=lane_names,
        authority_lint=authority_record,
        drift=drift,
        retained_reference=retained_reference,
        problems=problems,
        out=out_path,
    )
    _write_atomic(out_path, document)

    validation_errors = _validate_admission(
        json.loads(out_path.read_text(encoding="utf-8"))
    )
    for error in validation_errors:
        print(f"ERROR: {error}", file=sys.stderr)
    if validation_errors:
        document["ok"] = False
        document["exit"] = 1
        _write_atomic(out_path, document)

    ok = bool(document["ok"]) and not validation_errors
    exit_code = 0 if ok else 1
    print(f"ok={str(ok).lower()} exit={exit_code}")
    print(f"admission={out_path}")
    return document, exit_code


def check_admission(out: Path | None = None) -> tuple[dict[str, object], int]:
    """Validate an existing retained admission without re-running lanes."""
    out_path = (out or DEFAULT_OUT).expanduser().resolve()
    if not out_path.exists():
        print(
            f"ERROR: finalizer admission absent at {out_path}; "
            "run 'make m4-gate' first",
            file=sys.stderr,
        )
        return {}, 1
    data = json.loads(out_path.read_text(encoding="utf-8"))
    errors = _validate_admission(data)
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    ok = bool(data.get("ok")) and not errors
    print(f"ok={str(ok).lower()} exit={0 if ok else 1}")
    print(f"admission={out_path}")
    return data, 0 if ok else 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="m4_gate",
        description=(
            "Run the focused m4 finalizer gate: retained lanes, authority "
            "lint, forbidden drift rejection, the Python matrix, and the "
            "present-accepted feasibility admission."
        ),
    )
    parser.add_argument(
        "--out",
        type=Path,
        help="Admission evidence path (default: artifacts/m4/finalizer-admission.json).",
    )
    parser.add_argument(
        "--feasibility",
        type=Path,
        help="Feasibility admission path (default: the m4 plan task_feasibility.json).",
    )
    parser.add_argument(
        "--python",
        help="Primary interpreter for lane subprocesses (default: sys.executable).",
    )
    parser.add_argument(
        "--python-secondary",
        help="Secondary matrix interpreter (default: discover python3.12/python3.13).",
    )
    parser.add_argument(
        "--evidence-dir",
        type=Path,
        help="Per-lane log/JUnit evidence directory (default: out/m4-gate/latest).",
    )
    parser.add_argument(
        "--selectors",
        help="Comma-separated lane subset to run (default: all focused lanes).",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Validate an existing admission without re-running lanes.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.check_only:
        _data, exit_code = check_admission(args.out)
        return exit_code
    selectors = None
    if args.selectors:
        selectors = tuple(
            raw.strip() for raw in args.selectors.split(",") if raw.strip()
        )
    _data, exit_code = run_gate(
        out=args.out,
        feasibility_path=args.feasibility,
        python=args.python,
        python_secondary=args.python_secondary,
        evidence_dir=args.evidence_dir,
        selectors=selectors,
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
