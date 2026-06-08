"""Repository structure guardrails for Astrid canonical concepts."""

from __future__ import annotations

import ast
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from astrid.core.executor.folder import load_folder_executors
from astrid.core.orchestrator.folder import load_folder_orchestrators
from astrid.core.pack import (
    ELEMENT_KIND_REGISTRY,
    element_kind_registry_for_pack,
    load_pack_manifest,
    pack_manifest_path,
)
from astrid.paths import REPO_ROOT

LEGACY_PUBLIC_DIRS = ("conductors", "performers", "instruments", "primitives", "executors", "orchestrators")
LEGACY_LOCAL_DIRS = ("performers", "conductors", "nodes", "instruments", "primitives")
INTERNAL_PACK_DIRS = {"__pycache__", "schemas"}
TOP_LEVEL_ASTRID_FILES = {
    "__init__.py",
    "__main__.py",
    "_media.py",
    "_paths.py",
    "doctor.py",
    "gateway.py",
    "gateway_dispatch.py",
    "gateway_help.py",
    "gateway_project.py",
    "gateway_wait.py",
    "media.py",
    "paths.py",
    "pipeline.py",
    "sdk.py",
    "sdk_discovery.py",
    "sdk_errors.py",
    "sdk_generation.py",
    "sdk_invocation.py",
    "sdk_results.py",
    "setup_cli.py",
    "structure.py",
    "theme_schema.py",
}
TOP_LEVEL_ASTRID_DIRS = {
    "audit",
    "contracts",
    "core",
    "docs",
    "domains",
    "elements",
    "modalities",
    "orchestrate",
    "packs",
    "skills",
    "threads",
    "timeline",
    "utilities",
    "verify",
}


@dataclass(frozen=True)
class StructureReport:
    errors: tuple[str, ...]
    warnings: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.errors


def validate_repo_structure(root: str | Path = REPO_ROOT) -> StructureReport:
    repo_root = Path(root)
    errors: list[str] = []
    warnings: list[str] = []
    errors.extend(_validate_legacy_dirs(repo_root))
    errors.extend(_validate_local_state_dirs(repo_root))
    errors.extend(_validate_top_level_astrid(repo_root / "astrid"))
    errors.extend(_validate_generated_debris(repo_root))
    errors.extend(_validate_pack_executor_folders(repo_root / "astrid" / "packs"))
    errors.extend(_validate_pack_orchestrator_folders(repo_root / "astrid" / "packs"))
    errors.extend(_validate_pack_element_folders(repo_root / "astrid" / "packs"))
    errors.extend(validate_import_layering(repo_root))
    errors.extend(validate_cli_domain_boundary(repo_root))
    # Migration-completion drift is a blocking structure violation, not a warning.
    errors.extend(validate_migration_completion(repo_root))
    errors.extend(validate_first_party_shim_import_boundary(repo_root))
    # Top-level astrid/packs/ modules must be thin documented shims only.
    errors.extend(_validate_packs_top_level_modules(repo_root / "astrid" / "packs"))
    return StructureReport(errors=tuple(errors), warnings=tuple(warnings))


def validate_import_layering(root: str | Path = REPO_ROOT) -> list[str]:
    # astrid/pipeline.py is intentionally outside this validator's scope; it is
    # a top-level dispatcher and its pack imports are deferred to m5b.
    repo_root = Path(root)
    core_root = repo_root / "astrid" / "core"
    if not core_root.is_dir():
        return [f"missing core directory: {core_root}"]

    violations: list[str] = []
    for path in _iter_python_files(core_root):
        rel = _repo_rel(path, repo_root)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            violations.append(f"could not parse imports in {rel}: {exc.msg} at line {exc.lineno}")
            continue
        except UnicodeDecodeError as exc:
            violations.append(f"could not read imports in {rel}: {exc}")
            continue

        module_name = _module_name_for_path(path, repo_root)
        for node in ast.walk(tree):
            imported = _imported_modules_from_node(node, module_name=module_name)
            for module in imported:
                if not _is_forbidden_core_import(module):
                    continue
                if not _is_import_layering_exempt(path, repo_root):
                    violations.append(f"{rel}:{node.lineno} imports forbidden module {module!r}")
            for module in _dynamic_imported_modules_from_node(node):
                if (
                    _is_concrete_pack_implementation_module(module)
                    and not _is_pack_import_bridge_exempt(path, repo_root)
                ):
                    violations.append(
                        f"{rel}:{node.lineno} dynamically imports forbidden concrete pack module {module!r}"
                    )
    return violations


