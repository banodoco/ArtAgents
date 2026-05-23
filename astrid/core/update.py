"""Deterministic update-check and update-apply for forked capabilities.

Compares a local fork against its upstream (the original capability it was
forked from) and flags safety, cost, and permission escalations.  No real
LLM calls, no network calls — purely metadata comparison.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import replace
from pathlib import Path
from typing import Any


def update_check(
    capability_id: str,
    registry: Any,
    *,
    capability_type: str = "executor",
    capability_kind: str | None = None,
) -> dict[str, Any]:
    """Compare a locally-forked capability against its upstream.

    Returns an auditable report dict with keys:

    * ``capability_id``
    * ``forked_from``
    * ``upstream_version``
    * ``local_version``
    * ``metadata_diff`` — dict of ``field → (upstream_value, local_value)``
    * ``safety_escalations`` — list of human-readable escalation strings
    * ``cost_escalations``
    * ``permission_escalations``
    * ``recommendation`` — ``"safe_to_update"``, ``"review_required"``, or
      ``"blocked"``
    * ``report`` — human-readable multi-line string
    """
    # Resolve the local (forked) definition.
    local_def = _registry_get(registry, capability_id, capability_type, capability_kind)

    forked_from = str(local_def.metadata.get("forked_from") or "")
    if not forked_from:
        return {
            "capability_id": capability_id,
            "error": "not_forked",
            "report": f"{capability_id} was not forked — nothing to update against.",
        }

    # Resolve the upstream definition.
    try:
        upstream_def = _registry_get(
            registry, forked_from, capability_type, capability_kind
        )
    except (KeyError, ValueError) as exc:
        return {
            "capability_id": capability_id,
            "forked_from": forked_from,
            "error": "upstream_not_found",
            "detail": str(exc),
            "report": (
                f"Upstream {forked_from!r} not found in the registry. "
                f"It may have been removed or renamed."
            ),
        }

    local_version = str(local_def.metadata.get("version") or getattr(local_def, "version", ""))
    upstream_version = str(upstream_def.metadata.get("version") or getattr(upstream_def, "version", ""))

    # Diff metadata fields.
    diff_fields = ("version", "description", "short_description", "keywords")
    metadata_diff: dict[str, tuple[Any, Any]] = {}
    for field in diff_fields:
        local_val = getattr(local_def, field, None)
        upstream_val = getattr(upstream_def, field, None)
        if _normalize(local_val) != _normalize(upstream_val):
            metadata_diff[field] = (upstream_val, local_val)

    # Diff inputs/outputs (count + names).
    local_inputs = _port_names(getattr(local_def, "inputs", ()))
    upstream_inputs = _port_names(getattr(upstream_def, "inputs", ()))
    if local_inputs != upstream_inputs:
        metadata_diff["inputs"] = (sorted(upstream_inputs), sorted(local_inputs))

    local_outputs = _port_names(getattr(local_def, "outputs", ()))
    upstream_outputs = _port_names(getattr(upstream_def, "outputs", ()))
    if local_outputs != upstream_outputs:
        metadata_diff["outputs"] = (sorted(upstream_outputs), sorted(local_outputs))

    # Diff isolation metadata.
    local_iso = getattr(local_def, "isolation", None)
    upstream_iso = getattr(upstream_def, "isolation", None)
    if local_iso is not None and upstream_iso is not None:
        if getattr(local_iso, "mode", None) != getattr(upstream_iso, "mode", None):
            metadata_diff["isolation.mode"] = (
                getattr(upstream_iso, "mode", None),
                getattr(local_iso, "mode", None),
            )
        if getattr(local_iso, "network", None) != getattr(upstream_iso, "network", None):
            metadata_diff["isolation.network"] = (
                getattr(upstream_iso, "network", None),
                getattr(local_iso, "network", None),
            )
        local_bins = set(getattr(local_iso, "binaries", ()))
        upstream_bins = set(getattr(upstream_iso, "binaries", ()))
        if local_bins != upstream_bins:
            metadata_diff["isolation.binaries"] = (
                sorted(upstream_bins),
                sorted(local_bins),
            )

    # Detect safety escalations.
    safety_escalations: list[str] = []
    if local_iso is not None and upstream_iso is not None:
        was_network = bool(getattr(upstream_iso, "network", False))
        now_network = bool(getattr(local_iso, "network", False))
        if not was_network and now_network:
            safety_escalations.append(
                "network: changed from false to true — "
                "local fork introduces network access"
            )

        upstream_new_bins = set(getattr(upstream_iso, "binaries", ())) - set(
            getattr(local_iso, "binaries", ())
        )
        if upstream_new_bins:
            safety_escalations.append(
                f"new required binaries in upstream: {', '.join(sorted(upstream_new_bins))}"
            )

    # Detect permission/cost escalations from metadata.
    cost_escalations: list[str] = []
    permission_escalations: list[str] = []

    local_safety = getattr(local_def, "safety", None)
    upstream_safety = getattr(upstream_def, "safety", None)
    if local_safety is not None and upstream_safety is not None:
        local_secrets = set(getattr(local_safety, "secrets_required", ()))
        upstream_secrets = set(getattr(upstream_safety, "secrets_required", ()))
        new_secrets = upstream_secrets - local_secrets
        if new_secrets:
            safety_escalations.append(
                f"new secrets_required in upstream: {', '.join(sorted(new_secrets))}"
            )

        local_perms = set(getattr(local_safety, "permissions", ()))
        upstream_perms = set(getattr(upstream_safety, "permissions", ()))
        new_perms = upstream_perms - local_perms
        if new_perms:
            permission_escalations.append(
                f"new permissions in upstream: {', '.join(sorted(new_perms))}"
            )

        local_cost = str(getattr(local_safety, "cost_estimate", "") or "")
        upstream_cost = str(getattr(upstream_safety, "cost_estimate", "") or "")
        if upstream_cost != local_cost:
            cost_escalations.append(
                f"cost_estimate changed: {local_cost!r} → {upstream_cost!r}"
            )

    # Determine recommendation.
    if safety_escalations:
        recommendation = "blocked"
    elif permission_escalations:
        recommendation = "review_required"
    elif metadata_diff:
        recommendation = "safe_to_update"
    elif local_version != upstream_version:
        recommendation = "safe_to_update"
    else:
        recommendation = "up_to_date"

    # Build report.
    lines: list[str] = [
        f"update check: {capability_id}",
        f"  forked from: {forked_from}",
        f"  local version:  {local_version}",
        f"  upstream version: {upstream_version}",
    ]
    if metadata_diff:
        lines.append(f"  metadata changes ({len(metadata_diff)}):")
        for field, (old, new) in sorted(metadata_diff.items()):
            lines.append(f"    {field}: {_truncate(old)} → {_truncate(new)}")
    if safety_escalations:
        lines.append(f"  ⚠ safety escalations ({len(safety_escalations)}):")
        for esc in safety_escalations:
            lines.append(f"    - {esc}")
    if cost_escalations:
        lines.append(f"  💰 cost escalations ({len(cost_escalations)}):")
        for esc in cost_escalations:
            lines.append(f"    - {esc}")
    if permission_escalations:
        lines.append(f"  🔐 permission escalations ({len(permission_escalations)}):")
        for esc in permission_escalations:
            lines.append(f"    - {esc}")
    lines.append(f"  recommendation: {recommendation}")

    return {
        "capability_id": capability_id,
        "forked_from": forked_from,
        "upstream_version": upstream_version,
        "local_version": local_version,
        "metadata_diff": {
            k: (str(v[0]) if v[0] is not None else None, str(v[1]) if v[1] is not None else None)
            for k, v in metadata_diff.items()
        },
        "safety_escalations": safety_escalations,
        "cost_escalations": cost_escalations,
        "permission_escalations": permission_escalations,
        "recommendation": recommendation,
        "report": "\n".join(lines),
    }


def update_apply(
    capability_id: str,
    registry: Any,
    *,
    force: bool = False,
    skip_safety: bool = False,
    capability_type: str = "executor",
    capability_kind: str | None = None,
) -> dict[str, Any]:
    """Apply an upstream update to a locally-forked capability.

    Copies the upstream capability's content root into the local fork
    directory, preserving ``.astrid_fork_state.json`` and any local
    override files.  Writes ``.astrid_update_report.json`` into the
    capability root afterwards.

    Returns the same report dict as ``update_check()`` with additional
    keys: ``applied`` (bool), ``report_path`` (str).
    """
    check_result = update_check(
        capability_id,
        registry,
        capability_type=capability_type,
        capability_kind=capability_kind,
    )

    if check_result.get("error"):
        check_result["applied"] = False
        check_result["report_path"] = ""
        return check_result

    if check_result.get("recommendation") == "up_to_date":
        check_result["applied"] = False
        check_result["report_path"] = ""
        return check_result

    if not force and check_result.get("recommendation") == "blocked":
        check_result["applied"] = False
        check_result["report_path"] = ""
        check_result["report"] += "\nupdate blocked: safety escalations detected. Use --force to override."
        return check_result

    if not skip_safety and check_result.get("safety_escalations"):
        check_result["applied"] = False
        check_result["report_path"] = ""
        check_result["report"] += (
            f"\nupdate blocked: {len(check_result['safety_escalations'])} safety "
            f"escalation(s). Use --skip-safety to override."
        )
        return check_result

    # Resolve definitions to find content roots.
    local_def = _registry_get(registry, capability_id, capability_type, capability_kind)
    forked_from = str(local_def.metadata.get("forked_from") or "")
    upstream_def = _registry_get(registry, forked_from, capability_type, capability_kind)

    local_root = _content_root(local_def)
    upstream_root = _content_root(upstream_def)

    # Guard: both roots must be real directories.
    if not local_root or not local_root.is_dir():
        check_result["applied"] = False
        check_result["report_path"] = ""
        check_result["error"] = "local_root_missing"
        check_result["report"] += f"\nupdate failed: local content root {local_root} not found."
        return check_result
    if not upstream_root or not upstream_root.is_dir():
        check_result["applied"] = False
        check_result["report_path"] = ""
        check_result["error"] = "upstream_root_missing"
        check_result["report"] += (
            f"\nupdate failed: upstream content root {upstream_root} not found."
        )
        return check_result

    # Apply: copy upstream content into local root (overwriting).
    _copy_upstream_content(local_root, upstream_root)

    # Write the update report.
    report_path = local_root / ".astrid_update_report.json"
    report_data = {
        "schema_version": 1,
        "capability_id": capability_id,
        "forked_from": forked_from,
        "upstream_version": check_result["upstream_version"],
        "local_version": check_result["local_version"],
        "applied_at": _now_iso(),
        "safety_escalations": check_result["safety_escalations"],
        "cost_escalations": check_result["cost_escalations"],
        "permission_escalations": check_result["permission_escalations"],
        "recommendation": check_result["recommendation"],
    }
    report_path.write_text(json.dumps(report_data, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    check_result["applied"] = True
    check_result["report_path"] = str(report_path)
    check_result["report"] += f"\nupdate applied. Report written to {report_path}"
    return check_result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _registry_get(
    registry: Any,
    capability_id: str,
    capability_type: str,
    capability_kind: str | None,
) -> Any:
    """Call ``registry.get(...)`` using the right signature per type."""
    if capability_type == "element":
        if capability_kind is None:
            raise ValueError("capability_kind is required for element lookups")
        return registry.get(capability_kind, capability_id)
    return registry.get(capability_id)


def _port_names(ports: tuple[Any, ...]) -> set[str]:
    """Extract ordered port names from a tuple of Port-like objects."""
    return {getattr(p, "name", str(p)) for p in ports}


def _normalize(value: Any) -> Any:
    """Normalize values for comparison (sort tuples, lowercase strings)."""
    if isinstance(value, tuple):
        return tuple(sorted(str(v) for v in value))
    if isinstance(value, list):
        return tuple(sorted(str(v) for v in value))
    if isinstance(value, str):
        return value.strip()
    return value


def _truncate(value: Any, max_len: int = 80) -> str:
    """Truncate a stringified value for display."""
    s = str(value)
    if len(s) <= max_len:
        return s
    return s[: max_len - 3] + "..."


def _content_root(definition: Any) -> Path | None:
    """Extract the content root from a capability definition."""
    metadata = getattr(definition, "metadata", {}) or {}
    root_str = metadata.get("content_root")
    if root_str:
        return Path(root_str)
    # Fallback: some definitions have a `root` attribute.
    raw_root = getattr(definition, "root", None)
    if raw_root is not None:
        return Path(raw_root) if not isinstance(raw_root, Path) else raw_root
    return None


def _copy_upstream_content(local_root: Path, upstream_root: Path) -> None:
    """Copy upstream files into local_root, preserving fork state."""
    # Preserve .astrid_fork_state.json.
    fork_state_path = local_root / ".astrid_fork_state.json"
    saved_fork_state: bytes | None = None
    if fork_state_path.is_file():
        saved_fork_state = fork_state_path.read_bytes()

    # Preserve .overrides.json if it happens to live here.
    overrides_path = local_root / ".overrides.json"
    saved_overrides: bytes | None = None
    if overrides_path.is_file():
        saved_overrides = overrides_path.read_bytes()

    # Copy upstream files into local root.
    for item in sorted(upstream_root.iterdir()):
        src = upstream_root / item.name
        dst = local_root / item.name
        if src.is_dir():
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)

    # Restore preserved local state.
    if saved_fork_state is not None:
        fork_state_path.write_bytes(saved_fork_state)
    if saved_overrides is not None:
        overrides_path.write_bytes(saved_overrides)


def _now_iso() -> str:
    """Return an ISO-8601 timestamp string."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "update_check",
    "update_apply",
]
