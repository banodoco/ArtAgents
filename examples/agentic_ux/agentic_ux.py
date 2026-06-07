#!/usr/bin/env python3
"""External example: full Astrid SDK loop (discover → inspect → invoke → read-events).

This script demonstrates the public SDK surface from an external application.
It imports only ``astrid`` plus standard-library modules, performs a complete
capability lifecycle against the canonical ``editorial.arrange`` executor, and
prints a deterministic JSON summary to stdout.

Usage::

    python examples/agentic_ux/agentic_ux.py \
        --projects-root /tmp/astrid-demo-projects \
        --capability-id editorial.arrange

The committed golden events fixture (≤3 JSONL records) is copied into a
temporary project layout so that ``astrid.read_events()`` can observe it
without needing a live executor run.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# The public SDK's invoke() path for built-in executors (e.g. editorial.arrange)
# may import pack runtime modules that carry a guard against direct invocation.
# Setting ASTRID_INTERNAL_INVOCATION tells the guard "this is a legitimate
# programmatic SDK call" and prevents a spurious SystemExit(2).
os.environ.setdefault("ASTRID_INTERNAL_INVOCATION", "1")

import astrid

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
GOLDEN_EVENTS = FIXTURE_DIR / "golden_events.jsonl"

PROJECT_SLUG = "demo-agentic-ux"
RUN_ID = "demo-run-001"


def _build_summary(
    *,
    discovery: astrid.DiscoveryResult,
    capability: astrid.Capability,
    invocation: astrid.InvocationResult,
    events: tuple[astrid.EventStreamRecord, ...],
) -> dict[str, Any]:
    """Build a deterministic JSON-safe summary dict from the SDK results."""

    return {
        "discovery": {
            "executor_count": len(discovery.executors),
            "orchestrator_count": len(discovery.orchestrators),
            "element_count": len(discovery.elements),
            "total_capabilities": len(discovery.capabilities),
        },
        "inspection": {
            "id": capability.id,
            "capability_type": capability.capability_type,
            "native_kind": capability.native_kind,
            "inputs": [
                {"name": p.name, "type": p.type, "required": p.required}
                for p in capability.inputs
            ],
            "outputs": [
                {"name": o.name, "type": o.type} for o in capability.outputs
            ],
        },
        "invocation": {
            "capability_id": invocation.capability_id,
            "capability_type": invocation.capability_type,
            "native_kind": invocation.native_kind,
            "ok": invocation.ok,
            "dry_run": invocation.raw_result.get("dry_run", False),
        },
        "events": {
            "count": len(events),
            "kinds": [e.kind for e in events],
        },
    }


def _setup_temp_project(projects_root: Path) -> Path:
    """Create a minimal project run directory with the golden events fixture."""

    run_dir = projects_root / PROJECT_SLUG / "runs" / RUN_ID
    run_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(GOLDEN_EVENTS, run_dir / "events.jsonl")
    return run_dir


def _port_to_dict(port: astrid.Port) -> dict[str, Any]:
    return {
        "name": port.name,
        "type": port.type,
        "required": port.required,
        "description": port.description,
        "default": port.default,
        "placeholder": port.placeholder,
    }


def _output_to_dict(output: astrid.Output) -> dict[str, Any]:
    return {
        "name": output.name,
        "type": output.type,
        "mode": output.mode,
        "description": output.description,
        "placeholder": output.placeholder,
        "path_template": output.path_template,
        "extension": output.extension,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Astrid SDK external example: discover → inspect → invoke → read-events"
    )
    parser.add_argument(
        "--projects-root",
        required=True,
        type=Path,
        help="Base directory for temporary project structure (e.g., /tmp/astrid-demo-projects)",
    )
    parser.add_argument(
        "--capability-id",
        default="editorial.arrange",
        help="Qualified capability ID to inspect and dry-run invoke (default: %(default)s)",
    )
    args = parser.parse_args()

    projects_root: Path = args.projects_root
    capability_id: str = args.capability_id

    # ── 1. Discover ──────────────────────────────────────────────────────
    discovery = astrid.discover(include_installed=False)

    # ── 2. Inspect ───────────────────────────────────────────────────────
    capability = astrid.get_capability(
        capability_id,
        kind="executor",
        include_installed=False,
    )

    # ── 3. Dry-run invoke ────────────────────────────────────────────────
    with tempfile.TemporaryDirectory(prefix="astrid-agentic-ux-") as tmp_out:
        invocation = astrid.invoke(
            capability_id,
            kind="executor",
            include_installed=False,
            out=Path(tmp_out),
            inputs={
                "brief": "example brief for agentic UX demo",
                "pool": "default",
                "theme": "default",
                "target_duration": 60,
            },
            dry_run=True,
            verbose=False,
        )

    # ── 4. Read events from the committed golden fixture ─────────────────
    _setup_temp_project(projects_root)

    events = astrid.read_events(
        PROJECT_SLUG,
        RUN_ID,
        projects_root=projects_root,
        verify=True,
    )

    # ── 5. Print deterministic JSON summary ──────────────────────────────
    summary = _build_summary(
        discovery=discovery,
        capability=capability,
        invocation=invocation,
        events=events,
    )
    json.dump(summary, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