def validate_cli_domain_boundary(root: str | Path = REPO_ROOT) -> list[str]:
    """Reject domain-library imports of CLI modules.

    This intentionally stays narrow to avoid false positives in Astrid's
    existing CLI helper split: only files under ``astrid/domains/`` are checked,
    and only imports of ``*.cli`` modules are flagged.
    """

    repo_root = Path(root)
    domains_root = repo_root / "astrid" / "domains"
    if not domains_root.is_dir():
        return []

    violations: list[str] = []
    for path in _iter_python_files(domains_root):
        rel = _repo_rel(path, repo_root)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            violations.append(f"could not parse imports in {rel}: {exc.msg} at line {exc.lineno}")
            continue
        except UnicodeDecodeError as exc:
            violations.append(f"could not read imports in {rel}: {exc}")
            continue

        module_name = _module_name_for_path(path, repo_root)
        for node in ast.walk(tree):
            for module in _imported_modules_from_node(node, module_name=module_name):
                cli_module = _cli_module_boundary_name(module)
                if cli_module is not None:
                    violations.append(
                        f"{rel}:{node.lineno} imports CLI module {cli_module!r}; move CLI-only logic to a cli.py entrypoint or shared helper"
                    )
    return violations


_TODO_MILESTONE_RE = re.compile(r"TODO\(m\d+[ab]?\)", re.IGNORECASE)
_SYS_MODULES_INJECTION_EXEMPTIONS = frozenset(
    {
        # SD2: compile.py temporarily registers a UUID-namespaced module for
        # importlib relative imports and pops it in finally; keep the guard
        # narrow so only this approved register-then-pop pattern is exempt.
        "astrid/orchestrate/compile.py",
        # The in-process runtime invoker reloads pack modules fresh on each
        # invocation via importlib.util + sys.modules pop/assign.  This is
        # a controlled, necessary pattern to guarantee source-level freshness
        # without subprocess isolation.
        "astrid/core/runtime/in_process.py",
        # SD1: pipeline.py is an approved compatibility shim that aliases the
        # canonical gateway module through sys.modules on purpose.
        "astrid/pipeline.py",
    }
)
_STABLE_COMPATIBILITY_SHIM_EXEMPTIONS = frozenset(
    {
        # TODO(m13): revisit these explicit shim exemptions once the
        # renamed public modules have enough caller migration history.
        # M13 keeps these public import surfaces intentionally alive while
        # canonical implementations move to clearer module names.
        "astrid/_media.py",
        "astrid/_paths.py",
        "astrid/core/_search.py",
        "astrid/pipeline.py",
    }
)
_MILESTONE_COMPATIBILITY_SHIM_EXEMPTIONS = frozenset(
    {
        # Approved thin public re-export surfaces for the canonical core
        # timeline API.  These are not stale migration shims; they are the
        # intentional public compatibility layer so callers can continue to
        # import from astrid.timeline while the implementation lives in
        # astrid.core.timeline.  Adding them here prevents the generic shim
        # detector from flagging them without weakening the detector itself.
        "astrid/timeline/__init__.py",
        "astrid/timeline/timeline_model.py",
        "astrid/timeline/banodoco_composer.py",
    }
)

