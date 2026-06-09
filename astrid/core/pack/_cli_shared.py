"""Shared helpers for pack CLI modules.

Extracted from ``astrid/core/pack/cli.py`` to break circular imports between
the facade module and its leaf modules (cli_basic, cli_inspect, etc.).

All leaf modules import from this module at module level instead of reaching
back into the ``.cli`` facade via in-function lazy imports.
"""

from __future__ import annotations

from typing import Any

from astrid.core.pack import PackDefinition

_TAXONOMY_FIELDS = (
    "origin",
    "install_tier",
    "pack_type",
    "domain",
    "stability",
    "support",
)


def _pack_payload(pack: PackDefinition) -> dict:
    return pack.to_dict()


def _pack_taxonomy(pack: PackDefinition) -> dict[str, str]:
    return {field: getattr(pack, field) for field in _TAXONOMY_FIELDS}


def _print_taxonomy_block(taxonomy: dict[str, Any], *, indent: str = "") -> None:
    print(f"{indent}taxonomy:")
    for field in _TAXONOMY_FIELDS:
        print(f"{indent}  {field}: {taxonomy.get(field, '')}")
