""":mod:`astrid.core.pack.cli` — Canonical pack CLI implementation.

This is the canonical home for the ``astrid packs`` CLI machinery,
moved from ``astrid/packs/cli.py`` during M1 Pack Layout Normalization
(Plan v1.0).

The ``astrid.core.pack_machinery.cli`` and ``astrid.packs.cli`` modules
are now thin compatibility re-export shims. All new imports should
target this module directly.

M4 giant-file split: ``build_parser`` moved to ``.cli_parser``,
validate/new/list/status handlers moved to ``.cli_basic``, inspect helpers
moved to ``.cli_inspect``, and agent-index/search handlers moved to
``.cli_search``.  This module remains a facade that re-exports the
canonical definitions.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any, Optional

from astrid.contracts.errors import AstridError
from astrid.core.pack import PackDefinition

# ── Re-exports from split modules ───────────────────────────────────────────
# build_parser and _add_taxonomy_filter_args are now defined in cli_parser.
# Basic handlers (validate, new, list, status) are now defined in cli_basic.
# Inspect helpers are now defined in cli_inspect.
# Agent-index and search handlers are now defined in cli_search.
# Everything is re-exported here so that ``astrid.packs.cli`` and
# ``astrid.core.pack_machinery.cli`` compatibility shims (which use
# ``from astrid.core.pack.cli import *``) continue to resolve correctly.
from .cli_parser import build_parser, _add_taxonomy_filter_args  # noqa: E402, F401
from .cli_basic import (  # noqa: E402, F401
    _create_pack_skeleton,
    _effective_status,
    _eprint,
    _filtered_packs,
    _format_list_row,
    _format_status_row,
    _group_packs_by_domain,
    _handle_list,
    _handle_new,
    _handle_status,
    _handle_validate,
    _list_installed_packs,
    _matches_taxonomy_filters,
    _pack_category,
    _pack_id_is_valid,
    _PACK_ID_RE,
    _print_grouped_rows,
    _SKILL_MD_STUB,
    _taxonomy_filters,
    _validate_pack_path,
    _with_grouped_payload,
    cmd_list,
    cmd_new,
    cmd_validate,
)
from .cli_inspect import (  # noqa: E402, F401
    _build_agent_view,
    _build_full_inspect,
    _find_component_manifest,
    _handle_inspect,
    _inspect_discovered_pack,
    _inspect_installed_pack,
    _INSPECT_COMPONENT_MANIFEST_NAMES,
    _print_agent_view,
    _print_full_inspect,
    _read_stage_excerpt,
    _scan_inspect_components,
    cmd_inspect,
)
from .cli_search import (  # noqa: E402, F401
    _handle_agent_index,
    _handle_search,
    _pack_search_text,
    _score_pack,
    _SEARCH_FIELD_WEIGHTS,
)

# ── Re-exports for backward compatibility — tests access via cli namespace ──
from astrid.core.pack.validate import (  # noqa: E402, F401
    extract_trust_summary,
    validate_pack,
)

# ── Shared constants ────────────────────────────────────────────────────────

_TAXONOMY_FIELDS = (
    "origin",
    "install_tier",
    "pack_type",
    "domain",
    "stability",
    "support",
)


# ── Shared helpers (used by both basic and inspect handlers) ──────────────


def _pack_payload(pack: PackDefinition) -> dict:
    return pack.to_dict()


def _pack_taxonomy(pack: PackDefinition) -> dict[str, str]:
    return {field: getattr(pack, field) for field in _TAXONOMY_FIELDS}


def _print_taxonomy_block(taxonomy: dict[str, Any], *, indent: str = "") -> None:
    print(f"{indent}taxonomy:")
    for field in _TAXONOMY_FIELDS:
        print(f"{indent}  {field}: {taxonomy.get(field, '')}")


# ── install / update / uninstall / rollback handlers ─────────────────────
# These are thin delegation wrappers that stay in the facade because they
# call into astrid.core.pack.install and have no helper logic of their own.


def _handle_install(args: argparse.Namespace) -> int:
    """Handler for ``packs install``."""
    from astrid.core.pack.install import _run_install_command

    return _run_install_command(args)


def _handle_update(args: argparse.Namespace) -> int:
    """Handler for ``packs update``."""
    from astrid.core.pack.install import _run_update_command

    return _run_update_command(args)


def _handle_uninstall(args: argparse.Namespace) -> int:
    """Handler for ``packs uninstall``."""
    from astrid.core.pack.install import _run_uninstall_command

    return _run_uninstall_command(args)


def _handle_rollback(args: argparse.Namespace) -> int:
    """Handler for ``packs rollback``."""
    from astrid.core.pack.install import _run_rollback_command

    return _run_rollback_command(args)


# ── Entry point ─────────────────────────────────────────────────────────────


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

    try:
        return int(handler(args))
    except AstridError as exc:
        from astrid.contracts.errors import render_astrid_error

        return render_astrid_error(exc)


__all__ = [
    # Public API
    "build_parser",
    "cmd_inspect",
    "cmd_list",
    "cmd_new",
    "cmd_validate",
    "main",
    # Re-exported for backward compatibility — used by tests that mock
    # through the astrid.packs.cli shim path.
    "extract_trust_summary",  # imported from validate, tests access via cli
    "validate_pack",  # imported from validate, available via cli namespace
    "_PACK_ID_RE",
    "_SKILL_MD_STUB",
    "_TAXONOMY_FIELDS",
    "_INSPECT_COMPONENT_MANIFEST_NAMES",
    "_SEARCH_FIELD_WEIGHTS",
    "_add_taxonomy_filter_args",
    "_build_agent_view",
    "_build_full_inspect",
    "_create_pack_skeleton",
    "_effective_status",
    "_eprint",
    "_filtered_packs",
    "_find_component_manifest",
    "_format_list_row",
    "_format_status_row",
    "_group_packs_by_domain",
    "_handle_agent_index",
    "_handle_install",
    "_handle_inspect",
    "_handle_list",
    "_handle_new",
    "_handle_rollback",
    "_handle_search",
    "_handle_status",
    "_handle_uninstall",
    "_handle_update",
    "_handle_validate",
    "_inspect_discovered_pack",
    "_inspect_installed_pack",
    "_list_installed_packs",
    "_matches_taxonomy_filters",
    "_pack_category",
    "_pack_id_is_valid",
    "_pack_payload",
    "_pack_search_text",
    "_pack_taxonomy",
    "_print_agent_view",
    "_print_full_inspect",
    "_print_grouped_rows",
    "_print_taxonomy_block",
    "_read_stage_excerpt",
    "_scan_inspect_components",
    "_score_pack",
    "_taxonomy_filters",
    "_validate_pack_path",
    "_with_grouped_payload",
]

if __name__ == "__main__":
    raise SystemExit(main())