_FIRST_PARTY_SHIM_IMPORT_BAN = frozenset(
    {
        "astrid._media",
        "astrid._paths",
        "astrid.core._search",
    }
)
_FIRST_PARTY_SHIM_IMPORT_EXEMPTIONS: dict[str, frozenset[str]] = {
    "astrid._media": frozenset(
        {
            "tests/test_m2_public_surface.py",
            "tests/test_structure_contracts.py",
        }
    ),
    "astrid._paths": frozenset(
        {
            "tests/test_m2_public_surface.py",
            "tests/test_structure_contracts.py",
        }
    ),
    "astrid.core._search": frozenset(),
}
_PACK_RUNTIME_BRIDGE_EXEMPT_REL = frozenset(
    {
        # These files are the sanctioned pack-runtime/registry bridge layer.
        # They may resolve manifest-declared pack runtime modules without
        # weakening the general core -> packs boundary.
        "astrid/core/executor/runner.py",
        "astrid/core/orchestrator/runner.py",
        "astrid/core/pack/resolver.py",
        "astrid/core/runtime/in_process.py",
        "astrid/core/task/plan_builder.py",
    }
)
_PACK_SYSTEM_TOP_LEVEL_MODULES = frozenset(
    {
        "__init__",
        "_canonical_entrypoint",
        "agent_index",
        "cli",
        "gitignore",
        "install",
        "schemas",
        "validate",
    }
)
_DEBRIS_SCAN_ROOTS = ("astrid", "tests", "scripts")
_DEBRIS_DIR_NAMES = frozenset({"__pycache__", "build"})
_DEBRIS_FILE_NAMES = frozenset({".DS_Store"})
_COMMITTED_GOLDEN_BUILD_DIR_EXEMPTIONS: dict[str, str] = {
    # Exact repo-relative build/ directories only. Add entries here only when a
    # committed golden fixture genuinely must live under build/, and record the
    # path plus the fixture rationale inline.
    #
    # No committed golden build/ fixtures are approved today.
}


def validate_migration_completion(root: str | Path = REPO_ROOT) -> list[str]:
    repo_root = Path(root)
    astrid_root = repo_root / "astrid"
    if not astrid_root.is_dir():
        return []

    advisories: list[str] = []
    import_map = _live_import_map(repo_root)
    for path in _iter_python_files(astrid_root, excluded_parts={"packs", "tests", "__pycache__"}):
        rel = _repo_rel(path, repo_root)
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            advisories.append(f"{rel}: could not scan migration-completion markers: {exc}")
            continue

        if "DEPRECATED" in text and not _TODO_MILESTONE_RE.search(text):
            advisories.append(f"{rel}: DEPRECATED marker lacks TODO(milestone) removal target")
        if _contains_sys_modules_injection(path) and rel not in _SYS_MODULES_INJECTION_EXEMPTIONS:
            advisories.append(f"{rel}: sys.modules injection remains outside tests")

        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError as exc:
            advisories.append(f"{rel}: could not parse migration-completion scan: {exc.msg} at line {exc.lineno}")
            continue

        advisories.extend(_dangling_all_alias_advisories(tree, rel))

        if _looks_like_compatibility_shim(text):
            module_name = _module_name_for_path(path, repo_root)
            caller_count = len(import_map.get(module_name, set()))
            if caller_count > 0 and not _is_compatibility_shim_exempt(rel, text):
                advisories.append(f"{rel}: compatibility shim still has {caller_count} live import caller(s)")
    return advisories


def validate_first_party_shim_import_boundary(root: str | Path = REPO_ROOT) -> list[str]:
    """Reject first-party imports of legacy shim modules outside explicit public
    compatibility tests.

    This scans first-party source under ``astrid/`` and ``scripts/`` plus all
    repository tests. Tests are treated as non-public by default; only paths
    listed in ``_FIRST_PARTY_SHIM_IMPORT_EXEMPTIONS`` remain allowed to import
    the documented public compatibility shims.
    """
    repo_root = Path(root)
    violations: list[str] = []
    for scan_root in (repo_root / "astrid", repo_root / "scripts", repo_root / "tests"):
        for path in _iter_python_files(scan_root, excluded_parts={"__pycache__"}):
            rel = _repo_rel(path, repo_root)
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except SyntaxError as exc:
                violations.append(f"could not parse shim-import boundary in {rel}: {exc.msg} at line {exc.lineno}")
                continue
            except UnicodeDecodeError as exc:
                violations.append(f"could not read shim-import boundary in {rel}: {exc}")
                continue

            module_name = _module_name_for_path(path, repo_root)
            for node in ast.walk(tree):
                for imported in _imported_modules_from_node(node, module_name=module_name):
                    if imported not in _FIRST_PARTY_SHIM_IMPORT_BAN:
                        continue
                    if rel in _FIRST_PARTY_SHIM_IMPORT_EXEMPTIONS.get(imported, frozenset()):
                        continue
                    violations.append(f"{rel}:{node.lineno} imports banned first-party shim {imported!r}")
    return violations


