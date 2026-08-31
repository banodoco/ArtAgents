#!/usr/bin/env python3
"""External example: the manifest-only Astrid SDK preview loop.

This script demonstrates the public SDK surface from an external application.
It imports only ``astrid`` plus standard-library modules, performs a complete
capability lifecycle against the canonical ``editorial.arrange`` executor, and
prints a deterministic JSON summary to stdout.  Live execution and event
observation require an explicitly opened runtime client; this no-side-effect
example deliberately does not fabricate a local project or event stream.

Usage::

    python examples/agentic_ux/agentic_ux.py \
        --capability-id editorial.arrange
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import astrid  # noqa: E402  (repo root is added above for direct script execution)


def _build_summary(
    *,
    discovery: astrid.DiscoveryResult,
    capability: astrid.Capability,
    invocation: astrid.InvocationResult,
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
    }


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
        description="Astrid SDK external example: discover → inspect → invoke preview"
    )
    parser.add_argument(
        "--capability-id",
        default="editorial.arrange",
        help="Qualified capability ID to inspect and dry-run invoke (default: %(default)s)",
    )
    args = parser.parse_args()

    capability_id: str = args.capability_id

    # ── 1. Discover ──────────────────────────────────────────────────────
    discovery = astrid.discover()

    # ── 2. Inspect ───────────────────────────────────────────────────────
    capability = astrid.get_capability(
        capability_id,
        kind="executor",
    )

    # ── 3. Dry-run invoke ────────────────────────────────────────────────
    invocation = astrid.invoke(
        capability_id,
        kind="executor",
        inputs={
            "brief": "example brief for agentic UX demo",
            "pool": "default",
            "theme": "default",
            "target_duration": 60,
        },
        dry_run=True,
        verbose=False,
    )

    # ── 4. Print deterministic JSON summary ───────────────────────────────
    summary = _build_summary(
        discovery=discovery,
        capability=capability,
        invocation=invocation,
    )
    json.dump(summary, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
