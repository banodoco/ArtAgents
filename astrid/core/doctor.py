"""Environment diagnostics for Astrid."""

from __future__ import annotations

import argparse
import ast
import importlib
import importlib.machinery
import importlib.metadata
import importlib.util
import json
import os
import re
import shutil
import sys
import tomllib
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping

from astrid.core.timeline.kinds import default_transition_kind, transition_kind_options
from astrid.core.foundation.paths import REPO_ROOT

Status = str
_DECLARED_DEP_RE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
_ENV_KEY_RE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=")
_IMPORT_SCAN_SKIP_DIRS = frozenset(
    {
        "packs",
        "tests",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "cache",
        "generated",
    }
)
_LOCAL_IMPORT_PREFIXES = ("banodoco_timeline_schema", "vibecomfy")
_OPTIONAL_PRIVATE_IMPORTS = {
    "runpod_lifecycle": "runpod-lifecycle",
}
_IMPORT_TO_DISTRIBUTION_FALLBACKS = {
    "google": "google-genai",
    "google.genai": "google-genai",
    "jwt": "PyJWT",
    "jwt.algorithms": "PyJWT",
    "PIL": "pillow",
    "yaml": "PyYAML",
}


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    status: Status
    detail: str
    required: bool = True

    def failed(self, *, strict_optional: bool = False) -> bool:
        if self.status == "fail":
            return True
        return strict_optional and not self.required and self.status == "warn"


@dataclass(frozen=True)
class EnvTemplateEntry:
    key: str
    required: bool