def _is_compatibility_shim_exempt(rel: str, text: str) -> bool:
    return rel in _STABLE_COMPATIBILITY_SHIM_EXEMPTIONS or (
        rel in _MILESTONE_COMPATIBILITY_SHIM_EXEMPTIONS and "TODO(m5b)" in text
    )


def _validate_legacy_dirs(repo_root: Path) -> list[str]:
    errors: list[str] = []
    for dirname in LEGACY_PUBLIC_DIRS:
        candidate = repo_root / "astrid" / dirname
        if candidate.exists():
            errors.append(f"legacy public package must not exist: {candidate.relative_to(repo_root)}")
    return errors


def _validate_local_state_dirs(repo_root: Path) -> list[str]:
    errors: list[str] = []
    local_root = repo_root / ".astrid"
    if not local_root.exists():
        return errors
    for dirname in LEGACY_LOCAL_DIRS:
        candidate = local_root / dirname
        if candidate.exists():
            errors.append(f"legacy local state directory must not exist: {candidate.relative_to(repo_root)}")
    return errors


def _validate_top_level_astrid(package_root: Path) -> list[str]:
    errors: list[str] = []
    for child in sorted(package_root.iterdir()):
        if child.name.startswith("."):
            continue
        if child.is_dir() and child.name in _DEBRIS_DIR_NAMES:
            # Generated debris has a dedicated validator with narrower messages.
            continue
        if child.is_file() and child.name in _DEBRIS_FILE_NAMES:
            continue
        if child.is_file() and child.suffix == ".py" and child.name not in TOP_LEVEL_ASTRID_FILES:
            errors.append(f"top-level astrid module must move to a canonical package: {child.relative_to(package_root.parents[0])}")
        if child.is_dir() and child.name not in TOP_LEVEL_ASTRID_DIRS:
            errors.append(f"top-level astrid directory is not a canonical concept: {child.relative_to(package_root.parents[0])}")
    return errors


def _validate_generated_debris(repo_root: Path) -> list[str]:
    errors: list[str] = []
    errors.extend(_validate_golden_build_dir_exemptions())
    tracked_paths = _tracked_paths(repo_root)
    for root_name in _DEBRIS_SCAN_ROOTS:
        scan_root = repo_root / root_name
        if not scan_root.is_dir():
            continue
        for current_root, dirnames, filenames in os.walk(scan_root, topdown=True):
            current_path = Path(current_root)
            kept_dirnames: list[str] = []
            for dirname in dirnames:
                if dirname not in _DEBRIS_DIR_NAMES:
                    kept_dirnames.append(dirname)
                    continue
                candidate = current_path / dirname
                rel = _repo_rel(candidate, repo_root)
                if tracked_paths is not None and not _has_tracked_path_under(tracked_paths, rel):
                    continue
                if dirname == "build" and rel in _COMMITTED_GOLDEN_BUILD_DIR_EXEMPTIONS:
                    continue
                if dirname == "__pycache__":
                    errors.append(f"{rel}: generated debris directory must not exist")
                else:
                    errors.append(
                        f"{rel}: generated build directory must not exist outside documented golden fixtures"
                    )
            dirnames[:] = kept_dirnames

            for filename in filenames:
                if filename not in _DEBRIS_FILE_NAMES:
                    continue
                candidate = current_path / filename
                rel = _repo_rel(candidate, repo_root)
                if tracked_paths is not None and rel not in tracked_paths:
                    continue
                errors.append(f"{rel}: generated debris file must not exist")
    return errors


def _tracked_paths(repo_root: Path) -> frozenset[str] | None:
    if not (repo_root / ".git").exists():
        return None
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "ls-files", "-z", "--", *_DEBRIS_SCAN_ROOTS],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=False,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return frozenset(path for path in result.stdout.decode("utf-8").split("\0") if path)


def _has_tracked_path_under(tracked_paths: frozenset[str], rel: str) -> bool:
    prefix = f"{rel}/"
    return rel in tracked_paths or any(path.startswith(prefix) for path in tracked_paths)


