""":mod:`astrid.core.pack.cli_inspect` — Pack inspect command handlers and helpers.

Extracted from ``astrid/core/pack/cli.py`` during M4 giant-file split.
Contains ``cmd_inspect``, ``_handle_inspect``, and all private helpers for
building and printing both full and agent-focused pack inspect output.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

import yaml

from astrid.contracts.errors import AstridError
from astrid.core.element.schema import ELEMENT_MANIFEST_NAMES
from astrid.core.pack import (
    PackDefinition,
    discover_packs,
    pack_manifest_path,
    pack_taxonomy_from_manifest,
    packs_root,
)
from astrid.core.pack.validate import (
    extract_trust_summary,
)

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

    manifest_path = pack_manifest_path(rev_dir)
    if manifest_path is None:
        raise AstridError(
            f"inspect: no pack manifest found in installed revision {rev_dir}.",
            recovery_command=f"The installed revision may be corrupt. Try reinstalling: python3 -m astrid packs install {pack_id}",
        )

    try:
        if manifest_path.suffix == ".json":
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        else:
            manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise AstridError(
            f"inspect: failed to parse pack manifest: {e}",
            recovery_command=f"Check the manifest file for syntax errors: cat {manifest_path}",
        ) from e

    if not isinstance(manifest, dict):
        raise AstridError(
            "inspect: pack manifest is not a mapping",
            recovery_command=f"Check the manifest file structure: cat {manifest_path}",
        )

    try:
        trust_summary = extract_trust_summary(rev_dir)
    except Exception:
        trust_summary = {}

    if agent:
        agent_data = _build_agent_view(manifest, trust_summary)
        if json_output:
            print(json.dumps(agent_data, indent=2, default=str))
        else:
            _print_agent_view(agent_data)
        return 0

    full_data = _build_full_inspect(record, manifest, trust_summary, rev_dir=rev_dir)
    if json_output:
        print(json.dumps(full_data, indent=2, default=str))
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
        print("  ℹ Permissions are disclosure-only. No sandboxing or runtime enforcement in v1.")


# ---------------------------------------------------------------------------
# Full inspect helpers
# ---------------------------------------------------------------------------

# Recognised component manifest filenames keyed by kind.
_INSPECT_COMPONENT_MANIFEST_NAMES: dict[str, tuple[str, ...]] = {
    "executor": ("executor.yaml", "executor.yml", "executor.json"),
    "orchestrator": ("orchestrator.yaml", "orchestrator.yml", "orchestrator.json"),
    "element": ELEMENT_MANIFEST_NAMES,
}


def _find_component_manifest(comp_dir: Path, kind: str) -> Path | None:
    """Return the first manifest file found in *comp_dir* for *kind*."""
    names = _INSPECT_COMPONENT_MANIFEST_NAMES.get(kind, ())
    for name in sorted(names):
        candidate = comp_dir / name
        if candidate.is_file():
            return candidate
    return None


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


def _scan_inspect_components(
    rev_dir: Path | None, manifest: dict[str, Any]
) -> list[dict[str, Any]]:
    """Scan component manifests under declared content roots in *rev_dir*.

    Returns a deterministic (sorted by id) list of component overview dicts.
    Each dict includes: id, name, kind, description, runtime, is_entrypoint,
    docs_paths, stage_excerpt.
    """
    if rev_dir is None:
        return []

    content = manifest.get("content", {}) if isinstance(manifest.get("content"), dict) else {}
    agent = manifest.get("agent", {}) if isinstance(manifest.get("agent"), dict) else {}
    normal_eps = set()
    if isinstance(agent.get("normal_entrypoints"), list):
        normal_eps = {str(ep) for ep in agent["normal_entrypoints"] if ep}
    if not normal_eps and isinstance(agent.get("entrypoints"), list):
        normal_eps = {str(ep) for ep in agent["entrypoints"] if ep}

    components: list[dict[str, Any]] = []

    for comp_kind in ("executors", "orchestrators"):
        comp_root_rel = content.get(comp_kind)
        if not isinstance(comp_root_rel, str) or not comp_root_rel.strip():
            continue
        comp_root = rev_dir / comp_root_rel
        if not comp_root.is_dir():
            continue

        manifest_kind = comp_kind.rstrip("s")  # "executors" -> "executor"

        for comp_dir in sorted(comp_root.iterdir()):
            if not comp_dir.is_dir() or comp_dir.name.startswith("."):
                continue
            if comp_dir.name == "__pycache__":
                continue

            mf_path = _find_component_manifest(comp_dir, manifest_kind)
            if mf_path is None:
                continue

            data: dict[str, Any] | None
            try:
                if mf_path.suffix == ".json":
                    import json as _json_inspect
                    data = _json_inspect.loads(mf_path.read_text(encoding="utf-8"))
                else:
                    data = yaml.safe_load(mf_path.read_text(encoding="utf-8"))
            except Exception:
                continue

            if not isinstance(data, dict):
                continue

            comp_id = str(data.get("id", comp_dir.name))
            name = str(data.get("name", comp_id))
            description = str(data.get("description", ""))
            kind = str(data.get("kind", manifest_kind))

            # Runtime
            runtime_raw = data.get("runtime", {}) if isinstance(data.get("runtime"), dict) else {}
            runtime: dict[str, Any] | None = None
            if runtime_raw:
                runtime = {
                    "type": runtime_raw.get("type"),
                    "entrypoint": runtime_raw.get("entrypoint"),
                    "callable": runtime_raw.get("callable"),
                }

            # Is entrypoint?
            is_entrypoint = comp_id in normal_eps

            # Docs paths
            docs = data.get("docs", {}) if isinstance(data.get("docs"), dict) else {}
            stage_rel = docs.get("stage", "STAGE.md")
            stage_path = comp_dir / stage_rel
            docs_paths: dict[str, str] = {"stage": str(stage_path)}

            # Stage excerpt
            stage_excerpt = _read_stage_excerpt(stage_path)

            components.append({
                "id": comp_id,
                "name": name,
                "kind": kind,
                "description": description,
                "runtime": runtime,
                "is_entrypoint": is_entrypoint,
                "docs_paths": docs_paths,
                "stage_excerpt": stage_excerpt,
            })

    # Elements: two-level structure — elements/<kind>/<element_name>/
    elements_root_rel = content.get("elements")
    if isinstance(elements_root_rel, str) and elements_root_rel.strip():
        elements_root = rev_dir / elements_root_rel
        if elements_root.is_dir():
            for kind_dir in sorted(elements_root.iterdir()):
                if not kind_dir.is_dir() or kind_dir.name.startswith("."):
                    continue
                if kind_dir.name == "__pycache__":
                    continue

                for elem_dir in sorted(kind_dir.iterdir()):
                    if not elem_dir.is_dir() or elem_dir.name.startswith("."):
                        continue
                    if elem_dir.name == "__pycache__":
                        continue

                    mf_path = _find_component_manifest(elem_dir, "element")
                    if mf_path is None:
                        continue

                    data: dict[str, Any] | None
                    try:
                        if mf_path.suffix == ".json":
                            import json as _json_inspect
                            data = _json_inspect.loads(mf_path.read_text(encoding="utf-8"))
                        else:
                            data = yaml.safe_load(mf_path.read_text(encoding="utf-8"))
                    except Exception:
                        continue

                    if not isinstance(data, dict):
                        continue

                    comp_id = str(data.get("id", elem_dir.name))
                    name = str(data.get("metadata", {}).get("label", comp_id)) if isinstance(data.get("metadata"), dict) else str(data.get("name", comp_id))
                    description = str(data.get("description", ""))
                    kind = str(data.get("kind", kind_dir.name.rstrip("s")))

                    # Elements have no runtime/entrypoint
                    runtime = None
                    is_entrypoint = False

                    # Docs paths
                    docs = data.get("docs", {}) if isinstance(data.get("docs"), dict) else {}
                    stage_rel = docs.get("stage", "STAGE.md")
                    stage_path = elem_dir / stage_rel
                    docs_paths: dict[str, str] = {"stage": str(stage_path)}

                    # Stage excerpt
                    stage_excerpt = _read_stage_excerpt(stage_path)

                    components.append({
                        "id": comp_id,
                        "name": name,
                        "kind": kind,
                        "description": description,
                        "runtime": runtime,
                        "is_entrypoint": is_entrypoint,
                        "docs_paths": docs_paths,
                        "stage_excerpt": stage_excerpt,
                    })

    # Sort by id for determinism
    components.sort(key=lambda c: c["id"])
    return components


def _build_full_inspect(
    record: "InstallRecord", manifest: dict, trust_summary: dict,
    *, rev_dir: "Path | None" = None,
) -> dict:
    """Build a full inspect dict for JSON or pretty-print output.

    When *rev_dir* is provided, component manifests under declared content
    roots are scanned and STAGE.md excerpts are extracted for each component.
    """
    # ── Structured secrets ──────────────────────────────────────────
    secrets_raw = manifest.get("secrets")
    structured_secrets: list[dict[str, Any]] = []
    if isinstance(secrets_raw, list):
        for s_obj in secrets_raw:
            if isinstance(s_obj, dict) and s_obj.get("name"):
                structured_secrets.append({
                    "name": str(s_obj["name"]),
                    "required": bool(s_obj.get("required", False)),
                    "description": str(s_obj.get("description", "")),
                })
    elif isinstance(secrets_raw, dict):
        req_list = secrets_raw.get("required")
        if isinstance(req_list, list):
            for s in req_list:
                if s:
                    structured_secrets.append({
                        "name": str(s), "required": True, "description": "",
                    })

    # ── Structured dependencies ─────────────────────────────────────
    deps_raw = manifest.get("dependencies")
    structured_deps: dict[str, list[str]] = {}
    if isinstance(deps_raw, dict):
        for eco in ("python", "npm", "system"):
            eco_deps = deps_raw.get(eco)
            if isinstance(eco_deps, list):
                structured_deps[eco] = [str(d) for d in eco_deps if d]

    # ── Components scan ─────────────────────────────────────────────
    components = _scan_inspect_components(rev_dir, manifest) if rev_dir is not None else []
    taxonomy = pack_taxonomy_from_manifest(manifest, status=str(manifest.get("status", "active")))

    result = {
        "pack_id": record.pack_id,
        "name": record.name,
        "version": record.version,
        "schema_version": record.schema_version,
        "description": manifest.get("description", ""),
        "source_path": record.source_path,
        "installed_at": record.installed_at,
        "status": "active" if record.active else "inactive",
        "component_counts": trust_summary.get("component_counts", {}),
        "entrypoints": trust_summary.get("entrypoints", []),
        "declared_secrets": trust_summary.get("declared_secrets", []),
        "secrets": structured_secrets,  # structured: [{name, required, description}]
        "dependencies": trust_summary.get("dependencies", []),
        "dependencies_struct": trust_summary.get("dependencies_struct", {}),
        "docs": trust_summary.get("docs", {}),
        "warnings": trust_summary.get("warnings", []),
        "agent": manifest.get("agent") if isinstance(manifest.get("agent"), dict) else None,
        # Git-enriched and trust fields
        "git_url": record.git_url,
        "commit_sha": record.commit_sha,
        "source_type": record.source_type,
        "requested_ref": record.requested_ref,
        "astrid_version": record.astrid_version if hasattr(record, 'astrid_version') else None,
        "trust_tier": record.trust_tier,
        "manifest_digest": record.manifest_digest if hasattr(record, 'manifest_digest') else None,
        "previous_active_revision": record.previous_active_revision if hasattr(record, 'previous_active_revision') else None,
        # New structured fields from trust_summary
        "normal_entrypoints": trust_summary.get("normal_entrypoints", []),
        "do_not_use_for": trust_summary.get("do_not_use_for"),
        "required_context": trust_summary.get("required_context", []),
        "keywords": trust_summary.get("keywords", []),
        "capabilities": trust_summary.get("capabilities", []),
        # Permissions and trust metadata — sourced from extract_trust_summary()
        "permissions": trust_summary.get("permissions", []),
        "permission_ids": trust_summary.get("permission_ids", []),
        "trust": trust_summary.get("trust", {}),
        **taxonomy,
        "taxonomy": taxonomy,
        # Component details (scanned from disk)
        "components": components,
    }
    return result


def _print_full_inspect(data: dict) -> None:
    """Pretty-print a full pack inspect result."""
    # Late import for _print_taxonomy_block from the .cli facade
    from .cli import _print_taxonomy_block

    print(f"━━━ Pack: {data['pack_id']} ━━━")
    print(f"  Name:          {data['name']}")
    print(f"  Version:       {data['version']}")
    print(f"  Schema:        {data['schema_version']}")
    print(f"  Status:        {data['status']}")
    print(f"  Source:        {data['source_path']}")
    print(f"  Installed:     {data['installed_at']}")

    desc = data.get("description")
    if desc:
        print(f"  Description:   {desc}")

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
        print("    ℹ Permissions are disclosure-only. No sandboxing or runtime enforcement in v1.")


def _inspect_discovered_pack(*, pack_id: str, agent: bool, json_output: bool) -> int:
    """Render discovery-backed inspect output for non-installed packs."""
    # Late imports from .cli facade for shared helpers
    from .cli import _pack_payload, _pack_taxonomy, _print_taxonomy_block

    packs = {pack.id: pack for pack in discover_packs(packs_root(), include_hidden=True)}
    pack = packs.get(pack_id)
    if pack is None:
        raise AstridError(
            f"packs inspect: unknown pack {pack_id!r}",
            recovery_command="List available packs: python3 -m astrid packs list",
        )

    payload = pack.agent if agent else _pack_payload(pack)
    if json_output:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    if agent:
        for key, value in sorted(payload.items()):
            print(f"{key}: {value}")
        return 0

    for key in ("id", "name", "version", "description", "status", "visibility", "root", "manifest_path"):
        print(f"{key}: {payload.get(key, '')}")
    _print_taxonomy_block(payload.get("taxonomy", _pack_taxonomy(pack)))
    if pack.content:
        print("content:")
        for key, value in sorted(pack.content.items()):
            print(f"  {key}: {value}")
    if pack.agent:
        print("agent:")
        for key, value in sorted(pack.agent.items()):
            print(f"  {key}: {value}")
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
        )

    return _inspect_installed_pack(
        pack_id=args.pack_id,
        agent=bool(args.agent),
        json_output=bool(args.json),
    )
