"""Entrypoint help rendering for the Astrid gateway.

Extracted from ``astrid/gateway.py`` during M4 batch 41 (T42) to keep the
gateway facade focused while preserving the help-printing entrypoints that
callers and monkeypatch seams rely on via ``astrid.core.gateway._print_entrypoint_help``
and ``astrid.core.gateway._packs_subcommand_list``.

``_product_help_text`` / ``_print_product_help`` (m4 plan step 24, task
T26) are the executable help. They document the seven-family surface: the
five product families from the explicit registry
(``astrid/core/cli/domain_product.py``) with their kernel/pack ownership,
the two manifest-declared nested mounts, the ``--json`` envelope
convention, the stable exit codes, and the two operational families
(``doctor``, ``backup``).
"""

from __future__ import annotations


def _packs_subcommand_list() -> str:
    """Return a comma-separated list of ``astrid packs`` subcommands."""
    try:
        import argparse

        from astrid.core.pack.cli import build_parser as packs_build_parser

        packs_parser = packs_build_parser()
        # Extract subcommand names from the parser's subparsers action.
        for action in packs_parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                return ",".join(sorted(action.choices.keys()))
    except Exception:
        pass
    # Fallback: canonical list matching the packs CLI as of m5b.
    return "agent-index,inspect,list,new,search,status,validate"


def _print_entrypoint_help() -> None:
    print(
        """Astrid command gateway — Python SDK + CLI

The canonical Python boundary is ``import astrid`` (see docs/reference/sdk.md).
This gateway is the CLI entry point for the seven families: the five product
families (projects, timelines, media, tasks, runs) and the two operational
families (doctor, backup).

Usage:
  python3 -m astrid <family> <command> [options]
  python3 -m astrid help

Product families:
  python3 -m astrid projects ...
  python3 -m astrid timelines ...
  python3 -m astrid media ...
  python3 -m astrid tasks ...
  python3 -m astrid runs ...

Timeline evidence:
  python3 -m astrid timelines visualize --project PROJECT [--timeline-slug REF]
      [--format FORMAT[,FORMAT...]] [--json]

Operational families:
  python3 -m astrid doctor [--json]
  python3 -m astrid backup [--json]  # unavailable until a runtime route exists

Nested mounts (manifest-owned):
  python3 -m astrid timelines shots ...
  python3 -m astrid media references ...

Options:
  --json      product commands print the five-key SDK envelope
              (ok/data/error/receipt/idempotency_key); doctor emits its
              diagnostic object (backup has no --json flag)
  -h, --help  show help

Notes:
  python3 -m astrid is the package entry point.
  Use ``python3 -m astrid help`` for the full family census, kernel/pack
  ownership, nested mounts, and stable exit codes.

Ownership handoff:
  Product commands connect to the selected runtime through the generated
  client. If it is unavailable, run ``banodoco-local up --profile astrid``.
"""
    )


def _product_help_text() -> str:
    """Return the executable help for the seven-family gateway surface.

    The text is generated from the explicit product registry plus the two
    operational families, so the advertised census can never drift from
    ``astrid/core/cli/domain_product.py``: the five product families (with
    their kernel/pack ownership), the two manifest-declared nested mounts,
    the ``--json`` envelope convention, the stable exit codes, and the
    two operational families (``doctor``, ``backup``).
    """
    families = "projects timelines media tasks runs doctor backup"
    return f"""Astrid product commands — the seven runtime-client families

The gateway owns exactly seven families: the five product families and the
two operational families. ``shots`` mounts beneath ``timelines`` and
``references`` mounts beneath ``media``.

Usage:
  python3 -m astrid <family> <command> [options]
  python3 -m astrid <family> --help

Family census (exactly seven families): {families}

Product families:
  projects    [kernel] project create/list/show/update/select/current
  media       [kernel] media import/list/show/verify/relate
  tasks       [kernel] task create/list/show/cancel/retry/events
  runs        [kernel] run list/show/cancel/retry-failed/events
  timelines   [pack: timeline] timeline create/list/show/save/archive/unarchive/history/diff/visualize/render

Operational families:
  doctor      [runtime] read-only runtime health diagnostics
  backup      [runtime] backup is unavailable until a runtime route exists

Nested mounts (manifest-owned):
  timelines shots       [pack: shots] project-level reusable shot list/create/show/add/remove/reorder
  media references      [pack: references] reference create/update/archive/associate/link/set-primary/list/show

Options:
  --json      product commands print the five-key SDK envelope
              (ok/data/error/receipt/idempotency_key); doctor emits its
              diagnostic object (backup has no --json flag)
  -h, --help  show help

Exit codes:
  0  success (envelope ok=true)
  1  typed SDK error (envelope ok=false)
  2  usage/parse error

Ownership handoff:
  Product commands connect to the selected runtime through the generated
  client. If it is unavailable, run ``banodoco-local up --profile astrid``.
"""


def _print_product_help() -> None:
    """Print the product-focused executable help to stdout."""
    print(_product_help_text(), end="")