def _validate_golden_build_dir_exemptions() -> list[str]:
    errors: list[str] = []
    for rel, rationale in sorted(_COMMITTED_GOLDEN_BUILD_DIR_EXEMPTIONS.items()):
        path = Path(rel)
        if path.name != "build":
            errors.append(f"{rel}: documented golden build exemption must point to an exact build/ directory")
            continue
        if not rationale.strip():
            errors.append(f"{rel}: documented golden build exemption must include a rationale")
            continue
        if len(path.parts) < 2 or path.parts[0] not in _DEBRIS_SCAN_ROOTS:
            errors.append(
                f"{rel}: documented golden build exemption must live under astrid/, tests/, or scripts/"
            )
    return errors


def _validate_pack_executor_folders(packs_root: Path) -> list[str]:
    if not packs_root.is_dir():
        return [f"missing packs directory: {packs_root}"]

    errors: list[str] = []
    repo_root = packs_root.parents[1]
    for pack_dir in _public_child_dirs(packs_root, INTERNAL_PACK_DIRS):
        for folder in _public_child_dirs(pack_dir, INTERNAL_PACK_DIRS):
            if not _has_any(folder, ("executor.yaml", "executor.yml", "executor.json", "executor.py")):
                continue
            errors.extend(_require_files(folder, ("executor.yaml", "run.py", "STAGE.md"), root=repo_root))
            if _has_any(folder, ("orchestrator.yaml", "orchestrator.yml", "orchestrator.json", "orchestrator.py")):
                errors.append(f"executor folder contains orchestrator metadata: {folder.relative_to(repo_root)}")
            try:
                definitions = load_folder_executors(folder)
            except Exception as exc:
                errors.append(f"invalid executor folder {folder.relative_to(repo_root)}: {exc}")
                continue
            if not definitions:
                errors.append(f"executor folder emitted no executor metadata: {folder.relative_to(repo_root)}")
                continue
            for definition in definitions:
                pack_segment = definition.id.split(".", 1)[0]
                if pack_segment != pack_dir.name:
                    errors.append(
                        f"executor {definition.id!r} must live in pack {pack_segment!r} but was found in pack {pack_dir.name!r}"
                    )
    return errors


def _validate_pack_orchestrator_folders(packs_root: Path) -> list[str]:
    if not packs_root.is_dir():
        return [f"missing packs directory: {packs_root}"]

    errors: list[str] = []
    repo_root = packs_root.parents[1]
    for pack_dir in _public_child_dirs(packs_root, INTERNAL_PACK_DIRS):
        for folder in _public_child_dirs(pack_dir, INTERNAL_PACK_DIRS):
            if not _has_any(folder, ("orchestrator.yaml", "orchestrator.yml", "orchestrator.json", "orchestrator.py")):
                continue
            errors.extend(_require_files(folder, ("orchestrator.yaml", "run.py", "STAGE.md"), root=repo_root))
            if _has_any(folder, ("executor.yaml", "executor.yml", "executor.json", "executor.py")):
                errors.append(f"orchestrator folder contains executor metadata: {folder.relative_to(repo_root)}")
            try:
                definitions = load_folder_orchestrators(folder)
            except Exception as exc:
                errors.append(f"invalid orchestrator folder {folder.relative_to(repo_root)}: {exc}")
                continue
            if not definitions:
                errors.append(f"orchestrator folder emitted no orchestrator metadata: {folder.relative_to(repo_root)}")
                continue
            for definition in definitions:
                pack_segment = definition.id.split(".", 1)[0]
                if pack_segment != pack_dir.name:
                    errors.append(
                        f"orchestrator {definition.id!r} must live in pack {pack_segment!r} but was found in pack {pack_dir.name!r}"
                    )
    return errors


def _public_child_dirs(root: Path, skipped: set[str]) -> tuple[Path, ...]:
    return tuple(
        sorted(
            path
            for path in root.iterdir()
            if path.is_dir()
            and path.name not in skipped
            and not path.name.startswith(".")
            and not path.name.startswith("_")
        )
    )


def _require_files(folder: Path, filenames: tuple[str, ...], *, root: Path) -> list[str]:
    return [f"{folder.relative_to(root)} missing {filename}" for filename in filenames if not (folder / filename).is_file()]