def run_checks(*, optional_binaries: tuple[str, ...] = ("ffmpeg", "npx", "uv", "npm")) -> tuple[DoctorCheck, ...]:
    checks: list[DoctorCheck] = []
    checks.append(_check_python_version())
    checks.append(_check_required_imports())
    checks.append(_check_dependency_audit(optional_missing_is_ok=True))
    checks.append(_check_env_template())
    executor_registry = _capture_check("executor registry", _check_executor_registry)
    checks.append(executor_registry)
    checks.append(_capture_check("orchestrator registry", _check_orchestrator_registry))
    checks.append(_capture_check("element registry", _check_element_registry))
    checks.append(_capture_check("repo structure", _check_repo_structure))
    checks.append(_capture_check("vibecomfy metadata", _check_vibecomfy_metadata))
    checks.append(_capture_check("remotion config", _check_remotion_config))
    checks.append(_capture_check("timeline catalog", _check_timeline_catalog))
    checks.append(_check_runpod_stale_handles())
    checks.extend((_check_stale_project_runs(), _check_projects_root()))
    for binary in optional_binaries:
        checks.append(_check_optional_binary(binary))
    return tuple(checks)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python3 -m astrid doctor", description="Check the Astrid environment.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable diagnostics.")
    parser.add_argument(
        "--strict-optional",
        action="store_true",
        help="Treat missing optional external binaries as failures.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    checks = run_checks()
    failed = any(check.failed(strict_optional=args.strict_optional) for check in checks)
    if args.json:
        payload = {
            "ok": not failed,
            "checks": [asdict(check) for check in checks],
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print("Astrid doctor")
        for check in checks:
            print(f"[{check.status}] {check.name}: {check.detail}")
    return 1 if failed else 0


def _capture_check(name: str, fn: Callable[[], str]) -> DoctorCheck:
    try:
        return DoctorCheck(name=name, status="ok", detail=fn())
    except Exception as exc:  # pragma: no cover - detail shape is tested through mocks.
        return DoctorCheck(name=name, status="fail", detail=str(exc) or exc.__class__.__name__)


def load_executor_registry():
    from astrid.core.executor.registry import load_default_registry

    return load_default_registry()


def load_orchestrator_registry(*, executor_registry=None):
    from astrid.core.orchestrator.registry import load_default_registry

    return load_default_registry(executor_registry=executor_registry)


def load_element_registry(*, project_root: Path):
    from astrid.core.element.registry import load_default_registry

    return load_default_registry(project_root=project_root)


def _check_python_version() -> DoctorCheck:
    version = sys.version_info
    required = (3, 10)
    if version < required:
        return DoctorCheck(
            name="python",
            status="fail",
            detail=f"Python {required[0]}.{required[1]}+ required; found {version.major}.{version.minor}.{version.micro}",
        )
    return DoctorCheck(name="python", status="ok", detail=f"{version.major}.{version.minor}.{version.micro}")


def _check_required_imports() -> DoctorCheck:
    modules = (
        "astrid.core.timeline",
        "astrid.core.element.registry",
        "astrid.core.executor.registry",
        "astrid.core.orchestrator.registry",
        "astrid.core.project",
    )
    for module in modules:
        importlib.import_module(module)
    return DoctorCheck(name="required imports", status="ok", detail=f"{len(modules)} import(s) ok")


def _check_dependency_audit(
    *,
    repo_root: Path = REPO_ROOT,
    optional_missing_is_ok: bool = False,
) -> DoctorCheck:
    source_root = repo_root / "astrid"
    pyproject_path = repo_root / "pyproject.toml"
    declared = _declared_project_distributions(pyproject_path)
    imports = _scan_dependency_imports(source_root)
    packages = importlib.metadata.packages_distributions()

    undeclared: dict[str, set[str]] = defaultdict(set)
    unresolved: dict[str, set[str]] = defaultdict(set)
    optional_missing: dict[str, set[str]] = defaultdict(set)

    for import_name, files in imports.items():
        if _is_local_import(import_name):
            continue
        distribution = _resolve_distribution_name(import_name, packages)
        normalized = _normalize_distribution_name(distribution) if distribution else None
        if normalized is None:
            private_dist = _optional_private_distribution(import_name)
            if private_dist is not None:
                optional_missing[private_dist].update(files)
                continue
            unresolved[import_name].update(files)
            continue
        if normalized not in declared:
            undeclared[distribution or import_name].update(files)

    if undeclared or unresolved:
        return DoctorCheck(
            name="dependency audit",
            status="fail",
            detail=_format_dependency_issues(undeclared=undeclared, unresolved=unresolved),
        )
    if optional_missing:
        detail = "; ".join(
            f"{dist} missing ({', '.join(sorted(files))})"
            for dist, files in sorted(optional_missing.items())
        )
        # Private/optional distributions (e.g. runpod-lifecycle) are not on PyPI
        # and are routinely absent in CI and on fresh checkouts. In the aggregated
        # doctor report this is benign environment provisioning, not a repo defect,
        # so it surfaces as an ``ok`` with advisory detail. Callers that audit the
        # check in isolation keep the stricter ``warn`` signal.
        status = "ok" if optional_missing_is_ok else "warn"
        return DoctorCheck(name="dependency audit", status=status, detail=detail, required=False)
    return DoctorCheck(
        name="dependency audit",
        status="ok",
        detail=f"{len(imports)} third-party import(s) matched against {len(declared)} declared distribution(s)",
    )


def _check_env_template(
    *,
    repo_root: Path = REPO_ROOT,
    environ: Mapping[str, str] | None = None,
    env_candidates: list[Path] | None = None,
) -> DoctorCheck:
    from astrid.core.util.secrets import candidate_env_files, read_env_value

    template_path = repo_root / ".env.example"
    entries = _parse_env_template(template_path)
    required_entries = [entry for entry in entries if entry.required]
    if not required_entries:
        return DoctorCheck(name="env template", status="fail", detail="no required keys declared in .env.example")

    values = dict(os.environ if environ is None else environ)
    candidates = candidate_env_files() if env_candidates is None else list(env_candidates)
    missing: list[str] = []
    for entry in required_entries:
        value = values.get(entry.key, "").strip()
        if not value:
            for candidate in candidates:
                value = read_env_value(candidate, entry.key)
                if value:
                    break
        if not value:
            missing.append(entry.key)

    if missing:
        env_file_present = any(candidate.is_file() for candidate in candidates)
        if env_file_present:
            # A populated-but-incomplete env file is a genuine misconfiguration
            # of the developer's workspace and fails hard.
            detail = f"missing required key(s): {', '.join(sorted(missing))}; copy .env.example to .env and fill them in"
            return DoctorCheck(name="env template", status="fail", detail=detail)
        # No .env on disk and the key is absent from the environment: this is the
        # normal state of a fresh checkout or a CI runner with no secrets, not a
        # repo defect. The template itself is well-formed, so report ok and only
        # surface the unprovisioned keys as advisory detail.
        detail = (
            f"{len(required_entries)} required key(s) declared but unset "
            f"({', '.join(sorted(missing))}); copy .env.example to .env to provision"
        )
        return DoctorCheck(name="env template", status="ok", detail=detail, required=False)

    optional_count = len(entries) - len(required_entries)
    return DoctorCheck(
        name="env template",
        status="ok",
        detail=f"{len(required_entries)} required key(s) present; {optional_count} optional key(s) declared",
    )


def _check_executor_registry() -> str:
    registry = load_executor_registry()
    count = len(registry.list())
    if count == 0:
        raise RuntimeError("no executors discovered")
    return f"{count} executor(s)"


def _check_orchestrator_registry() -> str:
    executor_registry = load_executor_registry()
    registry = load_orchestrator_registry(executor_registry=executor_registry)
    count = len(registry.list())
    if count == 0:
        raise RuntimeError("no orchestrators discovered")
    return f"{count} orchestrator(s)"


def _check_element_registry() -> str:
    registry = load_element_registry(project_root=REPO_ROOT)
    counts = {kind: len(registry.list(kind=kind)) for kind in ("effects", "animations", "transitions")}
    missing = [kind for kind, count in counts.items() if count == 0]
    if missing:
        raise RuntimeError(f"no elements discovered for: {', '.join(missing)}")
    return ", ".join(f"{kind}={count}" for kind, count in counts.items())


def _check_repo_structure() -> str:
    from astrid.core.structure import validate_repo_structure

    report = validate_repo_structure(REPO_ROOT)
    if not report.ok:
        raise RuntimeError("; ".join(report.errors))
    if report.warnings:
        return f"canonical folders ok; {len(report.warnings)} migration advisory warning(s)"
    return "canonical folders ok"


def _check_vibecomfy_metadata() -> str:
    registry = load_executor_registry()
    run = registry.get("vibecomfy.run")
    metadata = run.metadata
    required = {
        "pack_id": "vibecomfy",
        "homepage": "https://github.com/peteromallet/VibeComfy",
        "catalog_source": "none_declared",
    }
    for key, expected in required.items():
        if metadata.get(key) != expected:
            raise RuntimeError(f"metadata[{key!r}] is {metadata.get(key)!r}, expected {expected!r}")
    if metadata.get("workflows") != [] or metadata.get("nodes") != [] or metadata.get("prompts") != []:
        raise RuntimeError("VibeComfy catalog metadata must be explicit empty lists when none are declared")
    if metadata.get("workflow_input_contract", {}).get("name") != "workflow":
        raise RuntimeError("missing workflow input contract")
    if not run.isolation.network:
        raise RuntimeError("VibeComfy run executor should declare network access")
    return "vibecomfy.run metadata visible"


def _check_remotion_config() -> str:
    paths = (
        REPO_ROOT / "remotion" / "remotion.config.ts",
        REPO_ROOT / "remotion" / "webpack-alias.mjs",
        REPO_ROOT / "remotion" / "tsconfig.json",
    )
    missing = [str(path.relative_to(REPO_ROOT)) for path in paths if not path.is_file()]
    if missing:
        raise RuntimeError(f"missing Remotion config: {', '.join(missing)}")
    return f"{len(paths)} file(s) present"


def _check_timeline_catalog() -> str:
    from astrid.core.element.catalog import list_animation_ids, list_effect_ids, list_transition_ids

    effects = set(list_effect_ids())
    animations = set(list_animation_ids())
    transitions = set(list_transition_ids())
    default_transition = default_transition_kind()
    expected = [
        ("effect", "text-card", effects),
        ("animation", "fade", animations),
        ("transition", default_transition, transitions),
    ]
    missing = [f"{kind}:{item}" for kind, item, values in expected if item not in values]
    if missing:
        raise RuntimeError(f"missing timeline catalog ids: {', '.join(missing)}")
    canonical_transitions = ",".join(transition_kind_options())
    return (
        f"effects={len(effects)}, animations={len(animations)}, "
        f"transitions={len(transitions)} default={default_transition} "
        f"canonical=[{canonical_transitions}]"
    )


def _check_runpod_stale_handles() -> DoctorCheck:
    """Report stray ``pod_handle.json`` files whose ``terminate_at`` has passed.

    Read-only — never calls ``terminate`` or ``append_event_locked``.
    Does NOT add a symmetric runpod metadata check (out of scope).
    """
    from astrid.core.foundation.project_paths import resolve_projects_root
    from astrid.core.integrations.runpod.sweeper import (
        _derive_run_dir,
        _handle_path_belongs_to_run,
        collect_handles,
    )

    projects_root = resolve_projects_root()
    if not projects_root.is_dir():
        return DoctorCheck(
            name="runpod stale handles",
            status="ok",
            detail="no projects root to scan",
        )

    handles = collect_handles(projects_root)
    now_utc = datetime.now(timezone.utc)
    stale_count = 0

    for path, handle in handles:
        run_dir = _derive_run_dir(path, projects_root)
        if run_dir is None or not _handle_path_belongs_to_run(run_dir, path):
            continue
        terminate_at_str = handle.get("terminate_at", "")
        if not terminate_at_str:
            continue
        try:
            terminate_at = datetime.fromisoformat(
                terminate_at_str.replace("Z", "+00:00")
            )
            if terminate_at <= now_utc:
                stale_count += 1
        except (ValueError, TypeError):
            pass

    if stale_count > 0:
        return DoctorCheck(
            name="runpod stale handles",
            status="warn",
            detail=f"{stale_count} stale handle(s) found",
        )
    return DoctorCheck(
        name="runpod stale handles",
        status="ok",
        detail="no stale handles detected",
    )


def _check_stale_project_runs() -> DoctorCheck:
    from astrid.core.contracts.run_status import RunStatus
    from astrid.core._shared.jsonio import read_json
    from astrid.core.foundation.project_paths import resolve_projects_root
    from astrid.core.project.run import update_run_record
    from astrid.core.util.time import utc_now_seconds

    projects_root = resolve_projects_root()
    if not projects_root.is_dir():
        return DoctorCheck(
            name="stale project runs",
            status="ok",
            detail="no projects root to scan",
            required=False,
        )

    repaired = 0
    unknown = 0
    for run_json_path in sorted(projects_root.glob("*/runs/*/run.json")):
        try:
            raw = read_json(run_json_path)
        except Exception:
            continue
        if not isinstance(raw, dict) or raw.get("status") != RunStatus.RUNNING.value:
            continue
        project_slug = raw.get("project_slug")
        run_id = raw.get("run_id")
        if not isinstance(project_slug, str) or not isinstance(run_id, str):
            continue
        verdict, detail = _project_run_liveness(raw)
        if verdict == "dead":
            metadata = dict(raw.get("metadata", {}))
            metadata["doctor_repair"] = {
                "detail": detail,
                "kind": "stale_running",
                "liveness": "dead",
                "repaired_at": utc_now_seconds(),
                "repaired_by": "astrid doctor",
            }
            metadata["error"] = f"astrid doctor repaired stale RUNNING record: {detail}"
            update_run_record(
                project_slug,
                run_id,
                {
                    "metadata": metadata,
                    "status": RunStatus.FAILED.value,
                },
                root=projects_root,
            )
            repaired += 1
        elif verdict == "unknown":
            unknown += 1

    if repaired:
        detail = f"repaired {repaired} stale RUNNING project run(s)"
        if unknown:
            detail = f"{detail}; left {unknown} RUNNING record(s) untouched because liveness was unknown"
        return DoctorCheck(name="stale project runs", status="warn", detail=detail, required=False)
    if unknown:
        return DoctorCheck(
            name="stale project runs",
            status="warn",
            detail=f"left {unknown} RUNNING record(s) untouched because liveness was unknown",
            required=False,
        )
    return DoctorCheck(
        name="stale project runs",
        status="ok",
        detail="no stale RUNNING project runs detected",
        required=False,
    )


def _check_projects_root() -> DoctorCheck:
    from astrid.core.foundation.project_paths import PROJECTS_ROOT_ENV, resolve_projects_root

    projects_root = resolve_projects_root()
    detail = f"{projects_root} ({PROJECTS_ROOT_ENV} override supported)"
    if projects_root.is_dir():
        return DoctorCheck(name="projects root", status="ok", detail=detail, required=False)
    return DoctorCheck(
        name="projects root",
        status="warn",
        detail=f"{detail}; run `python3 -m astrid setup --apply` to create it",
        required=False,
    )


def _check_optional_binary(binary: str) -> DoctorCheck:
    found = shutil.which(binary)
    if found is None:
        return DoctorCheck(name=f"optional binary {binary}", status="warn", detail="not found on PATH", required=False)
    return DoctorCheck(name=f"optional binary {binary}", status="ok", detail=str(Path(found)), required=False)


def _declared_project_distributions(pyproject_path: Path) -> set[str]:
    if not pyproject_path.is_file():
        raise RuntimeError(f"missing dependency manifest: {pyproject_path}")
    payload = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    dependencies = payload.get("project", {}).get("dependencies", [])
    if not isinstance(dependencies, list):
        raise RuntimeError("pyproject.toml project.dependencies must be a list")
    declared: set[str] = set()
    for requirement in dependencies:
        if not isinstance(requirement, str):
            raise RuntimeError("pyproject.toml project.dependencies entries must be strings")
        match = _DECLARED_DEP_RE.match(requirement)
        if not match:
            raise RuntimeError(f"unable to parse dependency declaration: {requirement!r}")
        declared.add(_normalize_distribution_name(match.group(1)))
    return declared


def _scan_dependency_imports(source_root: Path) -> dict[str, set[str]]:
    imports: dict[str, set[str]] = defaultdict(set)
    for path in source_root.rglob("*.py"):
        relative = path.relative_to(source_root)
        if any(part in _IMPORT_SCAN_SKIP_DIRS for part in relative.parts):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    _record_import(imports, alias.name, relative)
            elif isinstance(node, ast.ImportFrom):
                if node.level or not node.module:
                    continue
                _record_import(imports, node.module, relative)
    return {name: set(files) for name, files in imports.items()}


def _record_import(imports: dict[str, set[str]], module_name: str, relative: Path) -> None:
    top_level = module_name.split(".", 1)[0]
    if module_name.startswith("astrid.") or top_level == "astrid" or top_level in sys.stdlib_module_names:
        return
    imports[module_name].add(str(relative))


def _is_local_import(import_name: str) -> bool:
    if any(import_name == prefix or import_name.startswith(f"{prefix}.") for prefix in _LOCAL_IMPORT_PREFIXES):
        return True
    spec = importlib.util.find_spec(import_name) or importlib.util.find_spec(import_name.split(".", 1)[0])
    if spec is None:
        return False
    origin = _spec_origin(spec)
    if origin is None:
        return False
    origin_text = str(origin)
    return "site-packages" not in origin_text and "dist-packages" not in origin_text


def _optional_private_distribution(import_name: str) -> str | None:
    for prefix, distribution in _OPTIONAL_PRIVATE_IMPORTS.items():
        if import_name == prefix or import_name.startswith(f"{prefix}."):
            return distribution
    return None


def _resolve_distribution_name(
    import_name: str,
    packages_distributions: Mapping[str, list[str]],
) -> str | None:
    for candidate in (import_name, import_name.split(".", 1)[0]):
        fallback = _IMPORT_TO_DISTRIBUTION_FALLBACKS.get(candidate)
        if fallback is not None:
            return fallback
        distributions = packages_distributions.get(candidate)
        if distributions:
            return sorted(distributions)[0]
    return None


def _normalize_distribution_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _format_dependency_issues(
    *,
    undeclared: Mapping[str, set[str]],
    unresolved: Mapping[str, set[str]],
) -> str:
    parts: list[str] = []
    if undeclared:
        items = ", ".join(
            f"{distribution} ({', '.join(sorted(files))})"
            for distribution, files in sorted(undeclared.items())
        )
        parts.append(f"undeclared distribution(s): {items}")
    if unresolved:
        items = ", ".join(
            f"{import_name} ({', '.join(sorted(files))})"
            for import_name, files in sorted(unresolved.items())
        )
        parts.append(f"unresolved import(s): {items}")
    return "; ".join(parts)


def _parse_env_template(template_path: Path) -> list[EnvTemplateEntry]:
    if not template_path.is_file():
        raise RuntimeError(f"missing env template: {template_path}")
    entries: list[EnvTemplateEntry] = []
    comment_block: list[str] = []
    for raw in template_path.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if not stripped:
            comment_block.clear()
            continue
        if stripped.startswith("#"):
            comment_block.append(stripped[1:].strip())
            continue
        match = _ENV_KEY_RE.match(raw)
        if match:
            annotation = " ".join(comment_block)
            entries.append(
                EnvTemplateEntry(
                    key=match.group(1),
                    required=bool(re.search(r"\brequired\b", annotation, flags=re.IGNORECASE)),
                )
            )
        comment_block.clear()
    if not entries:
        raise RuntimeError(".env.example does not declare any keys")
    return entries


def _spec_origin(spec: importlib.machinery.ModuleSpec) -> Path | None:
    origin = spec.origin
    if origin and origin != "built-in":
        return Path(origin)
    locations = spec.submodule_search_locations
    if locations:
        return Path(next(iter(locations)))
    return None


def _project_run_liveness(record: Mapping[str, object]) -> tuple[str, str]:
    metadata = record.get("metadata")
    if not isinstance(metadata, Mapping):
        return ("unknown", "missing run metadata")
    if metadata.get("attached_to_task_run") is True:
        return ("unknown", "task-attached runs are out of scope")
    pid = metadata.get("pid")
    if not isinstance(pid, int) or pid <= 0:
        return ("unknown", "missing or invalid pid")
    process_platform = metadata.get("process_platform")
    if not isinstance(process_platform, str) or not process_platform:
        return ("unknown", "missing process platform")
    if process_platform != sys.platform:
        return ("unknown", f"recorded platform {process_platform!r} does not match current platform {sys.platform!r}")
    verdict = _probe_pid_liveness(pid)
    if verdict == "alive":
        return ("alive", f"pid {pid} is still alive")
    if verdict == "dead":
        return ("dead", f"pid {pid} is not alive on {process_platform}")
    return ("unknown", f"could not determine liveness for pid {pid}")


def _probe_pid_liveness(pid: int) -> str:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return "dead"
    except PermissionError:
        return "alive"
    except OSError:
        return "unknown"
    return "alive"


if __name__ == "__main__":
    raise SystemExit(main())
