"""Basic pack CLI handlers: validate, new, list, status.

Extracted from ``astrid/core/pack/cli.py`` during M4 giant-file split.
Contains ``cmd_validate``, ``cmd_new``, ``cmd_list`` and their supporting
helpers plus the ``_handle_*`` wrappers used by ``build_parser``.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from astrid.core.contracts.errors import AstridError
from astrid.core.pack import (
    PackDefinition,
    discover_packs,
    packs_root,
)
from astrid.core.pack.validate import (
    is_first_party_packs_root_candidate,
    validate_first_party_packs_root,
    validate_pack,
)

# Must match the pack_id pattern in _defs.json: lowercase, digits, underscore
_PACK_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")

# Duplicated from .cli to avoid circular import.  Keep in sync with
# _TAXONOMY_FIELDS in astrid.core.pack.cli and astrid.core.pack.cli_parser.
_TAXONOMY_FIELDS = (
    "origin",
    "install_tier",
    "pack_type",
    "domain",
    "stability",
    "support",
)

_SKILL_MD_STUB = """# {pack_name} — Agent Guide

## When to Use This Pack

Explain in 1-2 sentences when an agent should choose this pack.

## Entrypoints

List the orchestrators agents should start with for common tasks.

## Executors

Briefly describe each executor and its purpose.
"""


# Shared stderr sink for non-fatal warnings and diagnostics.
def _eprint(*args: object) -> None:
    print(*args, file=sys.stderr)


def _pack_id_is_valid(pack_id: str) -> bool:
    """Check that a pack id matches the v1 schema pattern."""
    return bool(_PACK_ID_RE.fullmatch(pack_id))


def _validate_pack_path(path: Path, must_exist: bool = True) -> Path:
    """Resolve and validate a pack root directory path.

    Args:
        path: The path to resolve.
        must_exist: If True, require the directory to exist.

    Returns:
        The resolved Path.

    Raises:
        SystemExit(2) on invalid paths.
    """
    resolved = path.resolve()
    if must_exist and not resolved.is_dir():
        raise AstridError(
            f"packs validate: {path} is not a directory or does not exist",
            recovery_command=f"ls -d {path}  # verify the path exists and is a directory",
        )
    return resolved


def _validate_target(path: Path) -> tuple[list[str], list[str]]:
    if is_first_party_packs_root_candidate(path):
        return validate_first_party_packs_root(path)
    return validate_pack(path)


def cmd_validate(argv: list[str]) -> int:
    """Run static validation on a pack root directory.

    Usage: python3 -m astrid packs validate <path>
    """
    parser = argparse.ArgumentParser(
        prog="python3 -m astrid packs validate",
        description="Statically validate a pack directory.",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Path to the pack root directory (default: current directory).",
    )
    parser.add_argument(
        "--warnings",
        action="store_true",
        help="Also print non-fatal warnings.",
    )
    args = parser.parse_args(argv)

    pack_root = _validate_pack_path(Path(args.path))

    errors, warnings = _validate_target(pack_root)

    if errors:
        raise AstridError(
            "\n".join(errors),
            recovery_command="Fix the validation errors listed above and re-run: python3 -m astrid packs validate",
        )

    if args.warnings and warnings:
        for w in warnings:
            _eprint(f"warning: {w}")

    resolved = pack_root.resolve()
    if is_first_party_packs_root_candidate(resolved):
        print(f"valid: {resolved} (19 first-party packs)")
    else:
        print(f"valid: {resolved}")
    return 0


def _pack_category(pack: PackDefinition) -> str:
    category = pack.metadata.get("category")
    if isinstance(category, str):
        return category
    return ""


def _effective_status(pack: PackDefinition) -> str:
    if pack.agent.get("purpose") == "TODO: describe what this pack is for":
        return "stub"
    return pack.status


def _taxonomy_filters(args: argparse.Namespace) -> dict[str, str]:
    return {
        field: value
        for field in _TAXONOMY_FIELDS
        if isinstance((value := getattr(args, field, None)), str) and value
    }


def _matches_taxonomy_filters(pack: PackDefinition, args: argparse.Namespace) -> bool:
    for field, value in _taxonomy_filters(args).items():
        if getattr(pack, field) != value:
            return False
    return True


def _filtered_packs(
    args: argparse.Namespace, *, include_hidden: bool | None = None
) -> list[PackDefinition]:
    show_hidden = bool(getattr(args, "show_hidden", False))
    packs = list(
        discover_packs(
            packs_root(),
            include_hidden=show_hidden if include_hidden is None else include_hidden,
        )
    )
    category = getattr(args, "category", None)
    status = getattr(args, "status", None)
    visibility = getattr(args, "visibility", None)
    if category:
        packs = [pack for pack in packs if _pack_category(pack) == category]
    packs = [pack for pack in packs if _matches_taxonomy_filters(pack, args)]
    if status:
        packs = [pack for pack in packs if _effective_status(pack) == status]
    if visibility:
        packs = [pack for pack in packs if pack.visibility == visibility]
    return packs


def _create_pack_skeleton(pack_id: str) -> int:
    """Create and validate a new pack skeleton in the current directory."""
    if not _pack_id_is_valid(pack_id):
        raise AstridError(
            f"packs new: invalid pack id {pack_id!r}. "
            f"Must match pattern: ^[a-z][a-z0-9_]*$",
            valid_options=[],
            recovery_command="Pick a pack id using only lowercase letters, digits, and underscores (e.g., my_pack)",
        )

    target = Path.cwd() / pack_id
    if target.exists():
        raise AstridError(
            f"packs new: directory {target} already exists; "
            f"refusing to overwrite",
            recovery_command=f"Remove the existing directory first: rm -rf {target}",
        )

    if not target.parent.is_dir():
        raise AstridError(
            f"packs new: parent directory {target.parent} does not exist",
            recovery_command="Create the parent directory or run packs new from an existing directory",
        )

    pack_name = pack_id.replace("_", " ").title()
    description = f"A pack for {pack_name}."

    target.mkdir(parents=False)
    for dirname in ("executors", "orchestrators", "elements"):
        (target / dirname).mkdir(parents=False)

    pack_yaml = target / "pack.yaml"
    pack_yaml.write_text(
        f"""schema_version: 1