def _has_any(folder: Path, filenames: tuple[str, ...]) -> bool:
    return any((folder / filename).exists() for filename in filenames)


def _validate_pack_element_folders(packs_root: Path) -> list[str]:
    if not packs_root.is_dir():
        return []

    errors: list[str] = []
    repo_root = packs_root.parents[1]
    for pack_dir in _public_child_dirs(packs_root, INTERNAL_PACK_DIRS):
        elements_root = pack_dir / "elements"
        if not elements_root.is_dir():
            continue
        manifest_path = pack_manifest_path(pack_dir)
        kind_registry = ELEMENT_KIND_REGISTRY
        if manifest_path is not None:
            try:
                kind_registry = element_kind_registry_for_pack(load_pack_manifest(manifest_path))
            except Exception as exc:
                errors.append(f"invalid pack manifest {pack_dir.relative_to(repo_root)}: {exc}")
                continue
        for kind_dir in _public_child_dirs(elements_root, INTERNAL_PACK_DIRS):
            try:
                kind_registry.normalize(kind_dir.name)
            except ValueError:
                errors.append(
                    "unexpected element kind folder "
                    f"{kind_dir.relative_to(repo_root)}: valid kinds are {list(kind_registry.canonical_kinds())}"
                )
                continue
            for element_dir in _public_child_dirs(kind_dir, INTERNAL_PACK_DIRS):
                errors.extend(_require_files(element_dir, ("component.tsx", "element.yaml"), root=repo_root))
    return errors


def _iter_python_files(root: Path, *, excluded_parts: set[str] | None = None) -> tuple[Path, ...]:
    if not root.is_dir():
        return ()
    skipped = excluded_parts or set()
    return tuple(
        sorted(
            path
            for path in root.rglob("*.py")
            if not any(part in skipped or part.startswith(".") for part in path.relative_to(root).parts)
        )
    )


def _repo_rel(path: Path, repo_root: Path) -> str:
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.as_posix()


def _module_name_for_path(path: Path, repo_root: Path) -> str:
    rel = path.relative_to(repo_root).with_suffix("")
    parts = rel.parts
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _imported_modules_from_node(node: ast.AST, *, module_name: str) -> tuple[str, ...]:
    if isinstance(node, ast.Import):
        return tuple(alias.name for alias in node.names)
    if isinstance(node, ast.ImportFrom):
        base = _resolve_import_from_module(node, module_name=module_name)
        if _is_forbidden_core_import(base):
            return (base,)
        modules = [base]
        if base:
            modules.extend(f"{base}.{alias.name}" for alias in node.names if alias.name != "*")
        return tuple(modules)
    return ()


def _dynamic_imported_modules_from_node(node: ast.AST) -> tuple[str, ...]:
    if not isinstance(node, ast.Call) or not node.args:
        return ()
    func = node.func
    if isinstance(func, ast.Attribute):
        if not (
            isinstance(func.value, ast.Name)
            and func.value.id == "importlib"
            and func.attr == "import_module"
        ):
            return ()
    elif isinstance(func, ast.Name):
        if func.id != "import_module":
            return ()
    else:
        return ()

    module_arg = node.args[0]
    if not isinstance(module_arg, ast.Constant) or not isinstance(module_arg.value, str):
        return ()
    return (module_arg.value,)


def _resolve_import_from_module(node: ast.ImportFrom, *, module_name: str) -> str:
    module = node.module or ""
    if node.level <= 0:
        return module
    package_parts = module_name.split(".")[:-1]
    keep = max(len(package_parts) - node.level + 1, 0)
    parts = package_parts[:keep]
    if module:
        parts.extend(module.split("."))
    return ".".join(parts)


def _is_forbidden_core_import(module: str) -> bool:
    return (
        module == "astrid.packs"
        or module.startswith("astrid.packs.")
        or module == "astrid.orchestrate"
        or module.startswith("astrid.orchestrate.")
        or module == "astrid.audit"
        or module.startswith("astrid.audit.")
    )


def _is_concrete_pack_implementation_module(module: str) -> bool:
    if not module.startswith("astrid.packs."):
        return False
    parts = module.split(".")
    if len(parts) < 3:
        return False
    return parts[2] not in _PACK_SYSTEM_TOP_LEVEL_MODULES


