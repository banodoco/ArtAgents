""":mod:`astrid.core.pack.cli_inspect` — Pack inspect command handlers and helpers.

Extracted from ``astrid/core/pack/cli.py`` during M4 giant-file split.
Contains ``cmd_inspect``, ``_handle_inspect``, and all private helpers for
building and printing both full and agent-focused pack inspect output.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from astrid.core.pack import (
    BundledCatalog,
    CanonicalPackEntry,
    DEFAULT_PACKS_ROOT,
    ExternalPackSource,
    canonical_manifest_path,
    read_normalize_validate,
)
from astrid.core.pack.discovery import discover_canonical_packs_ordered
from astrid.core.pack._cli_shared import _print_taxonomy_block


def _canonical_resource_row(handle: Any) -> dict[str, Any]:
    """Serialize one already-confined canonical resource handle."""
    return {
        "path": handle.path,
        "kind": handle.kind,
        "file_kind": handle.file_kind,
        "size": handle.size,
        "sha256": handle.sha256,
        "resolved": str(handle.resolved),
    }


def _build_canonical_inspect(
    entry: CanonicalPackEntry,
    *,
    record: Any | None = None,
) -> dict[str, Any]:
    """Build stable inspect data exclusively from canonical projections."""
    definition = entry.definition
    normalized = definition.to_dict()
    capabilities = entry.capability_projection()
    documentation = entry.documentation_projection()
    resource_projection = entry.resource_projection()
    resource_rows = [
        _canonical_resource_row(item) for item in resource_projection.resources
    ]
    database_projection = entry.database_projection()
    database = None if database_projection is None else database_projection.database

    database_data: dict[str, Any] = {
        "owner": None,
        "owned": False,
        "default_enabled": False,
        "head": None,
        "depends_on": [],
        "migrations": [],
        "tables": [],
        "stream_types": [],
        "event_kinds": [],
        "command_kinds": [],
        "repositories": [],
        "conformance": [],
        "cli_mounts": {},
        "bridge_mounts": [],
    }
    if database is not None:
        database_data.update(
            {
                "owner": entry.id,
                "owned": True,
                "default_enabled": database.default_enabled,
                "head": database.migration_head,
                "depends_on": [
                    {"pack": item.pack, "min_migration": item.min_migration}
                    for item in database.depends_on
                ],
                "migrations": [
                    {
                        "version": item.version,
                        "name": item.name,
                        "path": item.path,
                        "tables": list(item.tables),
                    }
                    for item in database.migrations
                ],
                "tables": sorted(
                    {
                        table
                        for migration in database.migrations
                        for table in migration.tables
                    }
                ),
                "stream_types": list(database.stream_types),
                "event_kinds": list(database.event_kinds),
                "command_kinds": list(database.command_kinds),
                "repositories": list(database.repositories),
                "conformance": list(database.conformance),
                "cli_mounts": dict(database.cli_mounts),
                "bridge_mounts": list(database.bridge_mounts),
            }
        )

    trust = dict(getattr(record, "trust_summary", {}) or {}) if record is not None else {}
    component_counts = (
        dict(getattr(record, "component_inventory", {}) or {})
        if record is not None
        else {}
    )
    entrypoints = list(getattr(record, "entrypoints", ()) or ()) if record is not None else []
    declared_secrets = (
        list(getattr(record, "declared_secrets", ()) or ()) if record is not None else []
    )
    dependencies = list(getattr(record, "dependencies", ()) or ()) if record is not None else []
    status = (
        "active" if bool(getattr(record, "active", False)) else "inactive"
        if record is not None
        else definition.status
    )
    manifest_digest = (
        str(getattr(record, "manifest_digest", "") or "")
        if record is not None
        else entry.manifest.sha256
    )
    if not entrypoints:
        entrypoints = list(definition.agent.get("normal_entrypoints", ()))
    if not declared_secrets:
        declared_secrets = [
            item["name"] for item in definition.secrets if item.get("name")
        ]

    docs_data: dict[str, Any] | None = None
    if documentation.documentation is not None:
        doc = documentation.documentation
        docs_data = {
            "kind": doc.kind,
            "path": doc.path,
            "reason": doc.reason,
            "required_context": [
                _canonical_resource_row(item) for item in documentation.required_context
            ],
        }

    result: dict[str, Any] = {
        "pack_id": entry.id,
        "identity": dict(entry.identity),
        "name": definition.name,
        "version": definition.version,
        "schema_version": definition.schema_version,
        "description": definition.description,
        "status": status,
        "pack_status": definition.status,
        "source": entry.source,
        "source_path": str(entry.root),
        "root": str(entry.root),
        "manifest": _canonical_resource_row(entry.manifest),
        "manifest_digest": manifest_digest,
        "provenance_identity": entry.provenance.provenance_identity,
        "taxonomy": {
            "origin": "builtin" if entry.source == "bundled" else "external",
            "install_tier": (
                "default"
                if database is not None and database.default_enabled
                else "optional"
            ),
            "pack_type": "capability" if capabilities.capabilities else "adapter",
            "domain": definition.domain,
            "stability": definition.stability,
            "support": definition.support,
        },
        "capabilities": list(capabilities.capabilities),
        "capability_summary": {
            "declared": list(capabilities.capabilities),
            "content": dict(capabilities.content),
            "extensions": normalized.get("extensions", {}),
            "aliases": normalized.get("aliases", []),
            "permissions": normalized.get("permissions", []),
        },
        "database": database_data,
        "documentation": docs_data,
        "resources": resource_rows,
        "resource_closure": {
            "count": len(resource_rows),
            "paths": [item["path"] for item in resource_rows],
        },
        "component_counts": component_counts,
        "entrypoints": entrypoints,
        "declared_secrets": declared_secrets,
        "dependencies": dependencies,
        "agent": normalized.get("agent"),
        "keywords": list(definition.keywords),
        "permissions": normalized.get("permissions", []),
        "permission_ids": trust.get(
            "permission_ids",
            [item.get("id") for item in normalized.get("permissions", [])],
        ),
        "trust": trust.get("trust", {}),
        "warnings": list(trust.get("warnings", ())),
        "dependencies_struct": trust.get("dependencies_struct", {}),
    }
    if record is not None:
        for field in (
            "installed_at",
            "git_url",
            "commit_sha",
            "requested_ref",
            "astrid_version",
            "trust_tier",
            "previous_active_revision",
        ):
            result[field] = getattr(record, field, None)
        result["install_source_path"] = getattr(record, "source_path", None)
    return result


def _build_canonical_agent_view(
    entry: CanonicalPackEntry,
    *,
    record: Any | None = None,
) -> dict[str, Any]:
    """Build the agent view from a normalized canonical definition."""
    trust = dict(getattr(record, "trust_summary", {}) or {}) if record is not None else {}
    view = _build_agent_view(entry.definition.to_dict(), trust)
    view.update(
        {
            "pack_id": entry.id,
            "identity": dict(entry.identity),
            "source": entry.source,
            "root": str(entry.root),
        }
    )
    return view

# ---------------------------------------------------------------------------
# pack inspect
# ---------------------------------------------------------------------------


def _inspect_installed_pack(*, pack_id: str, agent: bool, json_output: bool) -> int:
    """Render installed-pack inspect output for the public wrapper and CLI."""
    from astrid.core.pack.store import InstalledPackStore

    store = InstalledPackStore()
    record = store.get_active(pack_id)

    if record is None:
        raise AstridError(
            f"inspect: pack {pack_id!r} is not installed.",
            recovery_command=f"Install the pack first: python3 -m astrid packs install {pack_id}",
        )

    rev_dir = store.active_revision_path(pack_id)
    if rev_dir is None:
        raise AstridError(
            f"inspect: cannot resolve active revision for {pack_id!r}.",
            recovery_command=f"Try reinstalling the pack: python3 -m astrid packs install {pack_id}",
        )

    manifest_path = canonical_manifest_path(rev_dir)
    if manifest_path is None:
        raise AstridError(
            f"inspect: no canonical pack.yaml found in installed revision {rev_dir}.",
            recovery_command=f"The installed revision may be corrupt. Try reinstalling the pack: python3 -m astrid packs install {pack_id}",
        )

    try:
        entry = read_normalize_validate(
            manifest_path,
            source=ExternalPackSource.INSTALLED,
            expected_pack_id=pack_id,
        )
    except Exception as exc:
        raise AstridError(
            f"inspect: failed to load canonical pack entry: {exc}",
            recovery_command=f"Try reinstalling the pack: python3 -m astrid packs install {pack_id}",
        ) from exc

    if agent:
        agent_data = _build_canonical_agent_view(entry, record=record)
        if json_output:
            print(json.dumps(agent_data, indent=2, sort_keys=True, default=str))
        else:
            _print_agent_view(agent_data)
        return 0

    full_data = _build_canonical_inspect(entry, record=record)
    if json_output:
        print(json.dumps(full_data, indent=2, sort_keys=True, default=str))
    else:
        _print_full_inspect(full_data)

    return 0


def cmd_inspect(argv: list[str]) -> int:
    """Show details for an installed pack.

    Usage: python3 -m astrid packs inspect <pack_id> [--agent] [--json]
    """
    parser = argparse.ArgumentParser(
        prog="python3 -m astrid packs inspect",
        description="Show details for an installed pack.",
    )
    parser.add_argument(
        "pack_id",
        help="Pack identifier to inspect.",
    )
    parser.add_argument(
        "--agent",
        action="store_true",
        help="Emit agent-focused subset (purpose, entrypoints, constraints, "
        "context, secrets).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json",
        help="Output as JSON.",
    )
    parser.add_argument(
        "--pack-root", action="append", dest="pack_roots",
        help="Additional pack collection root (also honors ASTRID_PACKS_PATH).",
    )
    args = parser.parse_args(argv)
    return _inspect_installed_pack(
        pack_id=args.pack_id,
        agent=bool(args.agent),
        json_output=bool(args.json),
    )


# ---------------------------------------------------------------------------
# Agent-view helpers
# ---------------------------------------------------------------------------


def _build_agent_view(manifest: dict, trust_summary: dict) -> dict:
    """Build an agent-focused subset of a pack manifest."""
    agent_section = manifest.get("agent", {}) if isinstance(manifest.get("agent"), dict) else {}
    secrets_section = manifest.get("secrets")

    view: dict = {}

    # Purpose
    purpose = agent_section.get("purpose")
    if purpose:
        view["purpose"] = str(purpose)

    # Entrypoints — prefer normal_entrypoints, fall back to entrypoints
    normal_entrypoints = trust_summary.get("normal_entrypoints", [])
    if not normal_entrypoints and isinstance(agent_section.get("normal_entrypoints"), list):
        normal_entrypoints = [str(ep) for ep in agent_section["normal_entrypoints"] if ep]
    entrypoints = trust_summary.get("entrypoints", [])
    if not entrypoints and isinstance(agent_section.get("entrypoints"), list):
        entrypoints = [str(ep) for ep in agent_section["entrypoints"] if ep]
    display_entrypoints = normal_entrypoints if normal_entrypoints else entrypoints
    if display_entrypoints:
        view["normal_entrypoints"] = normal_entrypoints if normal_entrypoints else None
        view["entrypoints"] = display_entrypoints

    # Constraints (from agent section or metadata)
    constraints = agent_section.get("constraints")
    if constraints is None:
        metadata = manifest.get("metadata", {}) if isinstance(manifest.get("metadata"), dict) else {}
        constraints = metadata.get("constraints")
    if constraints:
        view["constraints"] = constraints if isinstance(constraints, str) else str(constraints)

    # Context (from agent section or metadata)
    context = agent_section.get("context")
    if context is None:
        metadata = manifest.get("metadata", {}) if isinstance(manifest.get("metadata"), dict) else {}
        context = metadata.get("context")
    if context:
        view["context"] = context if isinstance(context, str) else str(context)

    # do_not_use_for and required_context from agent section
    do_not_use_for = agent_section.get("do_not_use_for")
    if do_not_use_for:
        view["do_not_use_for"] = str(do_not_use_for)

    required_context = agent_section.get("required_context")
    if isinstance(required_context, list):
        view["required_context"] = [str(rc) for rc in required_context if rc]

    # Secrets — handle both new and old formats
    if isinstance(secrets_section, list):
        # New format: list of {name, required, description}
        structured_secrets: list[dict[str, Any]] = []
        for s_obj in secrets_section:
            if isinstance(s_obj, dict) and s_obj.get("name"):
                structured_secrets.append({
                    "name": str(s_obj["name"]),
                    "required": bool(s_obj.get("required", False)),
                    "description": str(s_obj.get("description", "")),
                })
        view["secrets"] = structured_secrets
    elif isinstance(secrets_section, dict):
        # Old format: dict with 'required' list
        secrets_list: list[str] = trust_summary.get("declared_secrets", [])
        if not secrets_list and isinstance(secrets_section.get("required"), list):
            secrets_list = [str(s) for s in secrets_section["required"] if s]
        if secrets_list:
            view["secrets"] = secrets_list

    # Keywords and capabilities from manifest
    keywords_raw = manifest.get("keywords")
    if isinstance(keywords_raw, list):
        view["keywords"] = [str(k) for k in keywords_raw if k]

    capabilities_raw = manifest.get("capabilities")
    if isinstance(capabilities_raw, list):
        view["capabilities"] = [str(c) for c in capabilities_raw if c]

    # Permissions and trust metadata — sourced from extract_trust_summary()
    permissions = trust_summary.get("permissions")
    if permissions:
        view["permissions"] = permissions
    permission_ids = trust_summary.get("permission_ids")
    if permission_ids:
        view["permission_ids"] = permission_ids
    trust_block = trust_summary.get("trust")
    if trust_block:
        view["trust"] = trust_block

    return view


def _print_agent_view(view: dict) -> None:
    """Pretty-print an agent-focused pack view."""
    print(f"━━━ Agent View: {view.get('pack_id', '?')} ━━━")
    if "purpose" in view:
        print(f"Purpose:        {view['purpose']}")
    if "entrypoints" in view:
        eps = view["entrypoints"]
        if isinstance(eps, list):
            print(f"Entrypoints:    {', '.join(eps)}")
    if "normal_entrypoints" in view and view.get("normal_entrypoints"):
        print(f"Normal EPts:    {', '.join(view['normal_entrypoints'])}")
    if "constraints" in view:
        print(f"Constraints:    {view['constraints']}")
    if "context" in view:
        print(f"Context:        {view['context']}")
    if "do_not_use_for" in view:
        print(f"Do Not Use For: {view['do_not_use_for']}")
    if "required_context" in view:
        print(f"Req. Context:   {', '.join(view['required_context'])}")
    if "secrets" in view:
        secrets = view["secrets"]
        if isinstance(secrets, list) and secrets and isinstance(secrets[0], dict):
            for s_obj in secrets:
                req = " (required)" if s_obj.get("required") else ""
                print(f"Secret:         {s_obj['name']}{req}: {s_obj.get('description', '')}")
        else:
            print(f"Secrets:        {', '.join(secrets)}")
    if "keywords" in view:
        print(f"Keywords:       {', '.join(view['keywords'])}")
    if "capabilities" in view:
        print(f"Capabilities:   {', '.join(view['capabilities'])}")

    # Permissions — sourced from extract_trust_summary()
    permissions = view.get("permissions")
    if permissions:
        print("Permissions:")
        for p in permissions:
            if isinstance(p, dict):
                reason = p.get("reason", "")
                services = p.get("services")
                svc_str = f" (services: {', '.join(services)})" if services else ""
                print(f"  • {p.get('id', '?')}: {reason}{svc_str}")

    permission_ids = view.get("permission_ids")
    if permission_ids:
        print(f"Permission IDs: {', '.join(permission_ids)}")

    # Trust block — sourced from extract_trust_summary()
    trust_block = view.get("trust")
    if trust_block and isinstance(trust_block, dict):
        print("Trust:")
        sandbox = trust_block.get("sandbox", "")
        runs_with = trust_block.get("runs_with_user_process_permissions")
        enforcement = trust_block.get("permission_enforcement", "")
        print(f"  sandbox: {sandbox}")
        print(f"  runs_with_user_process_permissions: {runs_with}")
        print(f"  permission_enforcement: {enforcement}")
        print("  ℹ Permissions are disclosure-only. No sandboxing or runtime enforcement in beta.")


# ---------------------------------------------------------------------------
# Full inspect helpers
# ---------------------------------------------------------------------------

# Re-export the shared helper under the name callers expect.
from astrid.core.pack._common import (  # noqa: E402
    _COMPONENT_MANIFEST_NAMES as _INSPECT_COMPONENT_MANIFEST_NAMES,
)
from astrid.core.pack._common import (
    find_component_manifest as _find_component_manifest,
)


def _read_stage_excerpt(stage_path: Path, *, max_lines: int = 30) -> str | None:
    """Return a bounded excerpt from a STAGE.md file.

    Reads at most *max_lines* lines, stopping early at the first ``##``
    heading (ATX level-2).  Returns ``None`` when the file cannot be read.
    """
    if not stage_path.is_file():
        return None
    try:
        text = stage_path.read_text(encoding="utf-8")
    except OSError:
        return None
    lines = text.splitlines()
    excerpt_lines: list[str] = []
    for i, line in enumerate(lines):
        if i >= max_lines:
            break
        if line.startswith("##") and i > 0:
            break
        excerpt_lines.append(line)
    return "\n".join(excerpt_lines).strip() or None






def _print_full_inspect(data: dict) -> None:
    """Pretty-print a full pack inspect result."""
    print(f"━━━ Pack: {data['pack_id']} ━━━")
    print(f"  Name:          {data['name']}")
    print(f"  Version:       {data['version']}")
    print(f"  Schema:        {data['schema_version']}")
    print(f"  Status:        {data['status']}")
    print(f"  Source:        {data.get('source_path', '')}")
    if data.get("source"):
        print(f"  Source Kind:   {data['source']}")
    if data.get("root"):
        print(f"  Root:          {data['root']}")
    installed_at = data.get("installed_at")
    if installed_at:
        print(f"  Installed:     {installed_at}")

    identity = data.get("identity")
    if isinstance(identity, dict):
        print(
            "  Identity:      "
            f"{identity.get('id', '')} / {identity.get('name', '')} "
            f"/ {identity.get('version', '')}"
        )
    if data.get("provenance_identity"):
        print(f"  Provenance ID: {data['provenance_identity']}")

    desc = data.get("description")
    if desc:
        print(f"  Description:   {desc}")

    capability_summary = data.get("capability_summary")
    if isinstance(capability_summary, dict):
        declared = capability_summary.get("declared", ())
        print(f"  Capabilities:  {', '.join(str(item) for item in declared)}")

    database = data.get("database")
    if isinstance(database, dict) and database.get("owned"):
        print(
            "  Database:      "
            f"owner={database.get('owner', '')} "
            f"head={database.get('head', '')} "
            f"default={database.get('default_enabled', False)}"
        )
        tables = database.get("tables", ())
        if tables:
            print(f"  DB Tables:      {', '.join(str(item) for item in tables)}")
    else:
        print("  Database:      none")

    documentation = data.get("documentation")
    if isinstance(documentation, dict):
        print(
            f"  Documentation: {documentation.get('kind', '')}"
            f"{' ' + str(documentation.get('path')) if documentation.get('path') else ''}"
        )
    else:
        print("  Documentation: none")

    closure = data.get("resource_closure")
    if isinstance(closure, dict):
        print(f"  Resources:     {closure.get('count', 0)} declared/resolved")

    _print_taxonomy_block(data.get("taxonomy", {}), indent="  ")

    # Git-enriched fields
    git_url = data.get("git_url", "")
    if git_url:
        print(f"  Git URL:       {git_url}")

    commit_sha = data.get("commit_sha", "")
    if commit_sha:
        print(f"  Commit SHA:    {commit_sha[:8]}")

    source_type = data.get("source_type", "")
    if source_type:
        print(f"  Source Type:   {source_type}")

    requested_ref = data.get("requested_ref", "")
    if requested_ref:
        print(f"  Requested Ref: {requested_ref}")

    astrid_version = data.get("astrid_version", "")
    if astrid_version:
        print(f"  Astrid Ver:    {astrid_version}")

    trust_tier = data.get("trust_tier", "")
    if trust_tier:
        print(f"  Trust Tier:    {trust_tier}")

    manifest_digest = data.get("manifest_digest", "")
    if manifest_digest:
        print(f"  Manifest Hash: {manifest_digest}")

    previous = data.get("previous_active_revision", "")
    if previous:
        print(f"  Prev Revision: {previous}")

    # Components
    counts = data.get("component_counts", {})
    if counts:
        parts = []
        for k in ("executors", "orchestrators", "elements"):
            if counts.get(k, 0):
                parts.append(f"{counts[k]} {k}")
        if parts:
            print(f"  Components:    {', '.join(parts)}")
        else:
            print("  Components:    (none)")
    else:
        print("  Components:    (none)")

    # Entrypoints
    entrypoints = data.get("entrypoints", [])
    if entrypoints:
        print(f"  Entrypoints:   {', '.join(entrypoints)}")

    # Secrets (structured)
    secrets = data.get("secrets", [])
    if secrets:
        if isinstance(secrets, list) and secrets and isinstance(secrets[0], dict):
            for s_obj in secrets:
                req = " (required)" if s_obj.get("required") else ""
                desc = s_obj.get("description", "")
                print(f"  Secret:        {s_obj['name']}{req}{': ' + desc if desc else ''}")
        else:
            print(f"  Secrets:       {', '.join(str(s) for s in secrets)}")

    # Dependencies
    deps = data.get("dependencies", [])
    if deps:
        if isinstance(deps, list):
            print(f"  Dependencies:  {', '.join(deps)}")
        elif isinstance(deps, dict):
            dep_parts = []
            for eco, pkg_list in deps.items():
                if pkg_list:
                    dep_parts.append(f"{eco}:{','.join(pkg_list)}")
            if dep_parts:
                print(f"  Dependencies:  {'; '.join(dep_parts)}")

    # Structured dependencies
    deps_struct = data.get("dependencies_struct", {})
    if deps_struct:
        dep_parts = []
        for eco, pkg_list in deps_struct.items():
            if pkg_list:
                dep_parts.append(f"{eco}:{','.join(pkg_list)}")
        if dep_parts:
            print(f"  Deps Struct:   {'; '.join(dep_parts)}")

    # New structured fields
    normal_entrypoints = data.get("normal_entrypoints", [])
    if normal_entrypoints:
        print(f"  Normal EPts:   {', '.join(normal_entrypoints)}")

    do_not_use_for = data.get("do_not_use_for")
    if do_not_use_for:
        print(f"  DoNotUseFor:   {do_not_use_for}")

    required_context = data.get("required_context", [])
    if required_context:
        print(f"  Req. Context:  {', '.join(required_context)}")

    keywords = data.get("keywords", [])
    if keywords:
        print(f"  Keywords:      {', '.join(keywords)}")

    capabilities = data.get("capabilities", [])
    if capabilities:
        print(f"  Capabilities:  {', '.join(capabilities)}")

    # Components list
    components = data.get("components", [])
    if components:
        print(f"  Components:    ({len(components)} total)")
        for comp in components:
            ep_mark = " [ENTRYPOINT]" if comp.get("is_entrypoint") else ""
            print(f"    • {comp['id']} ({comp.get('kind', '?')}){ep_mark}: {comp.get('description', '')[:80]}")
            se = comp.get("stage_excerpt")
            if se:
                first_line = se.split("\n")[0][:120]
                print(f"      stage: {first_line}")

    # Docs
    docs = data.get("docs", {})
    if docs:
        doc_parts = [f"{k}={v}" for k, v in docs.items() if v]
        if doc_parts:
            print(f"  Docs:          {', '.join(doc_parts)}")

    # Agent block
    agent = data.get("agent")
    if agent:
        purpose = agent.get("purpose") if isinstance(agent, dict) else None
        if purpose:
            print(f"  Purpose:       {purpose}")

    # Warnings
    warnings = data.get("warnings", [])
    if warnings:
        print("  ⚠ Warnings:")
        for w in warnings:
            print(f"    • {w}")

    # Permissions — sourced from extract_trust_summary()
    permissions = data.get("permissions")
    if permissions:
        print("  Permissions:")
        for p in permissions:
            if isinstance(p, dict):
                reason = p.get("reason", "")
                services = p.get("services")
                svc_str = f" (services: {', '.join(services)})" if services else ""
                print(f"    • {p.get('id', '?')}: {reason}{svc_str}")

    permission_ids = data.get("permission_ids")
    if permission_ids:
        print(f"  Permission IDs: {', '.join(permission_ids)}")

    # Trust block — sourced from extract_trust_summary()
    trust_block = data.get("trust")
    if trust_block and isinstance(trust_block, dict):
        print("  Trust:")
        sandbox = trust_block.get("sandbox", "")
        runs_with = trust_block.get("runs_with_user_process_permissions")
        enforcement = trust_block.get("permission_enforcement", "")
        print(f"    sandbox: {sandbox}")
        print(f"    runs_with_user_process_permissions: {runs_with}")
        print(f"    permission_enforcement: {enforcement}")
        print("  ℹ Permissions are disclosure-only. No sandboxing or runtime enforcement in beta.")


def _inspect_discovered_pack(
    *,
    pack_id: str,
    agent: bool,
    json_output: bool,
    pack_roots: tuple[str, ...] = (),
) -> int:
    """Render a bundled or externally discovered canonical pack entry."""
    catalog = BundledCatalog.from_root(DEFAULT_PACKS_ROOT)
    entries: dict[str, CanonicalPackEntry] = {
        entry.id: entry for entry in catalog.ordered_entries
    }
    repo_root = DEFAULT_PACKS_ROOT.parent.parent
    for entry in discover_canonical_packs_ordered(
        project_root=repo_root,
        extra_pack_roots=tuple(pack_roots),
        include_installed=True,
    ):
        # Preserve the existing source precedence: bundled entries win over
        # local/extra/environment/installed duplicates.
        entries.setdefault(entry.id, entry)

    entry = entries.get(pack_id)
    if entry is None:
        raise AstridError(
            f"packs inspect: unknown canonical pack {pack_id!r}",
            recovery_command="List available packs: python3 -m astrid packs list",
        )

    if agent:
        payload = _build_canonical_agent_view(entry)
        if json_output:
            print(json.dumps(payload, indent=2, sort_keys=True, default=str))
        else:
            _print_agent_view(payload)
        return 0

    payload = _build_canonical_inspect(entry)
    if json_output:
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    else:
        _print_full_inspect(payload)
    return 0

def _handle_inspect(args: argparse.Namespace) -> int:
    """Handler for ``packs inspect``."""
    from astrid.core.pack.store import InstalledPackStore

    store = InstalledPackStore()
    if store.get_active(args.pack_id) is None:
        return _inspect_discovered_pack(
            pack_id=args.pack_id,
            agent=bool(args.agent),
            json_output=bool(args.json),
            pack_roots=tuple(args.pack_roots or ()),
        )

    return _inspect_installed_pack(
        pack_id=args.pack_id,
        agent=bool(args.agent),
        json_output=bool(args.json),
    )
