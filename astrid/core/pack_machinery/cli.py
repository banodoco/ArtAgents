""":mod:`astrid.core.pack_machinery.cli` — Canonical pack CLI implementation.

This is the canonical home for the ``astrid packs`` CLI machinery,
moved from ``astrid/packs/cli.py`` during M1 Pack Layout Normalization
(Plan v1.0).

The ``astrid.packs.cli`` module is now a thin compatibility re-export
shim.  All new imports should target this module directly.

``packs validate <path>`` statically validates a pack root directory.
``packs new <id>`` scaffolds a minimal pack skeleton in the CWD.

Neither command loads the built-in registry, imports pack code, or
requires a bound session.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Optional

import yaml

from astrid.contracts.errors import AstridError
from astrid.core.cli_choices import RecoverableArgumentParser, add_choice_arg
from astrid.core.element.schema import ELEMENT_MANIFEST_NAMES
from astrid.core.pack import (
    PackDefinition,
    discover_packs,
    pack_manifest_path,
    pack_taxonomy_from_manifest,
    packs_root,
)
from astrid.core.element.schema import ELEMENT_MANIFEST_NAMES
from astrid.core.pack_machinery.validate import (
    extract_trust_summary,
    is_first_party_packs_root_candidate,
    validate_first_party_packs_root,
    validate_pack,
)

# Must match the pack_id pattern in _defs.json: lowercase, digits, underscore
_PACK_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")


# Shared stderr sink for non-fatal warnings and diagnostics.
def _eprint(*args: object) -> None:
    print(*args, file=sys.stderr)

_SKILL_MD_STUB = """# {pack_name} — Agent Guide

## When to Use This Pack

Explain in 1-2 sentences when an agent should choose this pack.

## Entrypoints

List the orchestrators agents should start with for common tasks.

## Executors