# Modules in core/runtime/ are sanctioned to import from astrid.packs for the
# in-process entrypoint machinery.  This is a deliberate architectural choice:
# the runtime package bridges between framework and pack boundaries and needs
# access to the canonical entrypoint context that guards pack entrypoints.
_IMPORT_LAYERING_EXEMPT_REL = frozenset(
    {
        "astrid/core/runtime/in_process.py",
        # SD2: event_stream.py still imports from astrid.audit to provide a
        # single task/audit event reader.  The current exemption mechanism is
        # file-level, so this bypasses the packs/orchestrate/audit checks for
        # the whole file until finer-grained mechanics exist.
        "astrid/core/task/event_stream.py",
    }
)


def _is_import_layering_exempt(path: Path, repo_root: Path) -> bool:
    rel = _repo_rel(path, repo_root)
    return rel in _IMPORT_LAYERING_EXEMPT_REL


def _is_pack_import_bridge_exempt(path: Path, repo_root: Path) -> bool:
    rel = _repo_rel(path, repo_root)
    return rel in _PACK_RUNTIME_BRIDGE_EXEMPT_REL


def _is_cli_module(module: str) -> bool:
    return module.endswith(".cli") or ".cli." in module


def _cli_module_boundary_name(module: str) -> str | None:
    if module.endswith(".cli"):
        return module
    marker = ".cli."
    if marker not in module:
        return None
    return module.split(marker, 1)[0] + ".cli"


def _contains_sys_modules_injection(path: Path) -> bool:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        return False
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            continue
        targets: list[ast.AST]
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        else:
            targets = [node.target]
        if any(_is_sys_modules_subscript(target) for target in targets):
            return True
    return False


def _is_sys_modules_subscript(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Attribute)
        and node.value.attr == "modules"
        and isinstance(node.value.value, ast.Name)
        and node.value.value.id == "sys"
    )


def _dangling_all_alias_advisories(tree: ast.AST, rel: str) -> list[str]:
    exported = _literal_all_exports(tree)
    if not exported:
        return []
    advisories: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name) or not isinstance(node.value, ast.Name):
            continue
        if target.id in exported and node.value.id in exported:
            advisories.append(f"{rel}:{node.lineno}: __all__ exports alias {target.id} = {node.value.id}")
    return advisories


def _literal_all_exports(tree: ast.AST) -> set[str]:
    exports: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets):
            continue
        value = node.value
        if not isinstance(value, (ast.List, ast.Tuple, ast.Set)):
            continue
        for item in value.elts:
            if isinstance(item, ast.Constant) and isinstance(item.value, str):
                exports.add(item.value)
    return exports


def _validate_packs_top_level_modules(packs_root: Path) -> list[str]:
    """Validate that every top-level ``.py`` file directly inside
    ``astrid/packs/`` is either the package ``__init__.py`` or a
    documented thin compatibility/re-export shim.

    Active implementation modules at the top level of ``astrid/packs/``
    are rejected.  Shims must:

    * declare themselves as a compatibility or re-export shim in their
      module docstring, and
    * be thin (no more than 12 meaningful lines of code).

    Pack data directories (subdirectories like ``builtin/``,
    ``stream_content/``, etc.) are not checked here.
    """
    if not packs_root.is_dir():
        return []

    errors: list[str] = []
    repo_root = packs_root.parents[1]

    for child in sorted(packs_root.iterdir()):
        if not child.is_file() or child.suffix != ".py":
            continue
        if child.name == "__init__.py":
            # Package namespace — allowed even though it has real imports.
            continue

        rel = _repo_rel(child, repo_root)
        try:
            text = child.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            errors.append(f"{rel}: could not read top-level packs module: {exc}")
            continue

        if not _looks_like_compatibility_shim(text):
            errors.append(
                f"{rel}: top-level astrid/packs/ module is not a documented "
                f"thin compatibility shim"
            )

    return errors


def _looks_like_compatibility_shim(text: str) -> bool:
    lower = text.lower()
    if "compatibility shim" not in lower and "re-export shim" not in lower:
        return False
    meaningful_lines = [
        line
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#") and not line.lstrip().startswith('"""')
    ]
    return len(meaningful_lines) <= 12


