#!/usr/bin/env python3
"""Astrid top-level command gateway.

The gateway dispatches to exactly seven families: the five product families
(``projects``, ``timelines``, ``media``, ``tasks``, ``runs``) plus the three
operational families (``doctor``, ``backup``). ``--help``/``-h``
and ``help`` print documentation (help is documentation and never requires a
session); ``--version`` prints the version. Everything else is dispatched to
one of the seven family handlers.

The settled unbound allowlist is recorded in
``SPRINT1_UNBOUND_ALLOWLIST_CONTRACT`` below: ``doctor`` and
``backup`` are operational families that must run before any session exists,
and ``help``/``--version`` are documentation.
"""

from __future__ import annotations

import sys

from astrid.core.contracts.errors import (
    AstridError,
    render_astrid_error,
    wrap_degraded_error,
)
from astrid.core.gateway.dispatch import (
    _TOP_LEVEL_HANDLERS,
    _build_dispatch_parser,
    _dispatch_backup,
    _dispatch_doctor,
    _dispatch_product,
    _top_level_commands,
)
from astrid.core.gateway.help import (
    _packs_subcommand_list,
    _print_entrypoint_help,
    _print_product_help,
    _product_help_text,
)

from . import dispatch as _gateway_dispatch


# Canonical accepted unbound contract for the seven-family gateway. Only the
# two operational families (which must run before any session exists) and
# help/version documentation are sessionless; everything else dispatches to a
# family handler.
SPRINT1_UNBOUND_ALLOWLIST_CONTRACT: tuple[tuple[str, ...], ...] = (
    ("-h",),
    ("--help",),
    ("help",),
    ("--version",),
    ("doctor",),
    ("backup",),
)


def main(argv: list[str] | None = None) -> int:
    raw = sys.argv[1:] if argv is None else list(argv)
    try:
        return _main_impl(raw)
    except AstridError as exc:
        return render_astrid_error(exc)
    except Exception as exc:  # noqa: BLE001
        bug = wrap_degraded_error(
            exc,
            state_snapshot={"argv": raw, "entrypoint": "astrid.core.gateway.main"},
        )
        return render_astrid_error(bug)


def _main_impl(raw: list[str]) -> int:
    first_arg = next(iter(raw), None)
    if first_arg in {"-h", "--help"}:
        _print_entrypoint_help()
        return 0
    # `astrid help` is the product-focused executable help (m4 plan step
    # 24, task T26): the seven families, nested mounts, the --json envelope
    # convention, and stable exit codes. It is session-free by construction
    # (help is documentation).
    if first_arg == "help":
        _print_product_help()
        return 0
    if first_arg == "--version":
        print("astrid")
        return 0
    return _dispatch(raw)


def _dispatch(raw: list[str]) -> int:
    return _gateway_dispatch._dispatch(raw)


if __name__ == "__main__":
    raise SystemExit(main())
