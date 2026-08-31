"""First-party packs root validation.

Extracted from ``astrid.core.pack.validate`` during M4 T26.
Validates the ``astrid/packs/`` source tree structure and inventory.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

# ---------------------------------------------------------------------------
# Known first-party pack IDs and internal directories
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FIRST_PARTY_PACKS_ROOT = _REPO_ROOT / "astrid" / "packs"
_FIRST_PARTY_PACK_IDS = (
    "blender",
    "builtin",
    "comfy_wrap",
    "editorial",
    "fal",
    "foley",
    "generation",
    "iteration",
    "media",
    "moirae",
    "rendering",
    "runpod",
    "stream_content",
    "training",
    "understanding",
    "vibecomfy",
    "video_editing",
    "youtube",
)
# Internal (non-capability) directories that are allowed in the first-party
# packs root: the ``_core`` skill-only shell plus the v10 schema packs that
# own domain tables/repositories (not pack.yaml capability packs).
_FIRST_PARTY_INTERNAL_DIRS = {
    "_core",
    "references",
    "shots",
    "timeline",
    # Typed-timeline is an internal capability implementation package. Its
    # capability manifest is handled by the generic pack loader, but it is
    # not one of this root inventory's schema-pack directories.
    "typed_timeline",
}
_IGNORED_PACKS_ROOT_DIRS = {"__pycache__"}


def is_first_party_packs_root_candidate(path: str | Path) -> bool:
    """Return True when *path* looks like Astrid's multi-pack source root."""
    root = Path(path).resolve()
    if not root.is_dir():
        return False

    # Late import to avoid circular dependency at module level.
    from astrid.core.pack import pack_manifest_path

    if pack_manifest_path(root) is not None:
        return False
    recognized_dirs = {
        child.name
        for child in root.iterdir()
        if child.is_dir()
        and not child.name.startswith(".")
        and child.name not in _IGNORED_PACKS_ROOT_DIRS
        and child.name in set(_FIRST_PARTY_PACK_IDS) | _FIRST_PARTY_INTERNAL_DIRS
    }
    if root == _FIRST_PARTY_PACKS_ROOT:
        return True
    return "_core" in recognized_dirs and len(recognized_dirs) >= len(_FIRST_PARTY_PACK_IDS)


def validate_first_party_packs_root(
    packs_root: str | Path,
) -> tuple[list[str], list[str]]:
    """Validate the canonical first-party ``astrid/packs`` source tree."""
    # Late imports to avoid circular dependency at module level.
    from astrid.core.pack.validate import validate_pack

    root = Path(packs_root).resolve()
    internal_schema_errors = _validate_first_party_packs_root_inventory(root)
    layout_errors: list[str] = []
    warnings: list[str] = []

    for pack_id in _FIRST_PARTY_PACK_IDS:
        pack_dir = root / pack_id
        if not pack_dir.is_dir():
            continue
        pack_errors, pack_warnings = validate_pack(pack_dir)
        layout_errors.extend(f"{pack_id}: {error}" for error in pack_errors)
        warnings.extend(f"{pack_id}: {warning}" for warning in pack_warnings)

    errors = _aggregate_first_party_packs_root_errors(
        internal_schema_errors=internal_schema_errors,
        layout_errors=layout_errors,
    )
    return errors, warnings


def _validate_first_party_packs_root_inventory(root: Path) -> list[str]:
    """Check that the first-party packs root has the expected directory inventory."""
    # Late import to avoid circular dependency at module level.
    from astrid.core.pack import pack_manifest_path

    errors: list[str] = []
    if not root.is_dir():
        return [f"{root}: first-party packs root does not exist"]

    child_dirs = {
        child.name: child
        for child in root.iterdir()
        if child.is_dir()
        and not child.name.startswith(".")
        and child.name not in _IGNORED_PACKS_ROOT_DIRS
        and not _is_repo_ignored_first_party_child(root, child)
    }
    expected_pack_ids = set(_FIRST_PARTY_PACK_IDS)
    allowed_names = expected_pack_ids | _FIRST_PARTY_INTERNAL_DIRS

    for pack_id in sorted(expected_pack_ids - set(child_dirs)):
        errors.append(f"missing first-party pack directory: {pack_id}")

    for name in sorted(set(child_dirs) - allowed_names):
        if name == "schemas":
            errors.append(
                "unexpected top-level directory: schemas (relocated to "
                "astrid/core/pack/schemas/)"
            )
            continue
        errors.append(f"unexpected top-level directory: {name}")

    for pack_id in sorted(expected_pack_ids & set(child_dirs)):
        pack_dir = child_dirs[pack_id]
        if pack_manifest_path(pack_dir) is None:
            errors.append(
                f"{pack_id}: pack manifest not found "
                f"(pack.yaml, pack.yml, or pack.json)"
            )

    core_dir = child_dirs.get("_core")
    if core_dir is None:
        errors.append("missing internal directory: _core")
        return errors

    for manifest_name in ("pack.yaml", "pack.yml", "pack.json"):
        if (core_dir / manifest_name).is_file():
            errors.append(
                f"_core: skill-only shell must not contain {manifest_name}"
            )
    if not (core_dir / "skill" / "SKILL.md").is_file():
        errors.append("_core: skill-only shell must provide skill/SKILL.md")
    for forbidden in sorted(
        child.name
        for child in core_dir.iterdir()
        if child.is_dir() and child.name in {"executors", "orchestrators", "elements", "build"}
    ):
        errors.append(
            f"_core: skill-only shell must not contain top-level {forbidden}/"
        )

    return errors


def _is_repo_ignored_first_party_child(root: Path, child: Path) -> bool:
    if root != _FIRST_PARTY_PACKS_ROOT:
        return False
    rel = child.relative_to(_REPO_ROOT).as_posix()
    tracked = subprocess.run(
        ["git", "ls-files", "--", rel],
        cwd=_REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if not tracked.stdout.strip():
        return True
    try:
        subprocess.run(
            ["git", "check-ignore", "-q", "--", rel],
            cwd=_REPO_ROOT,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, ValueError, subprocess.CalledProcessError):
        return False
    return True


def _aggregate_first_party_packs_root_errors(
    *,
    internal_schema_errors: list[str],
    layout_errors: list[str],
) -> list[str]:
    """Combine internal-schema and layout errors into a single error list."""
    body: list[str] = []
    body.extend(f"[internal-schema] {error}" for error in internal_schema_errors)
    body.extend(f"[layout] {error}" for error in layout_errors)
    if not body:
        return []
    count = len(body)
    noun = "issue" if count == 1 else "issues"
    return [f"first-party pack validation failed ({count} {noun})", *body]


__all__ = [
    "is_first_party_packs_root_candidate",
    "validate_first_party_packs_root",
]