Briefly describe each executor and its purpose.
"""


def _pack_id_is_valid(pack_id: str) -> bool:
    """Check that a pack id matches the v1 schema pattern."""
    return bool(_PACK_ID_RE.fullmatch(pack_id))


def _validate_pack_path(path: Path, must_exist: bool = True) -> Path:
    """Resolve and validate a pack root directory path.

    Args:
        path: The path to resolve.
        must_exist: If True, require the directory to exist.

    Returns:
        The resolved Path.

    Raises:
        SystemExit(2) on invalid paths.
    """
    resolved = path.resolve()
    if must_exist and not resolved.is_dir():
        raise AstridError(
            f"packs validate: {path} is not a directory or does not exist",
            recovery_command=f"ls -d {path}  # verify the path exists and is a directory",
        )
    return resolved


def _validate_target(path: Path) -> tuple[list[str], list[str]]:
    if is_first_party_packs_root_candidate(path):
        return validate_first_party_packs_root(path)
    return validate_pack(path)


def cmd_validate(argv: list[str]) -> int:
    """Run static validation on a pack root directory.

    Usage: python3 -m astrid packs validate <path>
    """
    parser = argparse.ArgumentParser(
        prog="python3 -m astrid packs validate",
        description="Statically validate a pack directory.",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Path to the pack root directory (default: current directory).",
    )
    parser.add_argument(
        "--warnings",
        action="store_true",
        help="Also print non-fatal warnings.",
    )
    args = parser.parse_args(argv)

    pack_root = _validate_pack_path(Path(args.path))

    errors, warnings = _validate_target(pack_root)

    if errors:
        raise AstridError(
            "\n".join(errors),
            recovery_command="Fix the validation errors listed above and re-run: python3 -m astrid packs validate",
        )

    if args.warnings and warnings:
        for w in warnings:
            _eprint(f"warning: {w}")

    resolved = pack_root.resolve()
    if is_first_party_packs_root_candidate(resolved):
        print(f"valid: {resolved} (19 first-party packs)")
    else:
        print(f"valid: {resolved}")
    return 0


def _pack_payload(pack: PackDefinition) -> dict:
    return pack.to_dict()


def _pack_category(pack: PackDefinition) -> str:
    category = pack.metadata.get("category")
    if isinstance(category, str):
        return category
    return ""


def _effective_status(pack: PackDefinition) -> str:
    if pack.agent.get("purpose") == "TODO: describe what this pack is for":
        return "stub"
    return pack.status


_TAXONOMY_FIELDS = (
    "origin",
    "install_tier",
    "pack_type",
    "domain",
    "stability",
    "support",
)


def _pack_taxonomy(pack: PackDefinition) -> dict[str, str]:
    return {field: getattr(pack, field) for field in _TAXONOMY_FIELDS}


def _taxonomy_filters(args: argparse.Namespace) -> dict[str, str]:
    return {
        field: value
        for field in _TAXONOMY_FIELDS
        if isinstance((value := getattr(args, field, None)), str) and value
    }


def _matches_taxonomy_filters(pack: PackDefinition, args: argparse.Namespace) -> bool:
    for field, value in _taxonomy_filters(args).items():
        if getattr(pack, field) != value:
            return False
    return True


def _group_packs_by_domain(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        taxonomy = row.get("taxonomy")
        if isinstance(taxonomy, dict):
            domain = taxonomy.get("domain")
        else:
            domain = row.get("domain")
        label = str(domain or "general")
        groups.setdefault(label, []).append(row)
    return [
        {
            "group_by": "domain",
            "value": domain,
            "taxonomy": {"domain": domain},
            "packs": sorted(group_rows, key=lambda pack_row: str(pack_row["id"])),
        }
        for domain, group_rows in sorted(groups.items())
    ]


def _with_grouped_payload(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {"packs": rows, "groups": _group_packs_by_domain(rows)}


def _print_taxonomy_block(taxonomy: dict[str, Any], *, indent: str = "") -> None:
    print(f"{indent}taxonomy:")
    for field in _TAXONOMY_FIELDS:
        print(f"{indent}  {field}: {taxonomy.get(field, '')}")


def _print_grouped_rows(rows: list[dict[str, Any]], *, row_formatter: Any) -> None:
    for index, group in enumerate(_group_packs_by_domain(rows)):
        if index:
            print()
        print(f"taxonomy: domain={group['value']}")
        for row in group["packs"]:
            row_formatter(row)


def _format_list_row(row: dict[str, Any]) -> None:
    taxonomy = row.get("taxonomy", {})
    print(
        f"{row['id']}\t{row['name']}\t{row['version']}\t"
        f"origin={taxonomy.get('origin', '')}\t"
        f"tier={taxonomy.get('install_tier', '')}\t"
        f"type={taxonomy.get('pack_type', '')}\t"
        f"stability={taxonomy.get('stability', '')}\t"
        f"support={taxonomy.get('support', '')}\t"
        f"{row['description']}"
    )


def _format_status_row(row: dict[str, Any]) -> None:
    validation = row["validation"]
    taxonomy = row.get("taxonomy", {})
    print(
        f"{row['id']}\t{row['effective_status']}\t{row['visibility']}\t"
        f"errors={validation['errors']}\twarnings={validation['warnings']}\t"
        f"origin={taxonomy.get('origin', '')}\t"
        f"tier={taxonomy.get('install_tier', '')}\t"
        f"type={taxonomy.get('pack_type', '')}\t"
        f"stability={taxonomy.get('stability', '')}\t"
        f"support={taxonomy.get('support', '')}\t"
        f"{row['description']}"
    )


def _add_taxonomy_filter_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--domain", help="Filter by taxonomy.domain.")
    parser.add_argument("--origin", help="Filter by taxonomy.origin.")
    parser.add_argument("--install-tier", dest="install_tier", help="Filter by taxonomy.install_tier.")
    parser.add_argument("--pack-type", dest="pack_type", help="Filter by taxonomy.pack_type.")
    parser.add_argument("--stability", help="Filter by taxonomy.stability.")
    parser.add_argument("--support", help="Filter by taxonomy.support.")


def _filtered_packs(args: argparse.Namespace, *, include_hidden: bool | None = None) -> list[PackDefinition]:
    show_hidden = bool(getattr(args, "show_hidden", False))
    packs = list(discover_packs(packs_root(), include_hidden=show_hidden if include_hidden is None else include_hidden))
    category = getattr(args, "category", None)
    status = getattr(args, "status", None)
    visibility = getattr(args, "visibility", None)
    if category:
        packs = [pack for pack in packs if _pack_category(pack) == category]
    packs = [pack for pack in packs if _matches_taxonomy_filters(pack, args)]
    if status:
        packs = [pack for pack in packs if _effective_status(pack) == status]
    if visibility:
        packs = [pack for pack in packs if pack.visibility == visibility]
    return packs


def _create_pack_skeleton(pack_id: str) -> int:
    """Create and validate a new pack skeleton in the current directory."""
    if not _pack_id_is_valid(pack_id):
        raise AstridError(
            f"packs new: invalid pack id {pack_id!r}. "
            f"Must match pattern: ^[a-z][a-z0-9_]*$",
            valid_options=[],
            recovery_command="Pick a pack id using only lowercase letters, digits, and underscores (e.g., my_pack)",
        )

    target = Path.cwd() / pack_id
    if target.exists():
        raise AstridError(
            f"packs new: directory {target} already exists; "
            f"refusing to overwrite",
            recovery_command=f"Remove the existing directory first: rm -rf {target}",
        )

    if not target.parent.is_dir():
        raise AstridError(
            f"packs new: parent directory {target.parent} does not exist",
            recovery_command="Create the parent directory or run packs new from an existing directory",
        )

    pack_name = pack_id.replace("_", " ").title()
    description = f"A pack for {pack_name}."

    target.mkdir(parents=False)

    pack_yaml = target / "pack.yaml"
    pack_yaml.write_text(
        f"""schema_version: 1
