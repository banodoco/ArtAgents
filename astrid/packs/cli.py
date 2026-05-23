"""`astrid packs` CLI: validate and new subcommands.

``packs validate <path>`` statically validates a pack root directory.
``packs new <id>`` scaffolds a minimal pack skeleton in the CWD.

Neither command loads the built-in registry, imports pack code, or
requires a bound session.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional

from astrid.core.pack import PackDefinition, discover_packs, load_pack_manifest, packs_root
from astrid.packs.validate import validate_pack

# Must match the pack_id pattern in _defs.json: lowercase, digits, underscore
_PACK_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")

_STAGE_MD_STUB = """# {pack_name}

## Purpose

What this pack does and when to use it.

## Components

- Executors: ...
- Orchestrators: ...
"""

_README_MD_STUB = """# {pack_name}

{description}

## Getting Started

1. Install Astrid
2. Run `python3 -m astrid packs validate .`
3. Start building executors and orchestrators
"""

_AGENTS_MD_STUB = """# {pack_name} — Agent Guide

## When to Use This Pack

Explain in 1-2 sentences when an agent should choose this pack.

## Entrypoints

List the orchestrators agents should start with for common tasks.

## Executors

Briefly describe each executor and its purpose.
"""


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
        print(
            f"packs validate: {path} is not a directory or does not exist",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return resolved


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

    errors, warnings = validate_pack(pack_root)

    if errors:
        for err in errors:
            print(err, file=sys.stderr)
        return 1

    if args.warnings and warnings:
        for w in warnings:
            print(f"warning: {w}", file=sys.stderr)

    resolved = pack_root.resolve()
    print(f"valid: {resolved}")
    return 0


def _pack_payload(pack: PackDefinition) -> dict:
    return pack.to_dict()


def _pack_category(pack: PackDefinition) -> str:
    category = pack.metadata.get("category")
    if isinstance(category, str):
        return category
    return ""


def _effective_status(pack: PackDefinition) -> str:
    if pack.agent.get("purpose") == "TODO: describe what this pack is for":
        return "stub"
    return pack.status


def _filtered_packs(args: argparse.Namespace, *, include_hidden: bool | None = None) -> list[PackDefinition]:
    show_hidden = bool(getattr(args, "show_hidden", False))
    packs = list(discover_packs(packs_root(), include_hidden=show_hidden if include_hidden is None else include_hidden))
    category = getattr(args, "category", None)
    status = getattr(args, "status", None)
    visibility = getattr(args, "visibility", None)
    if category:
        packs = [pack for pack in packs if _pack_category(pack) == category]
    if status:
        packs = [pack for pack in packs if _effective_status(pack) == status]
    if visibility:
        packs = [pack for pack in packs if pack.visibility == visibility]
    return packs


def _handle_list(args: argparse.Namespace) -> int:
    packs = _filtered_packs(args)
    if args.json:
        print(json.dumps({"packs": [_pack_payload(pack) for pack in packs]}, indent=2, sort_keys=True))
        return 0
    for pack in packs:
        print(f"{pack.id}\t{pack.name}\t{pack.version}\t{pack.description}")
    return 0


def _handle_inspect(args: argparse.Namespace) -> int:
    packs = {pack.id: pack for pack in discover_packs(packs_root(), include_hidden=True)}
    pack = packs.get(args.pack_id)
    if pack is None:
        print(f"packs inspect: unknown pack {args.pack_id!r}", file=sys.stderr)
        return 1
    payload = _pack_payload(pack)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    for key in ("id", "name", "version", "description", "status", "visibility", "root", "manifest_path"):
        print(f"{key}: {payload.get(key, '')}")
    if pack.content:
        print("content:")
        for key, value in sorted(pack.content.items()):
            print(f"  {key}: {value}")
    if pack.agent:
        print("agent:")
        for key, value in sorted(pack.agent.items()):
            print(f"  {key}: {value}")
    return 0


def _handle_status(args: argparse.Namespace) -> int:
    packs = list(discover_packs(packs_root(), include_hidden=bool(args.show_hidden)))
    rows: list[dict] = []
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
        print(json.dumps({"packs": rows}, indent=2, sort_keys=True))
        return 0
    for row in rows:
        validation = row["validation"]
        print(
            f"{row['id']}\t{row['effective_status']}\t{row['visibility']}\t"
            f"errors={validation['errors']}\twarnings={validation['warnings']}\t{row['description']}"
        )
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

    pack_id: str = args.pack_id

    # Validate the pack id
    if not _pack_id_is_valid(pack_id):
        print(
            f"packs new: invalid pack id {pack_id!r}. "
            f"Must match pattern: ^[a-z][a-z0-9_]*$",
            file=sys.stderr,
        )
        return 2

    # Target directory in CWD
    target = Path.cwd() / pack_id
    if target.exists():
        print(
            f"packs new: directory {target} already exists; "
            f"refusing to overwrite",
            file=sys.stderr,
        )
        return 1

    # Ensure parent (CWD) exists
    if not target.parent.is_dir():
        print(
            f"packs new: parent directory {target.parent} does not exist",
            file=sys.stderr,
        )
        return 1

    # Create the pack skeleton
    pack_name = pack_id.replace("_", " ").title()
    description = f"A pack for {pack_name}."

    target.mkdir(parents=False)

    # pack.yaml
    pack_yaml = target / "pack.yaml"
    pack_yaml.write_text(
        f"""schema_version: 1
