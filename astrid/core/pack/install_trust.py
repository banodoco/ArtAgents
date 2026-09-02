"""Pack install trust-summary formatting and confirmation helpers.

Extracted from ``astrid.core.pack.install`` during M4 giant-file
decomposition.  Public names remain importable from ``install.py``
so that existing ``mock.patch`` seams on ``astrid.core.pack.install.*``
continue to work.
"""

from __future__ import annotations

import sys

from astrid.core.pack import _normalize_pack_permissions
from astrid.core.pack.validate import V1_TRUST_BLOCK

# ---------------------------------------------------------------------------
# Trust-block normalisation
# ---------------------------------------------------------------------------


def _trust_block(summary: dict) -> dict[str, object]:
    trust = summary.get("trust")
    payload = dict(V1_TRUST_BLOCK)
    if isinstance(trust, dict):
        for key in V1_TRUST_BLOCK:
            if key in trust:
                payload[key] = trust[key]
    return payload


def _normalized_summary_permissions(summary: dict) -> list[dict[str, object]]:
    raw = summary.get("permissions")
    if isinstance(raw, list):
        try:
            return [
                permission.to_dict()
                for permission in _normalize_pack_permissions(
                    raw, field="trust_summary.permissions"
                )
            ]
        except Exception:
            pass
    raw_ids = summary.get("permission_ids")
    if isinstance(raw_ids, list):
        return [{"id": str(value)} for value in raw_ids if value]
    return []


# ---------------------------------------------------------------------------
# Display formatting
# ---------------------------------------------------------------------------


def _format_permission(permission: dict[str, object]) -> str:
    label = str(permission.get("id", "?"))
    details: list[str] = []
    reason = permission.get("reason")
    if isinstance(reason, str) and reason.strip():
        details.append(reason.strip())
    access = permission.get("access")
    if isinstance(access, str) and access.strip():
        details.append(f"access={access.strip()}")
    services = permission.get("services")
    if isinstance(services, list):
        service_names = [
            str(service).strip() for service in services if str(service).strip()
        ]
        if service_names:
            details.append(f"services={', '.join(service_names)}")
    if not details:
        return label
    return f"{label}: {'; '.join(details)}"


def _format_trust_summary(
    summary: dict,
    *,
    git_url: str = "",
    commit_sha: str = "",
    astrid_version: str = "",
    trust_tier: str = "",
) -> str:
    """Format an extract_trust_summary dict for display.

    When *git_url* is non-empty the ``Source`` line shows the durable Git
    URL instead of ``summary['source_path']`` (which holds a temp path
    during Git installs).  *commit_sha* is displayed as the pinned
    revision (first 8 chars).  *astrid_version* and *trust_tier* are shown
    when non-empty.
    """
    lines: list[str] = []
    lines.append("━━━ Trust Summary ━━━")
    lines.append(f"  Pack ID:       {summary.get('pack_id', '?')}")
    lines.append(f"  Name:          {summary.get('name', '?')}")
    lines.append(f"  Version:       {summary.get('version', '?')}")
    lines.append(f"  Schema:        {summary.get('schema_version', '?')}")

    # For Git installs, show the durable git_url (not the temp checkout path)
    source_display = git_url if git_url else summary.get("source_path", "?")
    lines.append(f"  Source:        {source_display}")

    if commit_sha:
        lines.append(f"  Pinned Commit: {commit_sha[:8]}")

    if astrid_version:
        lines.append(f"  Astrid Ver:    {astrid_version}")

    if trust_tier:
        lines.append(f"  Trust Tier:    {trust_tier}")

    # Component counts
    counts = summary.get("component_counts", {})
    if counts:
        parts = []
        for k in ("executors", "orchestrators", "elements"):
            if counts.get(k, 0):
                parts.append(f"{counts[k]} {k}")
        if parts:
            lines.append(f"  Components:    {', '.join(parts)}")
        else:
            lines.append("  Components:    (none)")
    else:
        lines.append("  Components:    (none)")

    # Entrypoints
    entrypoints = summary.get("entrypoints", [])
    if entrypoints:
        lines.append(f"  Entrypoints:   {', '.join(entrypoints)}")

    # Declared secrets
    secrets = summary.get("secrets", [])
    if secrets:
        lines.append(f"  Secrets:       {', '.join(secrets)}")

    # Dependencies
    deps = summary.get("dependencies", [])
    if deps:
        lines.append(f"  Dependencies:  {', '.join(deps)}")

    # Docs
    docs = summary.get("docs", {})
    if docs:
        doc_parts = [f"{k}={v}" for k, v in docs.items() if v]
        if doc_parts:
            lines.append(f"  Docs:          {', '.join(doc_parts)}")

    permissions = _normalized_summary_permissions(summary)
    lines.append("  Permissions:")
    if permissions:
        for permission in permissions:
            lines.append(f"    - {_format_permission(permission)}")
    else:
        lines.append("    - none declared")

    trust = _trust_block(summary)
    lines.append("  Trust (v1):")
    lines.append(f"    - sandbox={trust['sandbox']}")
    lines.append(
        "    - runs_with_user_process_permissions="
        f"{str(bool(trust['runs_with_user_process_permissions'])).lower()}"
    )
    lines.append(
        "    - permission_enforcement="
        f"{trust['permission_enforcement']}"
    )
    lines.append("  Disclosure:")
    lines.append("    - Astrid does not sandbox installed packs.")
    lines.append("    - Permission declarations are disclosure-only and not enforced.")
    lines.append("    - Installed pack code runs with your user's process permissions.")

    # Warnings
    warnings = summary.get("warnings", [])
    if warnings:
        lines.append("  ⚠ Warnings:")
        for w in warnings:
            lines.append(f"    • {w}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Interactive confirmation
# ---------------------------------------------------------------------------


def _confirm(prompt: str, default_yes: bool = False) -> bool:
    """Ask the user for confirmation."""
    if default_yes:
        prompt += " [Y/n] "
    else:
        prompt += " [y/N] "
    try:
        response = input(prompt).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled.", file=sys.stderr)
        raise SystemExit(1)
    if default_yes:
        return response != "n"
    return response in ("y", "yes")


def _confirm_trust(pack_id: str, trust_summary: dict) -> bool:
    """Require an exact trust acknowledgement before installing code."""
    print(_format_trust_summary(trust_summary))
    print()
    expected = f"trust {pack_id}"
    try:
        response = input(
            f"Type {expected!r} to acknowledge this pack's trust summary: "
        ).strip()
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled.", file=sys.stderr)
        raise SystemExit(1)
    return response == expected


def _trust_missing_error(command: str, pack_id: str) -> None:
    print(
        f"{command}: trust acknowledgement required for pack {pack_id!r}. "
        f"Pass --trust for noninteractive use, or run interactively and type "
        f"'trust {pack_id}'. --yes only skips the ordinary confirmation prompt.",
        file=sys.stderr,
    )