id: {pack_id}
name: {pack_name}
version: 0.1.0
# One-line summary shown in `packs list` and search results. Make it specific.
description: {description}
origin: external
install_tier: core
pack_type: capability
domain: system
stability: stable
support: core
# Search/selection metadata: agents find and choose packs by these. Fill them in.
keywords: []          # search terms an agent would type, e.g. [video, editing, ffmpeg]
capabilities: []      # concrete things this pack can do, e.g. [trim_clip, concat, add_subtitles]
content:
  executors: executors
  orchestrators: orchestrators
  elements: elements
agent:
  purpose: "TODO: describe what this pack is for"
  do_not_use_for: "TODO: when an agent should NOT pick this pack"
  normal_entrypoints: []   # orchestrator/executor ids an agent should start with
  required_context: []     # inputs/secrets an agent must have before using this pack
""",
        encoding="utf-8",
    )

    skill_dir = target / "skill"
    skill_dir.mkdir(parents=False)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(
        _SKILL_MD_STUB.format(pack_name=pack_name),
        encoding="utf-8",
    )

    created = [
        "pack.yaml",
        "skill/SKILL.md",
    ]
    for rel in created:
        print(f"created {target.name}/{rel}")

    errors, warnings = validate_pack(target)
    if errors:
        error_details = "\n".join(f"  {err}" for err in errors)
        raise AstridError(
            f"packs new: scaffolded pack fails validation ({len(errors)} error(s))\n{error_details}",
            recovery_command="Fix the validation errors in the scaffolded pack files, then re-run: python3 -m astrid packs validate",
        )

    if warnings:
        for w in warnings:
            _eprint(f"warning: {w}")

    print(f"pack {pack_id!r} created and validated: {target}")
    return 0


def cmd_new(argv: list[str]) -> int:
    """Scaffold a minimal pack directory in the CWD.

    Usage: python3 -m astrid packs new <id>
    """
    parser = argparse.ArgumentParser(
        prog="python3 -m astrid packs new",
        description="Create a new pack skeleton in the current directory.",
    )
    parser.add_argument(
        "pack_id",
        help="Pack identifier (lowercase, digits, underscore; e.g., my_project).",
    )
    args = parser.parse_args(argv)
    return _create_pack_skeleton(args.pack_id)



# pack list
# ---------------------------------------------------------------------------


def _list_installed_packs() -> int:
    """Render the installed-pack list used by the public wrapper."""
    from astrid.core.pack_store import InstalledPackStore

    store = InstalledPackStore()
    records = store.list_installed()

    if not records:
        print("No packs installed.")
        return 0

    col_id = max(max(len(r.pack_id) for r in records), 2)
    col_name = max(max(len(r.name) for r in records), 4)
    col_version = max(max(len(r.version) for r in records), 7)
    col_status = 6
    col_installed = 19

    header = (
        f"{'ID':<{col_id}}  {'NAME':<{col_name}}  "
        f"{'VERSION':<{col_version}}  {'STATUS':<{col_status}}  "
        f"{'INSTALLED':<{col_installed}}"
    )
    print(header)
    print("-" * len(header))

    for record in records:
        status = "active" if record.active else "inactive"
        print(
            f"{record.pack_id:<{col_id}}  {record.name:<{col_name}}  "
            f"{record.version:<{col_version}}  {status:<{col_status}}  "
            f"{record.installed_at:<{col_installed}}"
        )

    return 0


def cmd_list(argv: list[str]) -> int:
    """List installed external packs.

    Usage: python3 -m astrid packs list
    """
    parser = argparse.ArgumentParser(
        prog="python3 -m astrid packs list",
        description="List installed external packs.",
    )
    parser.parse_args(argv)  # no arguments, just parses --help
    return _list_installed_packs()


# ---------------------------------------------------------------------------
# pack inspect
# ---------------------------------------------------------------------------


def _inspect_installed_pack(*, pack_id: str, agent: bool, json_output: bool) -> int:
    """Render installed-pack inspect output for the public wrapper and CLI."""
    from astrid.core.pack_store import InstalledPackStore

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


def build_parser() -> argparse.ArgumentParser:
    """Build the ``packs`` subcommand parser."""
    parser = RecoverableArgumentParser(
        prog="python3 -m astrid packs",
        description="Manage and validate Astrid packs.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser(
        "validate", help="Statically validate a pack directory."
    )
    validate_parser.add_argument(
        "path", nargs="?", default=".", help="Path to pack root (default: .)"
    )
    validate_parser.add_argument(
        "--warnings", action="store_true", help="Also print non-fatal warnings."
    )
    validate_parser.set_defaults(handler=_handle_validate)

    new_parser = subparsers.add_parser(
        "new", help="Create a new pack skeleton in the current directory."
    )
    new_parser.add_argument("pack_id", help="Pack identifier (e.g., my_project).")
    new_parser.set_defaults(handler=_handle_new)

    list_parser = subparsers.add_parser(
        "list", aliases=["ls"], help="List discovered packs."
    )
    list_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    list_parser.add_argument("--category", help="Filter by metadata.category.")
    _add_taxonomy_filter_args(list_parser)
    add_choice_arg(list_parser, "--status", values=("active", "deprecated", "stub", "experimental"), help="Filter by effective status.")
    add_choice_arg(list_parser, "--visibility", values=("visible", "hidden"), help="Filter by visibility.")
    list_parser.add_argument("--show-hidden", action="store_true", help="Include hidden packs.")
    list_parser.set_defaults(handler=_handle_list)

    inspect_parser = subparsers.add_parser(
        "inspect", help="Show details for an installed pack."
    )
    inspect_parser.add_argument("pack_id", help="Pack identifier to inspect.")
    inspect_parser.add_argument(
        "--agent", action="store_true",
        help="Emit agent-focused subset (purpose, entrypoints, constraints, context, secrets)."
    )
    inspect_parser.add_argument(
        "--json", action="store_true", dest="json",
        help="Output as JSON."
    )
    inspect_parser.set_defaults(handler=_handle_inspect)

    status_parser = subparsers.add_parser("status", help="Validate and summarize discovered packs.")
    status_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    status_parser.add_argument("--category", help="Filter by metadata.category.")
    _add_taxonomy_filter_args(status_parser)
    add_choice_arg(status_parser, "--status", values=("active", "deprecated", "stub", "experimental"), help="Filter by effective status.")
    add_choice_arg(status_parser, "--visibility", values=("visible", "hidden"), help="Filter by visibility.")
    status_parser.add_argument("--show-hidden", action="store_true", help="Include hidden packs.")
    status_parser.set_defaults(handler=_handle_status)

    # ── install ──
    install_parser = subparsers.add_parser(
        "install", help="Install a pack from a local directory or Git URL."
    )
    install_parser.add_argument(
        "source", help="Path to the pack source directory or a Git URL."
    )
    install_parser.add_argument(
        "--dry-run", action="store_true",
        help="Print trust summary without installing."
    )
    install_parser.add_argument(
        "--yes", "-y", action="store_true",
        help="Skip confirmation prompt."
    )
    install_parser.add_argument(
        "--trust", action="store_true",
        help="Acknowledge the pack trust summary for noninteractive installs."
    )
    install_parser.add_argument(
        "--force", action="store_true",
        help="Overwrite existing install (preserve old revision)."
    )
    install_parser.set_defaults(handler=_handle_install)

    # ── update ──
    update_parser = subparsers.add_parser(
        "update", help="Update an installed pack from its source."
    )
    update_parser.add_argument(
        "pack_id", help="Pack identifier to update."
    )
    update_parser.add_argument(
        "--dry-run", action="store_true",
        help="Print diff summary without updating."
    )
    update_parser.add_argument(
        "--yes", "-y", action="store_true",
        help="Skip confirmation prompt."
    )
    update_parser.add_argument(
        "--trust", action="store_true",
        help="Acknowledge the pack trust summary for noninteractive updates."
    )
    update_parser.set_defaults(handler=_handle_update)

    # ── uninstall ──
    uninstall_parser = subparsers.add_parser(
        "uninstall", help="Remove an installed pack."
    )
    uninstall_parser.add_argument(
        "pack_id", help="Pack identifier to uninstall."
    )
    uninstall_parser.add_argument(
        "--keep-revisions", action="store_true",
        help="Keep revision directories on disk."
    )
    uninstall_parser.add_argument(
        "--yes", "-y", action="store_true",
        help="Skip confirmation prompt."
    )
    uninstall_parser.set_defaults(handler=_handle_uninstall)

    # ── rollback ──
    rollback_parser = subparsers.add_parser(
        "rollback", help="Rollback an installed pack to a previous revision."
    )
    rollback_parser.add_argument(
        "pack_id", help="Pack identifier to rollback."
    )
    rollback_parser.add_argument(
        "--revision",
        help="Specific revision directory name to activate. "
        "If omitted, shows an interactive numbered list.",
    )
    rollback_parser.add_argument(
        "--yes", "-y", action="store_true",
        help="Skip confirmation prompt."
    )
    rollback_parser.set_defaults(handler=_handle_rollback)

    # ── agent-index ──
    agent_index_parser = subparsers.add_parser(
        "agent-index",
        help="Emit a machine-readable pack index for agents.",
    )
    agent_index_parser.add_argument(
        "--pack-id",
        help="Limit output to a single pack (returns the pack dict or null).",
    )
    agent_index_parser.add_argument(
        "--json", dest="json", action="store_true",
        help="Output as JSON (default).",
    )
    agent_index_parser.add_argument(
        "--text", dest="text_output", action="store_true",
        help="Output as a human-readable text table.",
    )
    agent_index_parser.set_defaults(handler=_handle_agent_index)

    # ── search ──
    search_parser = subparsers.add_parser(
        "search",
        help="Search packs by keyword/capability/purpose (ranked).",
    )
    search_parser.add_argument(
        "query",
        nargs="+",
        help="One or more search terms (matched against id, name, "
        "description, keywords, capabilities, and purpose).",
    )
    search_parser.add_argument(
        "--limit", type=int, default=20,
        help="Maximum results to show (default: 20; <=0 for all).",
    )
    search_parser.add_argument(
        "--json", action="store_true", help="Emit machine-readable JSON.",
    )
    search_parser.set_defaults(handler=_handle_search)

    return parser


def _handle_validate(args: argparse.Namespace) -> int:
    """Handler for ``packs validate``."""
    pack_root = _validate_pack_path(Path(args.path))
    errors, warnings = _validate_target(pack_root)

    if errors:
        raise AstridError(
            "\n".join(errors),
            recovery_command="Fix the validation errors listed above and re-run: python3 -m astrid packs validate",
        )

    if args.warnings and warnings:
        for warning in warnings:
            _eprint(f"warning: {warning}")

    resolved = pack_root.resolve()
    if is_first_party_packs_root_candidate(resolved):
        print(f"valid: {resolved} (19 first-party packs)")
    else:
        print(f"valid: {resolved}")
    return 0


def _handle_new(args: argparse.Namespace) -> int:
    """Handler for ``packs new``."""
    return _create_pack_skeleton(args.pack_id)


def _handle_list(args: argparse.Namespace) -> int:
    """Handler for ``packs list``."""
    packs = _filtered_packs(args)
    rows = [_pack_payload(pack) for pack in packs]
    if args.json:
        print(json.dumps(_with_grouped_payload(rows), indent=2, sort_keys=True))
        return 0
    _print_grouped_rows(rows, row_formatter=_format_list_row)
    return 0


def _handle_status(args: argparse.Namespace) -> int:
    """Handler for ``packs status``."""
    packs = _filtered_packs(args)
    rows: list[dict[str, Any]] = []
    for pack in packs:
        errors, warnings = validate_pack(pack.root)
        payload = _pack_payload(pack)
        payload["effective_status"] = _effective_status(pack)
        payload["validation"] = {
            "errors": len(errors),
            "warnings": len(warnings),
            "error_messages": errors,
            "warning_messages": warnings,
        }
        rows.append(payload)
    if args.json:
        print(json.dumps(_with_grouped_payload(rows), indent=2, sort_keys=True))
        return 0
    _print_grouped_rows(rows, row_formatter=_format_status_row)
    return 0


def _handle_inspect(args: argparse.Namespace) -> int:
    """Handler for ``packs inspect``."""
    from astrid.core.pack_store import InstalledPackStore

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


def _handle_install(args: argparse.Namespace) -> int:
    """Handler for ``packs install``."""
    from astrid.packs.install import _run_install_command

    return _run_install_command(args)


def _handle_update(args: argparse.Namespace) -> int:
    """Handler for ``packs update``."""
    from astrid.packs.install import _run_update_command

    return _run_update_command(args)


def _handle_uninstall(args: argparse.Namespace) -> int:
    """Handler for ``packs uninstall``."""
    from astrid.packs.install import _run_uninstall_command

    return _run_uninstall_command(args)


def _handle_rollback(args: argparse.Namespace) -> int:
    """Handler for ``packs rollback``."""
    from astrid.packs.install import _run_rollback_command

    return _run_rollback_command(args)


def _handle_agent_index(args: argparse.Namespace) -> int:
    """Handler for ``packs agent-index``."""

    from astrid.core.pack_store import InstalledPackStore
    from astrid.core.pack_machinery.agent_index import build_agent_index

    store = InstalledPackStore()

    pack_id = getattr(args, "pack_id", None)
    result = build_agent_index(store, pack_id=pack_id)

    if args.text_output:
        # Text table output
        if isinstance(result, dict) and "packs" in result:
            packs = result["packs"]
        elif isinstance(result, dict):
            packs = [result]  # single pack from --pack-id filter
        elif result is None:
            packs = []
        else:
            packs = [result]
        if not packs:
            print("(no packs found)")
            return 0
        for pack_entry in packs:
            pid = pack_entry.get("pack_id", "?")
            name = pack_entry.get("name", pid)
            version = pack_entry.get("version", "")
            purpose = pack_entry.get("purpose", "")
            source_type = pack_entry.get("source_type", "")
            normal_eps = pack_entry.get("normal_entrypoints", [])
            comp_counts = pack_entry.get("component_counts", {})
            secrets_cnt = len(pack_entry.get("secrets", []))

            print(f"━━━ {pid} ━━━")
            print(f"  Name:          {name}")
            if version:
                print(f"  Version:       {version}")
            print(f"  Source:        {source_type}")
            if purpose:
                print(f"  Purpose:       {purpose}")
            if normal_eps:
                print(f"  Entrypoints:   {', '.join(normal_eps)}")
            if comp_counts:
                parts = []
                for k in ("executors", "orchestrators", "elements"):
                    if comp_counts.get(k, 0):
                        parts.append(f"{comp_counts[k]} {k}")
                print(f"  Components:    {', '.join(parts)}")
            if secrets_cnt:
                print(f"  Secrets:       {secrets_cnt} declared")

            do_not = pack_entry.get("do_not_use_for")
            if do_not:
                print(f"  DoNotUseFor:   {do_not}")

            req_ctx = pack_entry.get("required_context", [])
            if req_ctx:
                print(f"  Req. Context:  {', '.join(req_ctx)}")

            keywords = pack_entry.get("keywords", [])
            if keywords:
                print(f"  Keywords:      {', '.join(keywords)}")

            capabilities = pack_entry.get("capabilities", [])
            if capabilities:
                print(f"  Capabilities:  {', '.join(capabilities)}")

            deps = pack_entry.get("dependencies", {})
            if deps:
                dep_parts = []
                for eco, pkg_list in deps.items():
                    if pkg_list:
                        dep_parts.append(f"{eco}:{','.join(pkg_list)}")
                if dep_parts:
                    print(f"  Dependencies:  {'; '.join(dep_parts)}")

            components = pack_entry.get("components", [])
            if components:
                print(f"  Components:    ({len(components)} total)")
                for comp in components:
                    ep_mark = " [ENTRYPOINT]" if comp.get("is_entrypoint") else ""
                    desc = comp.get("description", "")[:80]
                    print(f"    • {comp['id']} ({comp.get('kind', '?')}){ep_mark}: {desc}")

            warnings = pack_entry.get("warnings", [])
            if warnings:
                print("  ⚠ Warnings:")
                for w in warnings:
                    print(f"    • {w}")
            print()  # blank line between packs
    else:
        # JSON output (default)
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")

    return 0


# ---------------------------------------------------------------------------
# pack search
# ---------------------------------------------------------------------------

# Per-field weights for ranking a query term against a pack. Keyword and
# capability hits are the strongest signal (authored for discovery); id/name
# next; purpose/description are softer free-text matches. do_not_use_for is
# deliberately excluded so negative guidance never yields a positive match.
_SEARCH_FIELD_WEIGHTS = (
    ("keywords", 3.0),
    ("capabilities", 3.0),
    ("pack_id", 2.0),
    ("name", 2.0),
    ("purpose", 1.5),
    ("description", 1.0),
)


def _pack_search_text(pack: dict[str, Any], field: str) -> str:
    """Return lowercased searchable text for *field* of an agent-index entry."""
    value = pack.get(field)
    if isinstance(value, (list, tuple)):
        return " ".join(str(v) for v in value).lower()
    return str(value or "").lower()


def _score_pack(pack: dict[str, Any], terms: list[str]) -> float:
    """Score *pack* against query *terms*; 0.0 means no match.

    Every term must hit at least one field (AND semantics); a single
    unmatched term drops the pack, keeping multi-word queries precise
    rather than returning anything that matches one common word.
    """
    total = 0.0
    for term in terms:
        best = 0.0
        for field, weight in _SEARCH_FIELD_WEIGHTS:
            if term in _pack_search_text(pack, field):
                best = max(best, weight)
        if best == 0.0:
            return 0.0
        total += best
    return total


def _handle_search(args: argparse.Namespace) -> int:
    """Handler for ``packs search``."""
    from astrid.core.pack_store import InstalledPackStore
    from astrid.core.pack_machinery.agent_index import build_agent_index

    terms = [t.lower() for t in args.query if t.strip()]
    if not terms:
        print("search: empty query", file=sys.stderr)
        return 2

    index = build_agent_index(InstalledPackStore())
    packs = index.get("packs", []) if isinstance(index, dict) else []

    scored = [
        (score, pack)
        for pack in packs
        if (score := _score_pack(pack, terms)) > 0.0
    ]
    scored.sort(key=lambda sp: (-sp[0], str(sp[1].get("pack_id", ""))))

    total = len(scored)
    limit = args.limit if args.limit and args.limit > 0 else total
    shown = scored[:limit]

    if args.json:
        payload = {
            "query": terms,
            "total": total,
            "shown": len(shown),
            "packs": [
                {**pack, "search_score": round(score, 2)}
                for score, pack in shown
            ],
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    if not shown:
        print(f"No packs match: {' '.join(terms)}")
        return 0

    for score, pack in shown:
        summary = pack.get("purpose") or pack.get("description") or ""
        keywords = pack.get("keywords") or []
        kw = ", ".join(str(k) for k in keywords[:6])
        line = f"{pack.get('pack_id', '?')}\t{score:g}\t{summary}"
        if kw:
            line += f"\t[{kw}]"
        print(line)

    if total > len(shown):
        print(
            f"\n# showing top {len(shown)} of {total} matches — "
            f"add terms to narrow, or pass --limit to see more"
        )
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    """Entry point for ``astrid packs`` CLI.

    Args:
        argv: Command-line arguments (excluding the ``packs`` verb).
              If None, reads from sys.argv[1:].

    Returns:
        Exit code (0 on success).
    """
    if argv is None:
        argv = sys.argv[1:]

    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        # argparse exits on --help or parse errors
        return int(exc.code) if exc.code is not None else 2

    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_usage(file=sys.stderr)
        return 2

    try:
        return int(handler(args))
    except AstridError as exc:
        from astrid.contracts.errors import render_astrid_error

        return render_astrid_error(exc)


__all__ = [
    # Public API
    "build_parser",
    "cmd_inspect",
    "cmd_list",
    "cmd_new",
    "cmd_validate",
    "main",
    # Re-exported for backward compatibility — used by tests that mock
    # through the astrid.packs.cli shim path.
    "extract_trust_summary",  # imported from validate, tests access via cli
    "validate_pack",  # imported from validate, available via cli namespace
    "_PACK_ID_RE",
    "_SKILL_MD_STUB",
    "_TAXONOMY_FIELDS",
    "_INSPECT_COMPONENT_MANIFEST_NAMES",
    "_SEARCH_FIELD_WEIGHTS",
    "_add_taxonomy_filter_args",
    "_build_agent_view",
    "_build_full_inspect",
    "_create_pack_skeleton",
    "_effective_status",
    "_eprint",
    "_filtered_packs",
    "_find_component_manifest",
    "_format_list_row",
    "_format_status_row",
    "_group_packs_by_domain",
    "_handle_agent_index",
    "_handle_install",
    "_handle_inspect",
    "_handle_list",
    "_handle_new",
    "_handle_rollback",
    "_handle_search",
    "_handle_status",
    "_handle_uninstall",
    "_handle_update",
    "_handle_validate",
    "_inspect_discovered_pack",
    "_inspect_installed_pack",
    "_list_installed_packs",
    "_matches_taxonomy_filters",
    "_pack_category",
    "_pack_id_is_valid",
    "_pack_payload",
    "_pack_search_text",
    "_pack_taxonomy",
    "_print_agent_view",
    "_print_full_inspect",
    "_print_grouped_rows",
    "_print_taxonomy_block",
    "_read_stage_excerpt",
    "_scan_inspect_components",
    "_score_pack",
    "_taxonomy_filters",
    "_validate_pack_path",
    "_with_grouped_payload",
]

if __name__ == "__main__":
    raise SystemExit(main())