id: {pack_id}
name: {pack_name}
version: 0.1.0
description: {description}
content:
  executors: executors
  orchestrators: orchestrators
  elements: elements
agent:
  purpose: "TODO: describe what this pack is for"
""",
        encoding="utf-8",
    )

    # AGENTS.md
    agents_md = target / "AGENTS.md"
    agents_md.write_text(
        _AGENTS_MD_STUB.format(pack_name=pack_name),
        encoding="utf-8",
    )

    # README.md
    readme_md = target / "README.md"
    readme_md.write_text(
        _README_MD_STUB.format(pack_name=pack_name, description=description),
        encoding="utf-8",
    )

    # STAGE.md at pack root
    stage_md = target / "STAGE.md"
    stage_md.write_text(
        _STAGE_MD_STUB.format(pack_name=pack_name),
        encoding="utf-8",
    )

    # Create content root directories
    for subdir in ("executors", "orchestrators", "elements"):
        (target / subdir).mkdir(parents=False)

    # Report what was created
    created = [
        "pack.yaml",
        "AGENTS.md",
        "README.md",
        "STAGE.md",
        "executors/",
        "orchestrators/",
        "elements/",
    ]
    for rel in created:
        print(f"created {target.name}/{rel}")

    # Validate the new pack before declaring success
    errors, warnings = validate_pack(target)
    if errors:
        print(
            f"packs new: scaffolded pack fails validation ({len(errors)} error(s))",
            file=sys.stderr,
        )
        for err in errors:
            print(f"  {err}", file=sys.stderr)
        return 1

    if warnings:
        for w in warnings:
            print(f"warning: {w}", file=sys.stderr)

    print(f"pack {pack_id!r} created and validated: {target}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the ``packs`` subcommand parser."""
    parser = argparse.ArgumentParser(
        prog="python3 -m astrid packs",
        description="Manage and validate Astrid packs.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser(
        "validate", help="Statically validate a pack directory."
    )
    validate_parser.add_argument(
        "path", nargs="?", default=".", help="Path to pack root (default: .)"
    )
    validate_parser.add_argument(
        "--warnings", action="store_true", help="Also print non-fatal warnings."
    )
    validate_parser.set_defaults(handler=_handle_validate)

    list_parser = subparsers.add_parser("list", help="List discovered packs.")
    list_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    list_parser.add_argument("--category", help="Filter by metadata.category.")
    list_parser.add_argument("--status", choices=("active", "deprecated", "stub", "experimental"), help="Filter by effective status.")
    list_parser.add_argument("--visibility", choices=("visible", "hidden"), help="Filter by visibility.")
    list_parser.add_argument("--show-hidden", action="store_true", help="Include hidden packs.")
    list_parser.set_defaults(handler=_handle_list)

    inspect_parser = subparsers.add_parser("inspect", help="Inspect one pack.")
    inspect_parser.add_argument("pack_id")
    inspect_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    inspect_parser.set_defaults(handler=_handle_inspect)

    status_parser = subparsers.add_parser("status", help="Validate and summarize discovered packs.")
    status_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    status_parser.add_argument("--show-hidden", action="store_true", help="Include hidden packs.")
    status_parser.set_defaults(handler=_handle_status)

    new_parser = subparsers.add_parser(
        "new", help="Create a new pack skeleton in the current directory."
    )
    new_parser.add_argument("pack_id", help="Pack identifier (e.g., my_project).")
    new_parser.set_defaults(handler=_handle_new)

    return parser


def _handle_validate(args: argparse.Namespace) -> int:
    """Handler for ``packs validate``."""
    return cmd_validate([args.path] + (["--warnings"] if args.warnings else []))


def _handle_new(args: argparse.Namespace) -> int:
    """Handler for ``packs new``."""
    return cmd_new([args.pack_id])


def main(argv: Optional[list[str]] = None) -> int:
    """Entry point for ``astrid packs`` CLI.

    Args:
        argv: Command-line arguments (excluding the ``packs`` verb).
              If None, reads from sys.argv[1:].

    Returns:
        Exit code (0 on success).
    """
    if argv is None:
        argv = sys.argv[1:]

    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        # argparse exits on --help or parse errors
        return int(exc.code) if exc.code is not None else 2

    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_usage(file=sys.stderr)
        return 2

    return int(handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
