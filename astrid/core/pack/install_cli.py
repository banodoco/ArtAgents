"""``packs install`` CLI wrapper functions.

Parsed-args-to-orchestration adapters that bridge the pack CLI parser
(``astrid.core.pack.cli``) and the focused install modules
(``install_local``, ``install_git``, ``install_trust``).

Extracted from ``install.py`` during M4 T24 so that ``install.py`` can be
a pure facade that re-exports names from every focused install module.

.. note::

    The ``_run_*`` functions use **late imports** from
    ``astrid.core.pack.install`` (via ``.install``) so that
    ``mock.patch("astrid.packs.install.install_pack")`` still intercepts
    the call through the ``sys.modules`` compatibility shim.  Module-level
    imports from ``install_local`` would capture the real function object
    before the mock can replace it.
"""
from __future__ import annotations

__all__ = [
    "_run_install_command",
    "_run_rollback_command",
    "_run_uninstall_command",
    "_run_update_command",
    "cmd_install",
    "cmd_rollback",
    "cmd_uninstall",
    "cmd_update",
]

import sys
from pathlib import Path

# _is_git_url is a pure predicate (never mocked in tests) and is safe to
# import at module level.  Keeping it here avoids an extra late import in
# _run_install_command which is already the hottest CLI path.
from astrid.core.pack.install_git import _is_git_url  # noqa: E402


# ── Parsed-args entry points ────────────────────────────────────────────────


def _run_install_command(args) -> int:
    """Execute the parsed ``packs install`` command."""
    # Late import so mock.patch("astrid.packs.install.install_pack") works.
    from astrid.core.pack.install import install_pack  # noqa: E402

    if _is_git_url(args.source):
        return install_pack(
            args.source,
            dry_run=bool(args.dry_run),
            skip_confirm=bool(args.yes),
            trust_acknowledged=bool(getattr(args, "trust", False)),
            trust_method="cli_flag" if bool(getattr(args, "trust", False)) else None,
            trust_actor="cli" if bool(getattr(args, "trust", False)) else None,
            force=bool(args.force),
        )

    source = Path(args.source).expanduser()
    if not source.is_dir():
        print(
            f"install: {args.source} is not a directory or does not exist",
            file=sys.stderr,
        )
        return 2

    return install_pack(
        source,
        dry_run=bool(args.dry_run),
        skip_confirm=bool(args.yes),
        trust_acknowledged=bool(getattr(args, "trust", False)),
        trust_method="cli_flag" if bool(getattr(args, "trust", False)) else None,
        trust_actor="cli" if bool(getattr(args, "trust", False)) else None,
        force=bool(args.force),
    )


def _run_update_command(args) -> int:
    """Execute the parsed ``packs update`` command."""
    # Late import so mock.patch("astrid.packs.install.update_pack") works.
    from astrid.core.pack.install import update_pack  # noqa: E402

    return update_pack(
        args.pack_id,
        dry_run=bool(args.dry_run),
        skip_confirm=bool(args.yes),
        trust_acknowledged=bool(getattr(args, "trust", False)),
        trust_method="cli_flag" if bool(getattr(args, "trust", False)) else None,
        trust_actor="cli" if bool(getattr(args, "trust", False)) else None,
    )


def _run_uninstall_command(args) -> int:
    """Execute the parsed ``packs uninstall`` command."""
    # Late import so mock.patch("astrid.packs.install.uninstall_pack") works.
    from astrid.core.pack.install import uninstall_pack  # noqa: E402

    return uninstall_pack(
        args.pack_id,
        keep_revisions=bool(args.keep_revisions),
        skip_confirm=bool(args.yes),
    )


def _run_rollback_command(args) -> int:
    """Execute the parsed ``packs rollback`` command."""
    # Late import so mock.patch("astrid.packs.install.rollback_pack") works.
    from astrid.core.pack.install import rollback_pack  # noqa: E402

    return rollback_pack(
        args.pack_id,
        revision=args.revision,
        skip_confirm=bool(args.yes),
    )


# ── CLI handler wrappers (argparse) ─────────────────────────────────────────


def cmd_install(argv: list[str]) -> int:
    """``packs install`` CLI handler."""
    import argparse as _argparse

    parser = _argparse.ArgumentParser(
        prog="python3 -m astrid packs install",
        description="Install a pack from a local directory or Git URL.",
    )
    parser.add_argument(
        "source",
        help="Path to the pack source directory or a Git URL "
        "(https://..., git@..., ssh://..., git://...).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print trust summary without installing.",
    )
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip confirmation prompt.",
    )
    parser.add_argument(
        "--trust",
        action="store_true",
        help="Acknowledge the pack trust summary for noninteractive installs.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing install (preserve old revision).",
    )
    args = parser.parse_args(argv)
    return _run_install_command(args)


def cmd_update(argv: list[str]) -> int:
    """``packs update`` CLI handler."""
    import argparse as _argparse

    parser = _argparse.ArgumentParser(
        prog="python3 -m astrid packs update",
        description="Update an installed pack from its source.",
    )
    parser.add_argument(
        "pack_id",
        help="Pack identifier to update.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print diff summary without updating.",
    )
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip confirmation prompt.",
    )
    parser.add_argument(
        "--trust",
        action="store_true",
        help="Acknowledge the pack trust summary for noninteractive updates.",
    )
    args = parser.parse_args(argv)
    return _run_update_command(args)


def cmd_uninstall(argv: list[str]) -> int:
    """``packs uninstall`` CLI handler."""
    import argparse as _argparse

    parser = _argparse.ArgumentParser(
        prog="python3 -m astrid packs uninstall",
        description="Uninstall an installed pack.",
    )
    parser.add_argument(
        "pack_id",
        help="Pack identifier to uninstall.",
    )
    parser.add_argument(
        "--keep-revisions",
        action="store_true",
        help="Keep revision directories on disk.",
    )
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip confirmation prompt.",
    )
    args = parser.parse_args(argv)
    return _run_uninstall_command(args)


def cmd_rollback(argv: list[str]) -> int:
    """``packs rollback`` CLI handler."""
    import argparse as _argparse

    parser = _argparse.ArgumentParser(
        prog="python3 -m astrid packs rollback",
        description="Rollback an installed pack to a previous revision.",
    )
    parser.add_argument(
        "pack_id",
        help="Pack identifier to rollback.",
    )
    parser.add_argument(
        "--revision",
        help="Specific revision directory name to activate. "
        "If omitted, shows an interactive numbered list.",
    )
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip confirmation prompt.",
    )
    args = parser.parse_args(argv)
    return _run_rollback_command(args)
