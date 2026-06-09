"""Shared leaf helpers for executor and orchestrator packages.

These were previously duplicated verbatim (or near-verbatim) in
``astrid.core.executor.{runner,cli}`` and ``astrid.core.orchestrator.{runner,cli}``.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# runner.py helpers
# ---------------------------------------------------------------------------

_PLACEHOLDER_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _has_value(value: Any) -> bool:
    return value is not None and value != ""


def _stringify_value(value: Any) -> str:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (list, tuple)):
        return ",".join(str(item) for item in value)
    return str(value)


# ---------------------------------------------------------------------------
# cli.py helpers
# ---------------------------------------------------------------------------


def _eprint(*args: object) -> None:
    """Shared stderr sink for command previews and legacy override diagnostics."""
    print(*args, file=sys.stderr)


def _gateway_resolved_project(explicit_project: str | None) -> str | None:
    if explicit_project is not None:
        return None
    from astrid.core.gateway import ASTRID_GATEWAY_RESOLVED_PROJECT_ENV

    value = sys.modules["os"].environ.get(ASTRID_GATEWAY_RESOLVED_PROJECT_ENV)
    return value or None


def _banodoco_config_from_args(
    args: argparse.Namespace,
    *,
    agent_flag: str = "banodoco_agent_executors",
):
    """Build a BanodocoCatalogConfig from CLI args and env.

    ``agent_flag`` is the arg attribute to check for per-capability-type
    override (``banodoco_agent_executors`` or ``banodoco_agent_orchestrators``).
    """
    from astrid.core.executor.banodoco_catalog import BanodocoCatalogConfig

    env_config = BanodocoCatalogConfig.from_env()
    enabled = bool(getattr(args, agent_flag, False) or env_config.enabled)
    return BanodocoCatalogConfig(
        enabled=enabled,
        catalog_url=args.banodoco_catalog_url or env_config.catalog_url,
        include_defaults=False if args.no_banodoco_defaults else env_config.include_defaults,
        include_mandatory=False if args.no_banodoco_mandatory else env_config.include_mandatory,
        cache_dir=Path(args.banodoco_cache_dir).expanduser() if args.banodoco_cache_dir else env_config.cache_dir,
        refresh=bool(args.banodoco_refresh or env_config.refresh),
        timeout_seconds=env_config.timeout_seconds,
    )


def _require_qualified_id(value: str, label: str) -> None:
    if "." not in value or any(not part for part in value.split(".")):
        raise ValueError(f"{label} must be qualified as <pack>.<name>")


def _aliases_text(resolver: Any, canonical_id: str) -> str:
    """Return a space-joined string of alias ids for *canonical_id*.

    Deprecated aliases get a ``[deprecated]`` suffix so the deprecation
    status is visible to search scoring and human-readable output.
    Returns the empty string when there are no aliases.
    """
    records = resolver.get_aliases_for(canonical_id)
    if not records:
        return ""
    parts: list[str] = []
    for r in records:
        part = r.alias
        if r.deprecated:
            part += " [deprecated]"
        if r.deprecation_message:
            part += " " + r.deprecation_message
        parts.append(part)
    return " ".join(parts)


def _example_path_for_port(port: Any) -> str:
    """Render a plausible ``<path>`` placeholder for an input port.

    Uses the port name as the filename so the example looks like a real
    invocation; the suffix is best-effort based on the port type (image →
    .png, video → .mp4, audio → .wav, text → .txt, otherwise no suffix).
    """
    type_to_ext = {
        "image": ".png",
        "video": ".mp4",
        "audio": ".wav",
        "text": ".txt",
        "json": ".json",
        "directory": "",
        "dir": "",
    }
    port_type = getattr(port, "type", None) or ""
    suffix = type_to_ext.get(str(port_type).lower(), "")
    return f"/path/to/{port.name}{suffix}"


def _format_invocation_hint(verb: str, qid: str, inputs: tuple[Any, ...]) -> str:
    parts = [f"astrid {verb} run {qid}"]
    required = [port for port in inputs if getattr(port, "required", False)]
    for port in required[:3]:
        flag = str(getattr(port, "name", "input")).replace("_", "-")
        parts.append(f"--{flag} <path>")
    if len(required) > 3:
        parts.append("...")
    return " ".join(parts)


def _print_invocation_example(verb: str, qid: str, inputs: tuple[Any, ...]) -> None:
    """Synthesize an example invocation for ``inspect`` output.

    ``verb`` is ``"executors"`` or ``"orchestrators"``.
    """
    print()
    print("Example:")
    parts = [f"  astrid {verb} run {qid}"]
    for port in inputs:
        if not getattr(port, "required", False):
            continue
        parts.append(f"--input {port.name}={_example_path_for_port(port)}")
    parts.append("--out /path/to/output")
    print(" ".join(parts))


def _print_ports(label: str, ports: tuple[Any, ...]) -> None:
    if not ports:
        return
    print(f"{label}:")
    for port in ports:
        required = "required" if port.required else "optional"
        print(f"  - {port.name} ({port.type}, {required})")
