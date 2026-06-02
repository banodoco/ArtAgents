"""CLI for ``astrid models`` — model catalog discovery.

This module is imported by ``astrid/pipeline.py`` when the user invokes
``astrid models ...``.

Schema v2: model → mode → backend taxonomy.  ``astrid models list`` shows
a MODES column with per-backend availability indicators (e.g. ``t2i:LC``,
``i2i:C``, ``edit:L``).  ``astrid models show <id>`` prints per-mode
supports/requires, backend templates/endpoints, and param_maps.
"""

from __future__ import annotations

import argparse
import json
import sys

from astrid.contracts.errors import AstridError
from astrid.core.model_catalog.registry import ModelRegistry


def _build_parser() -> argparse.ArgumentParser:
    """Build the argparse parser for ``astrid models``."""
    parser = argparse.ArgumentParser(
        prog="astrid models",
        description="Discover registered generation models.",
    )
    sub = parser.add_subparsers(dest="cmd")

    # ``astrid models list``
    list_p = sub.add_parser("list", aliases=["ls"], help="List registered models")
    list_p.add_argument(
        "--json",
        action="store_true",
        dest="use_json",
        help="Emit machine-readable JSON instead of a table.",
    )
    list_p.add_argument(
        "--include-closed",
        action="store_true",
        dest="include_closed",
        help="Include closed-weight models (hidden by default).",
    )
    list_p.set_defaults(handler=_cmd_list)

    # ``astrid models show <model-id>``
    show_p = sub.add_parser("show", help="Show details for a single model")
    show_p.add_argument(
        "model_id",
        metavar="MODEL-ID",
        help="Registered model id (e.g. z-image, flux-dev).",
    )
    show_p.add_argument(
        "--json",
        action="store_true",
        dest="use_json",
        help="Emit machine-readable JSON instead of formatted text.",
    )
    show_p.set_defaults(handler=_cmd_show)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point for ``astrid models ...``.

    Returns 0 on success, 1 on registry-load failure, 2 on usage error.
    """
    parser = _build_parser()
    try:
        args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    except SystemExit as exc:
        return int(exc.code or 2)

    handler = getattr(args, "handler", None)
    if handler is not None:
        return handler(args)
    # argparse handles unknown subcommands via SystemExit
    return 2


# ------------------------------------------------------------------
# _cmd_list
# ------------------------------------------------------------------


def _cmd_list(args: argparse.Namespace) -> int:
    """``astrid models list`` — print registered models."""
    try:
        registry = ModelRegistry.load_default()
    except Exception as exc:
        raise AstridError(
            f"failed to load model registry: {exc}",
            recovery_command="astrid models list",
            state_snapshot={"command": "models list"},
        ) from exc

    entries = registry.list_all(include_closed=args.include_closed)

    if args.use_json:
        output = []
        for e in entries:
            record: dict = {
                "id": e.id,
                "modality": e.modality,
                "closed": bool(e.closed),
                "modes": {},
            }
            for mode_name, mode_spec in sorted(e.modes.items()):
                mode_info: dict = {
                    "supports": sorted(mode_spec.supports),
                    "requires": sorted(mode_spec.requires),
                    "backends": {},
                }
                for bk_name, bk_spec in sorted(mode_spec.backends.items()):
                    mode_info["backends"][bk_name] = {
                        "template": bk_spec.template or None,
                        "endpoint": bk_spec.endpoint or None,
                        "param_map": dict(sorted(bk_spec.param_map.items())),
                    }
                record["modes"][mode_name] = mode_info
            output.append(record)
        json.dump(output, sys.stdout, indent=2)
        print()
        return 0

    # Table output
    _print_list_table(entries)
    return 0


def _print_list_table(entries: list) -> None:
    """Print a human-readable table of registered models."""
    # Compute mode-backend indicators per model
    def _mode_flags(entry) -> dict[str, str]:
        flags: dict[str, str] = {}
        for mode_name, mode_spec in sorted(entry.modes.items()):
            parts: list[str] = []
            if "local" in mode_spec.backends:
                parts.append("L")
            if "cloud" in mode_spec.backends:
                parts.append("C")
            flags[mode_name] = "".join(parts) if parts else "-"
        return flags

    # Gather all mode names across entries
    all_modes: list[str] = []
    seen_modes: set[str] = set()
    for e in entries:
        for mn in sorted(e.modes):
            if mn not in seen_modes:
                seen_modes.add(mn)
                all_modes.append(mn)

    # Column widths
    id_width = max(max(len(e.id) for e in entries), 22) if entries else 22
    mode_col_width = 10  # "t2i:LC" fits in 10

    # Header
    header = f"{'ID':<{id_width}} {'MODALITY':<10}"
    for mn in all_modes:
        header += f" {mn.upper():<{mode_col_width}}"
    if any(e.closed for e in entries):
        header += " CLOSED"
    print(header)
    print("-" * len(header))

    # Rows
    for e in entries:
        flags = _mode_flags(e)
        row = f"{e.id:<{id_width}} {e.modality:<10}"
        for mn in all_modes:
            indicator = flags.get(mn, "-")
            cell = f"{mn}:{indicator}" if indicator != "-" else "-"
            row += f" {cell:<{mode_col_width}}"
        if any(ec.closed for ec in entries):
            row += f" {'yes' if e.closed else 'no':>6}"
        print(row)


# ------------------------------------------------------------------
# _cmd_show
# ------------------------------------------------------------------


def _cmd_show(args: argparse.Namespace) -> int:
    """``astrid models show <model-id>`` — print per-model details."""
    try:
        registry = ModelRegistry.load_default()
    except Exception as exc:
        raise AstridError(
            f"failed to load model registry: {exc}",
            recovery_command=f"astrid models show {args.model_id}",
            state_snapshot={"command": "models show", "model_id": args.model_id},
        ) from exc

    try:
        entry = registry.get(args.model_id)
    except KeyError as exc:
        raise AstridError(
            str(exc),
            recovery_command="astrid models list",
            state_snapshot={"command": "models show", "model_id": args.model_id},
        ) from exc

    if args.use_json:
        _show_json(entry)
    else:
        _show_text(entry)
    return 0


def _show_json(entry) -> None:
    """Emit a single model entry as JSON."""
    record: dict = {
        "id": entry.id,
        "modality": entry.modality,
        "closed": bool(entry.closed),
        "modes": {},
    }
    for mode_name, mode_spec in sorted(entry.modes.items()):
        mode_info: dict = {
            "supports": sorted(mode_spec.supports),
            "requires": sorted(mode_spec.requires),
            "backends": {},
        }
        for bk_name, bk_spec in sorted(mode_spec.backends.items()):
            mode_info["backends"][bk_name] = {
                "template": bk_spec.template or None,
                "template_hash": bk_spec.template_hash or None,
                "endpoint": bk_spec.endpoint or None,
                "param_map": dict(sorted(bk_spec.param_map.items())),
            }
        record["modes"][mode_name] = mode_info
    json.dump(record, sys.stdout, indent=2)
    print()


def _show_text(entry) -> None:
    """Print a human-readable model detail view."""
    print(f"Model:      {entry.id}")
    print(f"Modality:   {entry.modality}")
    print(f"Closed:     {'yes' if entry.closed else 'no'}")
    print()

    for mode_name, mode_spec in sorted(entry.modes.items()):
        print(f"  [{mode_name}]")
        print(f"    Supports:  {', '.join(sorted(mode_spec.supports))}")
        if mode_spec.requires:
            print(f"    Requires:  {', '.join(sorted(mode_spec.requires))}")
        else:
            print("    Requires:  (none)")

        for bk_name, bk_spec in sorted(mode_spec.backends.items()):
            print(f"    Backend: {bk_name}")
            if bk_spec.template:
                print(f"      Template:      {bk_spec.template}")
                if bk_spec.template_hash:
                    print(f"      Template hash: {bk_spec.template_hash}")
            if bk_spec.endpoint:
                print(f"      Endpoint:      {bk_spec.endpoint}")
            if bk_spec.param_map:
                print("      Param map:")
                for pk, pv in sorted(bk_spec.param_map.items()):
                    print(f"        {pk} → {pv}")
            else:
                print("      Param map: (none)")
        print()
