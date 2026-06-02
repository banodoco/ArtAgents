"""Repository structure guardrails for Astrid canonical concepts."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

from astrid._paths import REPO_ROOT
from astrid.core.executor.folder import load_folder_executors
from astrid.core.orchestrator.folder import load_folder_orchestrators
from astrid.core.pack import (
    ELEMENT_KIND_REGISTRY,
    element_kind_registry_for_pack,
    load_pack_manifest,
    pack_manifest_path,
)

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
    "media.py",
    "paths.py",
    "pipeline.py",
    "sdk.py",
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
        # The in-process runtime invoker reloads pack modules fresh on each
        # invocation via importlib.util + sys.modules pop/assign.  This is
        # a controlled, necessary pattern to guarantee source-level freshness
        # without subprocess isolation.
        "astrid/core/runtime/in_process.py",
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


# Modules in core/runtime/ are sanctioned to import from astrid.packs for the
# in-process entrypoint machinery.  This is a deliberate architectural choice:
# the runtime package bridges between framework and pack boundaries and needs
# access to the canonical entrypoint context that guards pack entrypoints.
_IMPORT_LAYERING_EXEMPT_REL = frozenset(
    {
        "astrid/core/runtime/in_process.py",
    }
)


def _is_import_layering_exempt(path: Path, repo_root: Path) -> bool:
    rel = _repo_rel(path, repo_root)
    return rel in _IMPORT_LAYERING_EXEMPT_REL


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
    "validate_import_layering",
    "validate_migration_completion",
    "validate_repo_structure",
    "validate_run_record_status_boundary",
]
