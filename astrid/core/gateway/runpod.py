"""Handlers for ``astrid runpod {sweep,volumes,ensure-storage}`` sub-verbs."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any, Literal

from astrid.core.contracts.errors import AstridError
from astrid.core.project.paths import resolve_projects_root


def dispatch_runpod(args: list[str]) -> int:
    """Dispatch ``astrid runpod {sweep,volumes,ensure-storage} ...`` sub-verbs."""
    parser = argparse.ArgumentParser(prog="astrid runpod")
    sub = parser.add_subparsers(dest="command", required=True)
    sweep = sub.add_parser("sweep")
    sweep.add_argument("--hard", action="store_true")
    sweep.add_argument("--dry-run", action="store_true")
    sweep.add_argument("--projects-root")
    sweep.set_defaults(handler=dispatch_runpod_sweep)
    sub.add_parser("volumes").set_defaults(handler=dispatch_runpod_volumes)
    ensure = sub.add_parser("ensure-storage")
    ensure.set_defaults(handler=dispatch_runpod_ensure_storage)
    parsed, tail = parser.parse_known_args(args)
    return int(parsed.handler(parsed, tail))


def dispatch_runpod_sweep(parsed: Any, _tail: list[str]) -> int:
    from astrid.core.integrations.runpod.sweeper import sweep as run_sweep

    mode: Literal["default", "hard"] = "hard" if parsed.hard else "default"
    projects_root = (
        Path(parsed.projects_root) if parsed.projects_root else resolve_projects_root()
    )
    summary = run_sweep(projects_root, mode=mode, dry_run=parsed.dry_run)
    print(json.dumps(summary, indent=2, default=str))
    return 0


def dispatch_runpod_volumes(_parsed: Any, args: list[str]) -> int:
    """Dispatch ``astrid runpod volumes ls``."""
    parser = argparse.ArgumentParser(prog="astrid runpod volumes")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("ls", help="List RunPod network volumes as JSON.")
    try:
        parsed = parser.parse_args(args)
    except SystemExit:
        return 2
    if parsed.command != "ls":
        raise AstridError(
            "usage: astrid runpod volumes ls",
            recovery_command="astrid runpod volumes ls",
            state_snapshot={"command": "runpod volumes"},
        )

    from astrid.core.integrations.runpod.storage import list_volumes

    try:

        async def _volumes_ls() -> None:
            volumes = await list_volumes()
            print(json.dumps(volumes, indent=2, default=str))

        asyncio.run(_volumes_ls())
        return 0
    except Exception as exc:
        raise AstridError(
            f"runpod volumes ls failed: {exc}",
            recovery_command="astrid runpod volumes ls",
            state_snapshot={"command": "runpod volumes ls"},
        ) from exc


def dispatch_runpod_ensure_storage(_parsed: Any, args: list[str]) -> int:
    """Dispatch ``astrid runpod ensure-storage <name> [--size <GB>] [--datacenter <id>]``."""
    parser = argparse.ArgumentParser(prog="astrid runpod ensure-storage")
    parser.add_argument("name", help="Volume name to find or create.")
    parser.add_argument("--size", type=int, default=50, help="Size in GB for new volumes (default: 50).")
    parser.add_argument("--datacenter", "--datacenter-id", dest="datacenter_id", default=None, help="RunPod datacenter ID.")
    try:
        parsed = parser.parse_args(args)
    except SystemExit:
        return 2

    from astrid.core.integrations.runpod.storage import ensure_storage

    try:

        async def _ensure() -> None:
            result = await ensure_storage(
                parsed.name,
                size_gb=parsed.size,
                datacenter_id=parsed.datacenter_id,
            )
            print(json.dumps(result, indent=2, default=str))

        asyncio.run(_ensure())
        return 0
    except Exception as exc:
        raise AstridError(
            f"ensure-storage failed: {exc}",
            recovery_command="astrid runpod ensure-storage <name>",
            state_snapshot={"command": "runpod ensure-storage"},
        ) from exc
