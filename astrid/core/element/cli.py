"""Command-line interface for Astrid elements."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

from astrid.core.contracts.errors import AstridError
from astrid.core.pack.override import OverrideStore, OverrideStoreError
from astrid.core.search import (
    SearchRecord,
    short_description_or_truncated,
)
from astrid.core.search import (
    search as run_search,
)

from .registry import ElementRegistryError, load_default_registry
from .schema import ElementDefinition, ElementValidationError, to_capability_handle


# Shared stderr sink for override-management diagnostics.
def _eprint(*args: object) -> None:
    print(*args, file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        # Create OverrideStore so --show-overrides works.
        project_root = _project_root_from_args(args)
        override_store = OverrideStore(project_root=project_root)
        registry = load_default_registry(
            active_theme=args.theme,
            project_root=project_root,
            extra_pack_roots=tuple(args.pack_root),
        )
        _normalize_kind_args(args, registry)
        registry.override_store = override_store
        return int(args.handler(args, registry))
    except (KeyError, ElementRegistryError, ElementValidationError, ValueError, OverrideStoreError) as exc:
        raise AstridError(str(exc)) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m astrid elements",
        description="List, inspect, and validate Astrid render elements.",
    )
    parser.add_argument("--theme", help="Active theme id, theme directory, or path to theme.json.")
    parser.add_argument("--project-root", type=Path, help="Project root for local pack discovery. Defaults to current working directory.")
    parser.add_argument("--pack-root", action="append", default=[], metavar="PATH", help="Extra pack root directory to discover elements from; may be repeated.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    list_parser = subparsers.add_parser("list", aliases=["ls"], help="List available elements.")
    list_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    list_parser.add_argument("--kind", help="Filter by element kind.")
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
    inspect_parser.add_argument("kind")
    inspect_parser.add_argument("element_id")
    inspect_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    inspect_parser.add_argument("--pack", help="Require the resolved element to belong to this pack id.")
    inspect_parser.add_argument("--show-overrides", action="store_true", help="Show override status for this capability.")
    inspect_parser.set_defaults(handler=_cmd_inspect)

    validate_parser = subparsers.add_parser("validate", help="Validate element metadata.")
    validate_parser.add_argument("kind", nargs="?")
    validate_parser.add_argument("element_id", nargs="?")
    validate_parser.set_defaults(handler=_cmd_validate)

    return parser


def _normalize_kind_args(args: argparse.Namespace, registry: Any) -> None:
    kind_attrs = (
        "kind",
    )
    kind_registry = registry.element_kind_registry
    for attr in kind_attrs:
        value = getattr(args, attr, None)
        if value is None:
            continue
        setattr(args, attr, kind_registry.normalize(value, error_cls=ElementRegistryError))


def _project_root_from_args(args: argparse.Namespace) -> Path:
    return getattr(args, "project_root", None) or Path.cwd()


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




if __name__ == "__main__":
    raise SystemExit(main())
