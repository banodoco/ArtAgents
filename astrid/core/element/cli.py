"""Command-line interface for Astrid elements."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

from astrid._paths import REPO_ROOT
from astrid.core._search import (
    SearchRecord,
    search as run_search,
    short_description_or_truncated,
)
from astrid.core.dirty import detect_local_edits
from astrid.core.override import OverrideStore, OverrideStoreError
from astrid.core.update import update_check, update_apply

from .install import install_element
from .registry import ElementRegistryError, load_default_registry
from .schema import ELEMENT_KINDS, ElementDefinition, ElementValidationError, to_capability_handle


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        # Create OverrideStore so --show-overrides and override set/remove/list work.
        override_store = OverrideStore(project_root=REPO_ROOT)
        registry = load_default_registry(active_theme=args.theme, project_root=REPO_ROOT)
        registry.override_store = override_store
        return int(args.handler(args, registry))
    except (KeyError, ElementRegistryError, ElementValidationError, ValueError, OverrideStoreError) as exc:
        print(f"elements: {exc}", file=sys.stderr)
        return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m astrid elements",
        description="List, inspect, validate, fork, and install Astrid render elements.",
    )
    parser.add_argument("--theme", help="Active theme id, theme directory, or path to theme.json.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List available elements.")
    list_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    list_parser.add_argument("--kind", choices=ELEMENT_KINDS, help="Filter by element kind.")
    list_parser.add_argument("--pack", help="Filter elements by pack id.")
    list_parser.add_argument("--no-describe", action="store_true", help="Omit the short_description column for legacy parsers.")
    list_parser.add_argument("--show-overrides", action="store_true", help="Annotate capabilities with active overrides.")
    list_parser.set_defaults(handler=_cmd_list)

    search_parser = subparsers.add_parser("search", help="Search elements by id, keywords, and descriptions.")
    search_parser.add_argument("terms", nargs="+", help="One or more search terms.")
    search_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    search_parser.add_argument("--limit", type=int, default=25, help="Maximum number of hits (default 25).")
    search_parser.add_argument("--pack", help="Filter elements by pack id.")
    search_parser.set_defaults(handler=_cmd_search)

    inspect_parser = subparsers.add_parser("inspect", help="Inspect one element.")
    inspect_parser.add_argument("kind", choices=ELEMENT_KINDS)
    inspect_parser.add_argument("element_id")
    inspect_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    inspect_parser.add_argument("--pack", help="Require the resolved element to belong to this pack id.")
    inspect_parser.add_argument("--show-overrides", action="store_true", help="Show override status for this capability.")
    inspect_parser.set_defaults(handler=_cmd_inspect)

    validate_parser = subparsers.add_parser("validate", help="Validate element metadata.")
    validate_parser.add_argument("kind", choices=ELEMENT_KINDS, nargs="?")
    validate_parser.add_argument("element_id", nargs="?")
    validate_parser.set_defaults(handler=_cmd_validate)

    fork_parser = subparsers.add_parser("fork", help="Fork an element into the local pack (astrid/packs/local).")
    fork_parser.add_argument("kind", choices=ELEMENT_KINDS)
    fork_parser.add_argument("element_id")
    fork_parser.add_argument("--overwrite", action="store_true", help="Replace an existing local fork.")
    fork_parser.set_defaults(handler=_cmd_fork)

    install_parser = subparsers.add_parser("install", help="Plan or apply local dependency install for one element.")
    install_parser.add_argument("kind", choices=ELEMENT_KINDS)
    install_parser.add_argument("element_id")
    install_parser.add_argument("--apply", action="store_true", help="Run the local install commands. Default is dry-run.")
    install_parser.set_defaults(handler=_cmd_install)

    # --- Override subcommands ---
    override_parser = subparsers.add_parser("override", help="Manage capability overrides.")
    override_sub = override_parser.add_subparsers(dest="override_action", required=True)

    override_set = override_sub.add_parser("set", help="Set an override: route a capability to a replacement.")
    override_set.add_argument("kind", choices=ELEMENT_KINDS)
    override_set.add_argument("element_id")
    override_set.add_argument("target_id", help="Fully-qualified id of the replacement capability.")
    override_set.set_defaults(handler=_cmd_override)

    override_remove = override_sub.add_parser("remove", help="Remove an override.")
    override_remove.add_argument("kind", choices=ELEMENT_KINDS)
    override_remove.add_argument("element_id")
    override_remove.set_defaults(handler=_cmd_override)

    override_list = override_sub.add_parser("list", help="List all active overrides.")
    override_list.set_defaults(handler=_cmd_override)

    # --- Dirty subcommands ---
    dirty_parser = subparsers.add_parser("dirty", help="Check or list locally-modified (dirty) capabilities.")
    dirty_sub = dirty_parser.add_subparsers(dest="dirty_action", required=True)

    dirty_check = dirty_sub.add_parser("check", help="Check dirty state for one element.")
    dirty_check.add_argument("kind", choices=ELEMENT_KINDS)
    dirty_check.add_argument("element_id")
    dirty_check.set_defaults(handler=_cmd_dirty)

    dirty_list = dirty_sub.add_parser("list", help="List all dirty capabilities.")
    dirty_list.set_defaults(handler=_cmd_dirty)

    # --- Update subcommands ---
    update_parser = subparsers.add_parser("update", help="Check for or apply upstream updates to forked capabilities.")
    update_sub = update_parser.add_subparsers(dest="update_action", required=True)

    update_check_parser = update_sub.add_parser("check", help="Compare local fork against upstream.")
    update_check_parser.add_argument("kind", choices=ELEMENT_KINDS)
    update_check_parser.add_argument("element_id")
    update_check_parser.set_defaults(handler=_cmd_update)

    update_apply_parser = update_sub.add_parser("apply", help="Apply upstream update to a local fork.")
    update_apply_parser.add_argument("kind", choices=ELEMENT_KINDS)
    update_apply_parser.add_argument("element_id")
    update_apply_parser.add_argument("--force", action="store_true", help="Apply even if safety escalations are detected.")
    update_apply_parser.add_argument("--skip-safety", action="store_true", help="Skip safety escalation checks.")
    update_apply_parser.set_defaults(handler=_cmd_update)

    return parser


def _cmd_list(args: argparse.Namespace, registry: Any) -> int:
    elements = _filter_by_pack(registry.list(kind=args.kind), getattr(args, "pack", None))
    show_overrides = bool(getattr(args, "show_overrides", False))
    if args.json:
        result = []
        for item in elements:
            handle = to_capability_handle(item)
            entry = {'_capability': handle.to_dict(), 'pack_id': _element_pack_id(item), **item.to_dict()}
            if show_overrides and registry.override_store is not None:
                override_target = registry.override_store.resolve(item.kind, item.id)
                entry['_override'] = override_target
            result.append(entry)
        print(json.dumps({'elements': result}, indent=2, sort_keys=True))
        return 0
    no_describe = bool(getattr(args, "no_describe", False))
    for element in elements:
        editability = "editable" if element.editable else "managed"
        override_tag = ""
        if show_overrides and registry.override_store is not None:
            target = registry.override_store.resolve(element.kind, element.id)
            if target is not None:
                override_tag = f"\t→ {target}"
        if no_describe:
            print(f"{element.kind}\t{element.id}\t{element.source}\t{editability}{override_tag}")
        else:
            short = short_description_or_truncated(element.short_description, element.description)
            print(f"{element.kind}\t{element.id}\t{element.source}\t{editability}\t{short}{override_tag}")
    return 0


def _cmd_search(args: argparse.Namespace, registry: Any) -> int:
    records = [_element_search_record(element) for element in _filter_by_pack(registry.list(), getattr(args, "pack", None))]
    hits = run_search(records, list(args.terms), limit=int(args.limit))
    if args.json:
        payload = [
            {
                "id": hit.record.id,
                "kind": hit.record.kind,
                "score": round(hit.score, 3),
                "short_description": hit.record.short_description,
            }
            for hit in hits
        ]
        print(json.dumps({"hits": payload}, indent=2, sort_keys=True))
        return 0
    for hit in hits:
        print(f"{hit.score:.2f}\t{hit.record.id}\t{hit.record.kind}\t{hit.record.short_description}")
    return 0


def _element_search_record(element: ElementDefinition) -> SearchRecord:
    short = short_description_or_truncated(element.short_description, element.description)
    fields = {
        "id": element.id,
        "name": str(element.metadata.get("name") or element.metadata.get("label") or element.id),
        "short_description": element.short_description,
        "description": element.description,
        "keywords": " ".join(element.keywords),
        "pack_id": str(element.metadata.get("pack_id") or ""),
        "version": str(element.metadata.get("version") or ""),
        "category": str(element.metadata.get("category") or element.kind),
    }
    return SearchRecord(id=element.id, kind=element.kind, short_description=short, fields=fields)


def _cmd_inspect(args: argparse.Namespace, registry: Any) -> int:
    # Resolve element_id before registry.get(kind, resolved_id).
    resolver = registry.alias_resolver
    resolved_id = resolver.resolve(args.element_id) if resolver else args.element_id
    element = registry.get(args.kind, resolved_id)
    _require_pack_match(element, getattr(args, "pack", None))
    show_overrides = bool(getattr(args, "show_overrides", False))
    if args.json:
        handle = to_capability_handle(element)
        if resolver is not None:
            aliases = resolver.get_aliases_for(resolved_id)
            handle = replace(handle, aliases=tuple(aliases))
        result = {"_capability": handle.to_dict(), **element.to_dict()}
        if show_overrides and registry.override_store is not None:
            result["_override"] = registry.override_store.resolve(element.kind, element.id)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    print(f"id: {element.id}")
    print(f"kind: {element.kind}")
    print(f"source: {element.source}")
    print(f"editable: {str(element.editable).lower()}")
    print(f"root: {element.root}")
    print(f"fork_target: {element.fork_target}")
    if element.short_description:
        print(f"short_description: {element.short_description}")
    if element.description:
        print(f"description: {element.description}")
    if element.keywords:
        print(f"keywords: {', '.join(element.keywords)}")
    if show_overrides and registry.override_store is not None:
        target = registry.override_store.resolve(element.kind, element.id)
        if target is not None:
            print(f"override: {element.kind}/{element.id} → {target}")
        else:
            print("override: none")
    return 0


def _element_pack_id(element: ElementDefinition) -> str:
    return str(element.metadata.get("pack_id") or "")


def _filter_by_pack(elements: list[ElementDefinition], pack_id: str | None) -> list[ElementDefinition]:
    if not pack_id:
        return elements
    return [element for element in elements if _element_pack_id(element) == pack_id]


def _require_pack_match(element: ElementDefinition, pack_id: str | None) -> None:
    if pack_id and _element_pack_id(element) != pack_id:
        raise ValueError(f"element {element.kind}/{element.id!r} does not belong to pack {pack_id!r}")


def _cmd_validate(args: argparse.Namespace, registry: Any) -> int:
    if args.kind and args.element_id:
        registry.get(args.kind, args.element_id)
        print(f"{args.kind}/{args.element_id}: ok")
        return 0
    elements = registry.list(kind=args.kind)
    print(f"{len(elements)} element(s): ok")
    return 0


def _cmd_fork(args: argparse.Namespace, registry: Any) -> int:
    # SD2: Element CLI forks to REPO_ROOT by default so forked elements
    # land alongside installed source-tree packs. Executor/orchestrator
    # CLIs fork to Path.cwd() by default — this asymmetry is intentional
    # because elements are source-tree capabilities while
    # executors/orchestrators are project-scoped.
    target = registry.fork(args.kind, args.element_id, project_root=REPO_ROOT, overwrite=bool(args.overwrite))
    print(f"forked: {target}")
    return 0


def _cmd_install(args: argparse.Namespace, registry: Any) -> int:
    element = registry.get(args.kind, args.element_id)
    result = install_element(element, project_root=REPO_ROOT, dry_run=not bool(args.apply))
    plan = result.plan
    if plan.noop_reason:
        print(f"{element.kind}/{element.id}: no install needed: {plan.noop_reason}")
        return result.returncode
    print(f"root: {plan.root}")
    if plan.venv_path is not None:
        print(f"venv: {plan.venv_path}")
    if plan.node_prefix is not None:
        print(f"node: {plan.node_prefix}")
    for line in plan.command_lines():
        print(line)
    if not args.apply:
        print("dry-run: pass --apply to run these local install commands")
    return result.returncode


def _cmd_override(args: argparse.Namespace, registry: Any) -> int:
    store = registry.override_store
    if store is None:
        print("elements: override store not available", file=sys.stderr)
        return 1
    action = getattr(args, "override_action", None)
    if action == "set":
        store.set_override(args.kind, args.element_id, args.target_id)
        print(f"override set: {args.kind}/{args.element_id} → {args.target_id}")
    elif action == "remove":
        store.remove_override(args.kind, args.element_id)
        print(f"override removed: {args.kind}/{args.element_id}")
    elif action == "list":
        overrides = store.list_overrides()
        if not overrides:
            print("no overrides")
            return 0
        for override_type, mappings in sorted(overrides.items()):
            for override_id, target in sorted(mappings.items()):
                print(f"{override_type}/{override_id} → {target}")
    else:
        print(f"elements override: unknown action {action!r}", file=sys.stderr)
        return 2
    return 0


def _cmd_dirty(args: argparse.Namespace, registry: Any) -> int:
    action = getattr(args, "dirty_action", None)
    if action == "check":
        element = registry.get(args.kind, args.element_id)
        content_root = element.metadata.get("content_root")
        if content_root is None:
            content_root = element.root
        forked_from = str(element.metadata.get("forked_from") or "")
        state = detect_local_edits(content_root, forked_from=forked_from)
        print(f"{element.kind}/{element.id}: {state}")
    elif action == "list":
        dirty_found = 0
        for element in registry.list():
            content_root = element.metadata.get("content_root")
            if content_root is None:
                content_root = element.root
            forked_from = str(element.metadata.get("forked_from") or "")
            state = detect_local_edits(content_root, forked_from=forked_from)
            if state != "clean":
                print(f"{element.kind}/{element.id}: {state}")
                dirty_found += 1
        if dirty_found == 0:
            print("no dirty capabilities")
    else:
        print(f"elements dirty: unknown action {action!r}", file=sys.stderr)
        return 2
    return 0


def _cmd_update(args: argparse.Namespace, registry: Any) -> int:
    action = getattr(args, "update_action", None)
    element_id = f"{args.kind}/{args.element_id}"
    if action == "check":
        report = update_check(
            args.element_id, registry,
            capability_type="element", capability_kind=args.kind,
        )
        print(report["report"])
        return 0
    elif action == "apply":
        force = bool(getattr(args, "force", False))
        skip_safety = bool(getattr(args, "skip_safety", False))
        report = update_apply(
            args.element_id, registry,
            force=force, skip_safety=skip_safety,
            capability_type="element", capability_kind=args.kind,
        )
        print(report["report"])
        return 0 if report.get("applied") else 1
    else:
        print(f"elements update: unknown action {action!r}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