def _live_import_map(repo_root: Path) -> dict[str, set[str]]:
    imports: dict[str, set[str]] = {}
    astrid_root = repo_root / "astrid"
    for path in _iter_python_files(astrid_root, excluded_parts={"tests", "__pycache__"}):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, UnicodeDecodeError):
            continue
        module_name = _module_name_for_path(path, repo_root)
        rel = _repo_rel(path, repo_root)
        for node in ast.walk(tree):
            for imported in _imported_modules_from_node(node, module_name=module_name):
                if imported:
                    imports.setdefault(imported, set()).add(rel)
    return imports


_LEGACY_RUN_RECORD_STATUS_TOKENS: frozenset[str] = frozenset(
    {
        "prepared",
        "success",
        "succeeded",
        "error",
        "orphaned",
    }
)


def validate_run_record_status_boundary(root: str | Path = REPO_ROOT) -> list[str]:
    """Flag legacy run-record status token writes that bypass ``RunStatus.value``.

    After the m5a status migration every explicit write to a run-record
    ``status`` field must serialize ``RunStatus.value`` (``running``,
    ``completed``, ``failed``, ``blocked``, ``aborted``, ``skipped``).
    This check scans for bare legacy-token string literals written into
    ``status`` keys of dict literals, which is the most common bypass
    pattern.
    """
    repo_root = Path(root)
    astrid_root = repo_root / "astrid"
    if not astrid_root.is_dir():
        return []

    advisories: list[str] = []
    for path in _iter_python_files(astrid_root, excluded_parts={"tests", "__pycache__", "packs"}):
        if path.name == "run_status.py" and path.parent.name == "contracts":
            continue
        rel = _repo_rel(path, repo_root)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict):
                continue
            advisory = _legacy_status_in_dict(node, rel)
            if advisory:
                advisories.append(advisory)
    return advisories


def _legacy_status_in_dict(node: ast.Dict, rel: str) -> str | None:
    """Return an advisory if *node* is a dict literal whose ``"status"`` key
    maps to a legacy run-record status token string literal."""
    keys = node.keys
    values = node.values
    if keys is None or len(keys) != len(values):
        return None
    for k, v in zip(keys, values):
        if not isinstance(k, ast.Constant) or not isinstance(k.value, str):
            continue
        if k.value != "status":
            continue
        if not isinstance(v, ast.Constant) or not isinstance(v.value, str):
            continue
        if v.value in _LEGACY_RUN_RECORD_STATUS_TOKENS:
            # Suppress advisory when the legacy token is immediately fed
            # through RunStatus.from_run_record_status().value — the
            # pattern ``RunStatus.from_run_record_status(...).value``
            # normalises before disk write, so it is not a bypass.
            if _value_is_normalized_through_run_status(v, node):
                return None
            return (
                f"{rel}:{node.lineno}: run-record status write uses "
                f"legacy token {v.value!r}; write RunStatus.value instead"
            )
    return None


def _value_is_normalized_through_run_status(value_node: ast.Constant, dict_node: ast.Dict) -> bool:
    """Return True when *value_node* sits inside a normalization expression
    like ``_normalize_run_record_status(...)`` that funnels through
    ``RunStatus.from_run_record_status().value``."""
    # Walk up from the Dict node through its parent chain.
    # If the dict literal is the argument to _normalize_run_record_status or
    # a similar function that calls RunStatus.from_run_record_status we
    # suppress the advisory.  In practice the dict literal is often a
    # keyword-argument value or a return value, and the normaliser is
    # called on the *status value* rather than the whole dict.  Since we
    # cannot fully resolve call chains with AST alone, we approximate:
    # if the dict's status value is subsequently processed by a function
    # whose name looks like a normaliser, suppress.
    # This is a best-effort heuristic; the validator errs on the side of
    # reporting rather than silently passing.
    return False


__all__ = [
    "StructureReport",
    "validate_cli_domain_boundary",
    "validate_first_party_shim_import_boundary",
    "validate_import_layering",
    "validate_migration_completion",
    "validate_repo_structure",
    "validate_run_record_status_boundary",
]
