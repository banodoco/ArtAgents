#!/usr/bin/env python3
"""Generate the Remotion effect registry from workspace and active-theme plugins."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

TOOLS_DIR = Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from astrid.core.element.registry import ElementRegistry, load_default_registry
from astrid.core.element.schema import ELEMENT_MANIFEST_NAMES, ElementDefinition

WORKSPACE_ROOT = TOOLS_DIR.parent
THEMES_ROOT = WORKSPACE_ROOT / "themes"
REMOTION_SRC = TOOLS_DIR / "remotion" / "src"
# Sprint 5: composition source moved into
# packages/timeline-composition. The codegen now writes the generated
# registries directly into the package source so the package is the
# single owner of its own runtime tables. The in-tree shell at
# tools/remotion/ keeps a re-export shim (effects.generated.ts) for
# back-compat with tests that imported from the old location.
PACKAGE_SRC = Path(
    os.environ.get(
        "ASTRID_TIMELINE_COMPOSITION_SRC",
        str(WORKSPACE_ROOT / "packages" / "timeline-composition" / "typescript" / "src"),
    )
)
OUTPUT = PACKAGE_SRC / "effects.generated.ts"
OUTPUTS = {
    "effects": PACKAGE_SRC / "effects.generated.ts",
    "animations": PACKAGE_SRC / "animations.generated.ts",
    "transitions": PACKAGE_SRC / "transitions.generated.ts",
}
# Shim files in the in-tree shell that re-export from the package, so
# any pre-Sprint-5 callers that still imported the in-tree path resolve.
SHIM_OUTPUTS = {
    "effects": REMOTION_SRC / "effects.generated.ts",
    "animations": REMOTION_SRC / "animations.generated.ts",
    "transitions": REMOTION_SRC / "transitions.generated.ts",
}
SHIM_EXTENSIONS = (".ts", ".js", ".d.ts", ".js.map", ".d.ts.map")
ACTIVE_THEME_LINK = TOOLS_DIR / "remotion" / "_active_theme"
ACTIVE_THEME_POINTER = TOOLS_DIR / "remotion" / "_active_theme.txt"
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")

ElementKind = Literal["effects", "animations", "transitions"]
REGISTRY_STATE_VERSION = 1


@dataclass(frozen=True)
class PluginRecord:
    plugin_id: str
    kind: ElementKind
    scope: str
    root: Path
    meta: dict[str, Any]
    defaults: dict[str, Any]
    fingerprint: str
    import_scope: str | None = None


EffectRecord = PluginRecord


def _component_name(plugin_id: str) -> str:
    return "".join(part.capitalize() for part in plugin_id.split("-"))


def _resolve_theme_dir(theme: str | None) -> Path | None:
    if theme is None:
        return None
    candidate = Path(theme)
    if candidate.name == "theme.json":
        return candidate.parent.resolve()
    if candidate.exists():
        return (candidate if candidate.is_dir() else candidate.parent).resolve()
    return (THEMES_ROOT / theme).resolve()


def _theme_id(theme_dir: Path | None) -> str | None:
    return theme_dir.name if theme_dir is not None else None


def _validate_kind(kind: str) -> None:
    if kind not in {"effects", "animations", "transitions"}:
        raise ValueError(f"Invalid element kind {kind!r}")


def _singular(kind: ElementKind) -> str:
    return kind[:-1]


def _constant_prefix(kind: ElementKind) -> str:
    return _singular(kind).upper()


def _type_name(kind: ElementKind) -> str:
    return f"{_singular(kind).capitalize()}Id"


def _registry_name(kind: ElementKind) -> str:
    return f"{_constant_prefix(kind)}_REGISTRY"


def _ids_name(kind: ElementKind) -> str:
    return f"{_constant_prefix(kind)}_IDS"


def _workspace_root(kind: ElementKind) -> Path:
    _validate_kind(kind)
    return WORKSPACE_ROOT / kind


def discover_plugins(
    kind: ElementKind,
    theme_dir: Path | None = None,
    *,
    include_local: bool = True,
) -> dict[str, PluginRecord]:
    _validate_kind(kind)
    registry = _element_registry(theme_dir)
    plugins: dict[str, PluginRecord] = {}
    singular = _singular(kind)
    for conflict in registry.conflicts():
        if conflict.kind == kind and conflict.winner.source == "active_theme":
            print(
                f"WARN theme '{_theme_id(theme_dir) or _theme_id_from_element(conflict.winner) or 'unknown'}' overrides workspace {singular} '{conflict.id}'",
                file=sys.stderr,
            )
    if include_local:
        elements = registry.list(kind=kind)
    else:
        elements = tuple(
            definitions[0]
            for (item_kind, _), definitions in registry._entries.items()
            if item_kind == kind
            for definitions in [
                [element for element in definitions if element.source != "pack:local"]
            ]
            if definitions
        )
    for element in elements:
        plugins[element.id] = _plugin_from_element(element, theme_dir=theme_dir)
    return plugins


def discover_effects(
    theme_dir: Path | None = None,
    *,
    include_local: bool = True,
) -> dict[str, EffectRecord]:
    return discover_plugins("effects", theme_dir, include_local=include_local)


def discover_animations(
    theme_dir: Path | None = None,
    *,
    include_local: bool = True,
) -> dict[str, PluginRecord]:
    return discover_plugins("animations", theme_dir, include_local=include_local)


def discover_transitions(
    theme_dir: Path | None = None,
    *,
    include_local: bool = True,
) -> dict[str, PluginRecord]:
    return discover_plugins("transitions", theme_dir, include_local=include_local)


def _import_path(plugin: PluginRecord) -> str:
    scope = plugin.import_scope or plugin.scope
    return f"@{scope}-{plugin.kind}/{plugin.plugin_id}/component?astrid={plugin.fingerprint[:12]}"


def _element_registry(theme_dir: Path | None) -> ElementRegistry:
    return load_default_registry(active_theme=theme_dir, project_root=TOOLS_DIR)


def _plugin_from_element(element: ElementDefinition, *, theme_dir: Path | None) -> PluginRecord:
    return PluginRecord(
        plugin_id=element.id,
        kind=element.kind,
        scope=element.source,
        root=element.root,
        meta=element.metadata,
        defaults=element.defaults,
        fingerprint=_fingerprint_element(element),
        import_scope=_import_scope_for_element(element, theme_dir=theme_dir),
    )


def _fingerprint_element(element: ElementDefinition) -> str:
    root = element.root.resolve()
    files: dict[str, Path] = {}

    manifest_path = _manifest_path(root)
    if manifest_path is not None:
        files[_fingerprint_key("manifest", manifest_path.relative_to(root))] = manifest_path

    component_path = element.component
    if not component_path.is_absolute():
        component_path = root / component_path
    if component_path.is_file():
        files[_fingerprint_key("component", component_path.resolve().relative_to(root))] = component_path.resolve()

    for suffix in (".ts", ".tsx", ".css"):
        for support_path in root.rglob(f"*{suffix}"):
            if support_path.is_file():
                files[_fingerprint_key("support", support_path.resolve().relative_to(root))] = support_path.resolve()

    for asset in element.assets:
        asset_path = (root / asset.path).resolve()
        if asset_path.is_file():
            files[_fingerprint_key(f"asset:{asset.name}", asset.path)] = asset_path

    digest = hashlib.sha256()
    digest.update(b"astrid-element-fingerprint-v1\n")
    digest.update(f"{element.kind}/{element.id}\n".encode("utf-8"))
    for key in sorted(files):
        digest.update(key.encode("utf-8"))
        digest.update(b"\0")
        digest.update(files[key].read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _manifest_path(root: Path) -> Path | None:
    for name in ELEMENT_MANIFEST_NAMES:
        candidate = root / name
        if candidate.is_file():
            return candidate.resolve()
    return None


def _fingerprint_key(role: str, path: Path) -> str:
    return f"{role}:{path.as_posix()}"


def _import_scope_for_element(element: ElementDefinition, *, theme_dir: Path | None) -> str:
    if element.source == "active_theme":
        if theme_dir is not None:
            theme_elements = theme_dir / "elements" / element.kind / element.id
            if element.root == theme_elements.resolve():
                return "theme-elements"
        return "theme"
    if element.source == "overrides":
        return "override-elements"
    if element.source == "managed":
        return "managed-elements"
    if element.source.startswith("pack:"):
        return f"pack-{element.source.split(':', 1)[1]}-elements"
    return "managed-elements"


def _theme_id_from_element(element: ElementDefinition) -> str | None:
    if element.source != "active_theme":
        return None
    if element.root.parent.parent.name == "elements":
        return element.root.parent.parent.parent.name
    return element.root.parent.parent.name


def _clip_type_aliases(effects: dict[str, EffectRecord]) -> dict[str, str]:
    aliases: dict[str, str] = {}
    if "text-card" in effects:
        aliases["text"] = "text-card"
    for effect_id, effect in effects.items():
        raw_aliases = effect.meta.get("clipTypeAliases")
        if isinstance(raw_aliases, list):
            for alias in raw_aliases:
                if isinstance(alias, str) and alias:
                    aliases[alias] = effect_id
    return dict(sorted(aliases.items()))


def _ts_string(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _ts_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _ts_property_key(value: str) -> str:
    return value if re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", value) else _ts_string(value)


def _write_active_theme_pointer(theme_dir: Path | None) -> None:
    if theme_dir is None:
        if ACTIVE_THEME_LINK.is_symlink() or ACTIVE_THEME_LINK.is_file():
            ACTIVE_THEME_LINK.unlink()
        if ACTIVE_THEME_POINTER.exists():
            ACTIVE_THEME_POINTER.unlink()
        return

    if os.name == "nt":
        ACTIVE_THEME_POINTER.write_text(str(theme_dir.resolve()) + "\n", encoding="utf-8")
        return

    if ACTIVE_THEME_POINTER.exists():
        ACTIVE_THEME_POINTER.unlink()
    if ACTIVE_THEME_LINK.is_symlink() or ACTIVE_THEME_LINK.is_file():
        ACTIVE_THEME_LINK.unlink()
    elif ACTIVE_THEME_LINK.exists():
        raise RuntimeError(f"{ACTIVE_THEME_LINK} exists and is not a symlink")
    ACTIVE_THEME_LINK.symlink_to(theme_dir.resolve(), target_is_directory=True)


def _shim_module_text(kind: ElementKind, *, extension: str) -> str:
    package_module = f"@banodoco/timeline-composition/typescript/src/{kind}.generated"
    if extension in {".ts", ".js"}:
        return (
            "// DO NOT EDIT - generated shim by tools/scripts/gen_effect_registry.py\n"
            "// Re-exports the package-owned registry.\n"
            f"export * from '{package_module}';\n"
        )
    if extension == ".d.ts":
        return (
            "// DO NOT EDIT - generated shim by tools/scripts/gen_effect_registry.py\n"
            f"export * from '{package_module}';\n"
            f"//# sourceMappingURL={kind}.generated.d.ts.map\n"
        )
    raise ValueError(f"unsupported shim extension: {extension}")


def _empty_source_map(path: Path) -> str:
    return json.dumps(
        {"version": 3, "file": path.name, "sources": [], "names": [], "mappings": ""},
        sort_keys=True,
    ) + "\n"


def _write_shim_family(kind: ElementKind, shim_ts: Path) -> None:
    shim_ts.parent.mkdir(parents=True, exist_ok=True)
    base = shim_ts.with_suffix("")
    for extension in SHIM_EXTENSIONS:
        path = Path(f"{base}{extension}")
        if extension.endswith(".map"):
            path.write_text(_empty_source_map(path), encoding="utf-8")
        else:
            path.write_text(_shim_module_text(kind, extension=extension), encoding="utf-8")


def _write_generated_registry(path: Path, content: str) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_text(content, encoding="utf-8")
    except PermissionError:
        return False
    return True


def compute_generated_registry_state(
    *,
    theme_dir: Path | None = None,
    include_local: bool = True,
) -> dict[str, Any]:
    """Return a deterministic fingerprint of the generated registry sources."""
    generated = {
        kind: generate_element_registry(kind, theme_dir=theme_dir, include_local=include_local)
        for kind in sorted(OUTPUTS)
    }
    digest = hashlib.sha256()
    digest.update(f"astrid-registry-state-v{REGISTRY_STATE_VERSION}\n".encode("utf-8"))
    content_hashes: dict[str, str] = {}
    for kind, content in generated.items():
        content_digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        content_hashes[kind] = content_digest
        digest.update(kind.encode("utf-8"))
        digest.update(b"\0")
        digest.update(content_digest.encode("utf-8"))
        digest.update(b"\0")
    return {
        "version": REGISTRY_STATE_VERSION,
        "hash": digest.hexdigest(),
        "theme": _theme_id(theme_dir),
        "content_hashes": content_hashes,
    }


def generate(*, theme_dir: Path | None = None, include_local: bool = True) -> str:
    return generate_element_registry("effects", theme_dir=theme_dir, include_local=include_local)


def generate_element_registry(
    kind: ElementKind,
    *,
    theme_dir: Path | None = None,
    include_local: bool = True,
) -> str:
    _validate_kind(kind)
    if kind == "effects":
        return _generate_effect_registry(theme_dir=theme_dir, include_local=include_local)

    component_type = "AnimationComponent" if kind == "animations" else "TransitionComponent"
    meta_type = "AnimationMeta" if kind == "animations" else "Record<string, unknown>"
    plugins = discover_plugins(kind, theme_dir, include_local=include_local)
    plugin_ids = sorted(plugins)
    imports = [
        f"import {_component_name(plugin_id)} from '{_import_path(plugins[plugin_id])}';"
        for plugin_id in plugin_ids
    ]
    registry_entries = [
        f"  '{plugin_id}': {_component_name(plugin_id)},"
        for plugin_id in plugin_ids
    ]
    defaults_entries = [
        f"  '{plugin_id}': {_ts_json(plugins[plugin_id].defaults)},"
        for plugin_id in plugin_ids
    ]
    meta_entries = [
        f"  '{plugin_id}': {_ts_json(plugins[plugin_id].meta)},"
        for plugin_id in plugin_ids
    ]
    fingerprint_entries = [
        f"  '{plugin_id}': {_ts_string(plugins[plugin_id].fingerprint)},"
        for plugin_id in plugin_ids
    ]
    ids = ", ".join(_ts_string(plugin_id) for plugin_id in plugin_ids)
    active_theme = f"{json.dumps(_theme_id(theme_dir))} as const" if theme_dir is not None else "null"
    ids_name = _ids_name(kind)
    type_name = _type_name(kind)
    registry_name = _registry_name(kind)
    defaults_name = f"{_constant_prefix(kind)}_DEFAULTS"
    meta_name = f"{_constant_prefix(kind)}_META"
    fingerprints_name = f"{_constant_prefix(kind)}_FINGERPRINTS"
    blocks = [
        "// DO NOT EDIT - generated by tools/scripts/gen_effect_registry.py",
        f"import type {{{component_type}, {meta_type}}} from './effects-types';"
        if kind == "animations"
        else f"import type {{{component_type}}} from './effects-types';",
        *imports,
        "",
        f"export const ACTIVE_THEME_ID = {active_theme};",
        f"export const {ids_name} = [{ids}] as const;",
        f"export type {type_name} = typeof {ids_name}[number];",
        f"export const {registry_name}: Record<{type_name}, {component_type}> = {{",
        *registry_entries,
        "};",
        f"export const {defaults_name}: Record<{type_name}, Record<string, unknown>> = {{",
        *defaults_entries,
        "};",
        f"export const {meta_name}: Record<{type_name}, {meta_type}> = {{",
        *meta_entries,
        "};",
        f"export const {fingerprints_name}: Record<{type_name}, string> = {{",
        *fingerprint_entries,
        "};",
        "",
    ]
    return "\n".join(blocks)


def _generate_effect_registry(
    *,
    theme_dir: Path | None = None,
    include_local: bool = True,
) -> str:
    effects = discover_effects(theme_dir, include_local=include_local)
    effect_ids = sorted(effects)
    imports = [
        f"import {_component_name(effect_id)} from '{_import_path(effects[effect_id])}';"
        for effect_id in effect_ids
    ]
    registry_entries = [
        f"  '{effect_id}': {_component_name(effect_id)},"
        for effect_id in effect_ids
    ]
    fingerprint_entries = [
        f"  '{effect_id}': {_ts_string(effects[effect_id].fingerprint)},"
        for effect_id in effect_ids
    ]
    ids = ", ".join(_ts_string(effect_id) for effect_id in effect_ids)
    aliases = _clip_type_aliases(effects)
    alias_entries = [
        f"  {_ts_property_key(alias)}: {_ts_string(effect_id)},"
        for alias, effect_id in aliases.items()
    ]
    active_theme = f"{json.dumps(_theme_id(theme_dir))} as const" if theme_dir is not None else "null"
    blocks = [
        "// DO NOT EDIT - generated by tools/scripts/gen_effect_registry.py",
        "import type {EffectComponent} from './effects-types';",
        *imports,
        "",
        f"export const ACTIVE_THEME_ID = {active_theme};",
        f"export const EFFECT_IDS = [{ids}] as const;",
        "export type EffectId = typeof EFFECT_IDS[number];",
        "export const EFFECT_REGISTRY: Record<EffectId, EffectComponent> = {",
        *registry_entries,
        "};",
        "export const CLIP_TYPE_ALIASES: Record<string, EffectId> = {",
        *alias_entries,
        "};",
        "export const EFFECT_FINGERPRINTS: Record<EffectId, string> = {",
        *fingerprint_entries,
        "};",
        "",
    ]
    return "\n".join(blocks)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate Remotion effect registry.")
    parser.add_argument("--theme", help="Theme id, theme directory, or path to theme.json.")
    parser.add_argument(
        "--bundled-only",
        action="store_true",
        help="exclude ignored/local pack overrides when generating canonical bundled registries",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    theme_dir = _resolve_theme_dir(args.theme)
    _write_active_theme_pointer(theme_dir)
    failed_outputs: list[Path] = []
    for kind, output in OUTPUTS.items():
        content = generate_element_registry(
            kind,
            theme_dir=theme_dir,
            include_local=not args.bundled_only,
        )
        if not _write_generated_registry(output, content):
            failed_outputs.append(output)
    for kind, shim in SHIM_OUTPUTS.items():
        _write_shim_family(kind, shim)
    if failed_outputs:
        formatted = "\n".join(f"  - {path}" for path in failed_outputs)
        print(
            "ERROR failed to write package-owned generated registries:\n"
            f"{formatted}\n"
            "Remotion shim files were refreshed, but package outputs must be writable.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
