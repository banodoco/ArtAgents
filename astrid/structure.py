"""Repository structure guardrails for Astrid canonical concepts."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

from astrid._paths import REPO_ROOT
from astrid.core.executor.folder import load_folder_executors
from astrid.core.orchestrator.folder import load_folder_orchestrators
from astrid.core.pack import ELEMENT_KINDS as _ELEMENT_KINDS

LEGACY_PUBLIC_DIRS = ("conductors", "performers", "instruments", "primitives", "executors", "orchestrators")
LEGACY_LOCAL_DIRS = ("performers", "conductors", "nodes", "instruments", "primitives")
INTERNAL_PACK_DIRS = {"__pycache__", "schemas"}
TOP_LEVEL_ASTRID_FILES = {
    "__init__.py",
    "__main__.py",
    "_media.py",
    "_paths.py",
    "doctor.py",
    "pipeline.py",
    "setup_cli.py",
    "structure.py",
    "theme_schema.py",
}
TOP_LEVEL_ASTRID_DIRS = {
    "__pycache__",
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
    errors.extend(_validate_pack_executor_folders(repo_root / "astrid" / "packs"))
    errors.extend(_validate_pack_orchestrator_folders(repo_root / "astrid" / "packs"))
    errors.extend(_validate_pack_element_folders(repo_root / "astrid" / "packs"))
    errors.extend(validate_import_layering(repo_root))
    # Migration-completion drift is a blocking structure violation, not a warning.
    errors.extend(validate_migration_completion(repo_root))
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
            if not imported:
                continue
            for module in imported:
                if not _is_forbidden_core_import(module):
                    continue
                if _is_import_layering_exempt(path, repo_root):
                    continue
                violations.append(f"{rel}:{node.lineno} imports forbidden module {module!r}")
    return violations


_TODO_MILESTONE_RE = re.compile(r"TODO\(m\d+[ab]?\)", re.IGNORECASE)
_SYS_MODULES_INJECTION_EXEMPTIONS = frozenset(
    {
        # SD2: compile.py temporarily registers a UUID-namespaced module for
        # importlib relative imports and pops it in finally; keep the guard
        # narrow so only this approved register-then-pop pattern is exempt.
        "astrid/orchestrate/compile.py",
    }
)
_COMPATIBILITY_SHIM_EXEMPTIONS = frozenset()


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


def _is_compatibility_shim_exempt(rel: str, text: str) -> bool:
    return rel in _COMPATIBILITY_SHIM_EXEMPTIONS and "TODO(m5b)" in text


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
        if child.is_file() and child.suffix == ".py" and child.name not in TOP_LEVEL_ASTRID_FILES:
            errors.append(f"top-level astrid module must move to a canonical package: {child.relative_to(package_root.parents[0])}")
        if child.is_dir() and child.name not in TOP_LEVEL_ASTRID_DIRS:
            errors.append(f"top-level astrid directory is not a canonical concept: {child.relative_to(package_root.parents[0])}")
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
        for kind_dir in _public_child_dirs(elements_root, INTERNAL_PACK_DIRS):
            if kind_dir.name not in _ELEMENT_KINDS:
                errors.append(
                    f"unexpected element kind folder {kind_dir.relative_to(repo_root)}: must be one of {list(_ELEMENT_KINDS)}"
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
    return module == "astrid.packs" or module.startswith("astrid.packs.") or module == "astrid.orchestrate" or module.startswith(
        "astrid.orchestrate."
    )


def _is_import_layering_exempt(path: Path, repo_root: Path) -> bool:
    return False


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


__all__ = [
    "StructureReport",
    "validate_import_layering",
    "validate_migration_completion",
    "validate_repo_structure",
]