id: {pack_id}
name: {pack_name}
version: 0.1.0
# One-line summary shown in `packs list` and search results. Make it specific.
description: {description}
origin: external
install_tier: core
pack_type: capability
domain: system
stability: stable
support: core
# Search/selection metadata: agents find and choose packs by these. Fill them in.
keywords: []          # search terms an agent would type, e.g. [video, editing, ffmpeg]
capabilities: []      # concrete things this pack can do, e.g. [trim_clip, concat, add_subtitles]
content:
  executors: executors
  orchestrators: orchestrators
  elements: elements
agent:
  purpose: "TODO: describe what this pack is for"
  do_not_use_for: "TODO: when an agent should NOT pick this pack"
  normal_entrypoints: []   # orchestrator/executor ids an agent should start with
  required_context: []     # inputs/secrets an agent must have before using this pack
""",
        encoding="utf-8",
    )

    skill_dir = target / "skill"
    skill_dir.mkdir(parents=False)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(
        _SKILL_MD_STUB.format(pack_name=pack_name),
        encoding="utf-8",
    )

    created = [
        "pack.yaml",
        "executors/",
        "orchestrators/",
        "elements/",
        "skill/SKILL.md",
    ]
    for rel in created:
        print(f"created {target.name}/{rel}")

    errors, warnings = validate_pack(target)
    if errors:
        error_details = "\n".join(f"  {err}" for err in errors)
        raise AstridError(
            f"packs new: scaffolded pack fails validation ({len(errors)} error(s))\n{error_details}",
            recovery_command="Fix the validation errors in the scaffolded pack files, then re-run: python3 -m astrid packs validate",
        )

    if warnings:
        for w in warnings:
            _eprint(f"warning: {w}")

    print(f"pack {pack_id!r} created and validated: {target}")
    return 0


def cmd_new(argv: list[str]) -> int:
    """Scaffold a minimal pack directory in the CWD.

    Usage: python3 -m astrid packs new <id>
    """
    parser = argparse.ArgumentParser(
        prog="python3 -m astrid packs new",
        description="Create a new pack skeleton in the current directory.",
    )
    parser.add_argument(
        "pack_id",
        help="Pack identifier (lowercase, digits, underscore; e.g., my_project).",
    )
    args = parser.parse_args(argv)
    return _create_pack_skeleton(args.pack_id)


# pack list
# ---------------------------------------------------------------------------


def _list_installed_packs() -> int:
    """Render the installed-pack list used by the public wrapper."""
    from astrid.core.pack.store import InstalledPackStore

    store = InstalledPackStore()
    records = store.list_installed()

    if not records:
        print("No packs installed.")
        return 0

    col_id = max(max(len(r.pack_id) for r in records), 2)
    col_name = max(max(len(r.name) for r in records), 4)
    col_version = max(max(len(r.version) for r in records), 7)
    col_status = 6
    col_installed = 19

    header = (
        f"{'ID':<{col_id}}  {'NAME':<{col_name}}  "
        f"{'VERSION':<{col_version}}  {'STATUS':<{col_status}}  "
        f"{'INSTALLED':<{col_installed}}"
    )
    print(header)
    print("-" * len(header))

    for record in records:
        status = "active" if record.active else "inactive"
        print(
            f"{record.pack_id:<{col_id}}  {record.name:<{col_name}}  "
            f"{record.version:<{col_version}}  {status:<{col_status}}  "
            f"{record.installed_at:<{col_installed}}"
        )

    return 0


def cmd_list(argv: list[str]) -> int:
    """List installed external packs.

    Usage: python3 -m astrid packs list
    """
    parser = argparse.ArgumentParser(
        prog="python3 -m astrid packs list",
        description="List installed external packs.",
    )
    parser.parse_args(argv)  # no arguments, just parses --help
    return _list_installed_packs()


# ── Grouped-output helpers (used by _handle_list / _handle_status) ──────────


def _group_packs_by_domain(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        taxonomy = row.get("taxonomy")
        if isinstance(taxonomy, dict):
            domain = taxonomy.get("domain")
        else:
            domain = row.get("domain")
        label = str(domain or "general")
        groups.setdefault(label, []).append(row)
    return [
        {
            "group_by": "domain",
            "value": domain,
            "taxonomy": {"domain": domain},
            "packs": sorted(group_rows, key=lambda pack_row: str(pack_row["id"])),
        }
        for domain, group_rows in sorted(groups.items())
    ]


def _with_grouped_payload(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {"packs": rows, "groups": _group_packs_by_domain(rows)}


def _format_list_row(row: dict[str, Any]) -> None:
    taxonomy = row.get("taxonomy", {})
    print(
        f"{row['id']}\t{row['name']}\t{row['version']}\t"
        f"origin={taxonomy.get('origin', '')}\t"
        f"tier={taxonomy.get('install_tier', '')}\t"
        f"type={taxonomy.get('pack_type', '')}\t"
        f"stability={taxonomy.get('stability', '')}\t"
        f"support={taxonomy.get('support', '')}\t"
        f"{row['description']}"
    )


def _format_status_row(row: dict[str, Any]) -> None:
    validation = row["validation"]
    taxonomy = row.get("taxonomy", {})
    print(
        f"{row['id']}\t{row['effective_status']}\t{row['visibility']}\t"
        f"errors={validation['errors']}\twarnings={validation['warnings']}\t"
        f"origin={taxonomy.get('origin', '')}\t"
        f"tier={taxonomy.get('install_tier', '')}\t"
        f"type={taxonomy.get('pack_type', '')}\t"
        f"stability={taxonomy.get('stability', '')}\t"
        f"support={taxonomy.get('support', '')}\t"
        f"{row['description']}"
    )


def _print_grouped_rows(rows: list[dict[str, Any]], *, row_formatter: Any) -> None:
    for index, group in enumerate(_group_packs_by_domain(rows)):
        if index:
            print()
        print(f"taxonomy: domain={group['value']}")
        for row in group["packs"]:
            row_formatter(row)


# ── Handler wrappers used by build_parser ───────────────────────────────────


def _handle_validate(args: argparse.Namespace) -> int:
    """Handler for ``packs validate``."""
    pack_root = _validate_pack_path(Path(args.path))
    errors, warnings = _validate_target(pack_root)

    if errors:
        raise AstridError(
            "\n".join(errors),
            recovery_command="Fix the validation errors listed above and re-run: python3 -m astrid packs validate",
        )

    if args.warnings and warnings:
        for warning in warnings:
            _eprint(f"warning: {warning}")

    resolved = pack_root.resolve()
    if is_first_party_packs_root_candidate(resolved):
        print(f"valid: {resolved} (19 first-party packs)")
    else:
        print(f"valid: {resolved}")
    return 0


def _handle_new(args: argparse.Namespace) -> int:
    """Handler for ``packs new``."""
    return _create_pack_skeleton(args.pack_id)


def _handle_list(args: argparse.Namespace) -> int:
    """Handler for ``packs list``."""
    # _pack_payload is defined in .cli; late-import to avoid circular deps.
    from .cli import _pack_payload

    packs = _filtered_packs(args)
    rows = [_pack_payload(pack) for pack in packs]
    if args.json:
        print(json.dumps(_with_grouped_payload(rows), indent=2, sort_keys=True))
        return 0
    _print_grouped_rows(rows, row_formatter=_format_list_row)
    return 0


def _handle_status(args: argparse.Namespace) -> int:
    """Handler for ``packs status``."""
    # _pack_payload is defined in .cli; late-import to avoid circular deps.
    from .cli import _pack_payload

    packs = _filtered_packs(args)
    rows: list[dict[str, Any]] = []
    for pack in packs:
        errors, warnings = validate_pack(pack.root)
        payload = _pack_payload(pack)
        payload["effective_status"] = _effective_status(pack)
        payload["validation"] = {
            "errors": len(errors),
            "warnings": len(warnings),
            "error_messages": errors,
            "warning_messages": warnings,
        }
        rows.append(payload)
    if args.json:
        print(json.dumps(_with_grouped_payload(rows), indent=2, sort_keys=True))
        return 0
    _print_grouped_rows(rows, row_formatter=_format_status_row)
    return 0
