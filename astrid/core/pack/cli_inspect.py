"""Pack inspection for the read-only manifest-ledger discovery surface."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from astrid.core.contracts.errors import AstridError
from astrid.core.env_vars import ASTRID_PACKS_PATH
from astrid.core.pack import PackDefinition, discover_packs, packs_root
from astrid.core.pack._common import (
    _COMPONENT_MANIFEST_NAMES as _INSPECT_COMPONENT_MANIFEST_NAMES,
    find_component_manifest as _find_component_manifest,
)

from ._cli_shared import _pack_payload, _pack_taxonomy, _print_taxonomy_block


def cmd_inspect(argv: list[str]) -> int:
    """Show details for a discovered manifest-ledger pack."""
    parser = argparse.ArgumentParser(
        prog="python3 -m astrid packs inspect",
        description="Show details for a discovered pack.",
    )
    parser.add_argument("pack_id", help="Pack identifier to inspect.")
    parser.add_argument("--agent", action="store_true", help="Emit the agent-facing pack view.")
    parser.add_argument("--json", action="store_true", dest="json", help="Output as JSON.")
    parser.add_argument(
        "--pack-root", action="append", dest="pack_roots",
        help="Additional pack collection root (also honors ASTRID_PACKS_PATH).",
    )
    args = parser.parse_args(argv)
    return _inspect_discovered_pack(
        pack_id=args.pack_id,
        agent=bool(args.agent),
        json_output=bool(args.json),
        pack_roots=tuple(args.pack_roots or ()),
    )


def _inspect_discovered_pack(
    *, pack_id: str, agent: bool, json_output: bool, pack_roots: tuple[str, ...] = ()
) -> int:
    roots = [packs_root(), *[Path(item).expanduser() for item in pack_roots]]
    roots.extend(
        Path(item).expanduser()
        for item in os.environ.get(ASTRID_PACKS_PATH, "").split(os.pathsep)
        if item
    )
    packs: dict[str, PackDefinition] = {}
    for root in roots:
        for pack in discover_packs(root, include_hidden=True):
            packs.setdefault(pack.id, pack)
    pack = packs.get(pack_id)
    if pack is None:
        raise AstridError(
            f"packs inspect: unknown pack {pack_id!r}",
            recovery_command="List available packs: python3 -m astrid packs list",
        )

    payload = pack.agent if agent else _pack_payload(pack)
    if json_output:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    if agent:
        for key, value in sorted(payload.items()):
            print(f"{key}: {value}")
        return 0
    for key in ("id", "name", "version", "description", "status", "visibility", "root", "manifest_path"):
        print(f"{key}: {payload.get(key, '')}")
    _print_taxonomy_block(payload.get("taxonomy", _pack_taxonomy(pack)))
    if pack.content:
        print("content:")
        for key, value in sorted(pack.content.items()):
            print(f"  {key}: {value}")
    if pack.agent:
        print("agent:")
        for key, value in sorted(pack.agent.items()):
            print(f"  {key}: {value}")
    return 0


def _handle_inspect(args: argparse.Namespace) -> int:
    return _inspect_discovered_pack(
        pack_id=args.pack_id,
        agent=bool(args.agent),
        json_output=bool(args.json),
        pack_roots=tuple(args.pack_roots or ()),
    )


__all__ = [
    "cmd_inspect",
    "_handle_inspect",
    "_inspect_discovered_pack",
    "_INSPECT_COMPONENT_MANIFEST_NAMES",
    "_find_component_manifest",
]
