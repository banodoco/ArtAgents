from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
import yaml
from referencing import Registry, Resource

from astrid.core.pack import PackValidationError, load_pack_manifest
from astrid.core.pack.alias_resolver import extract_pack_aliases
from astrid.core.pack.registry import pack_rendering_manifest_paths


SCHEMAS_ROOT = (
    Path(__file__).resolve().parents[2] / "astrid" / "core" / "pack" / "schemas" / "v1"
)


def _write_pack(tmp_path: Path, body: str, *, pack_id: str = "render_pack") -> Path:
    pack_root = tmp_path / pack_id
    pack_root.mkdir()
    manifest_path = pack_root / "pack.yaml"
    manifest_path.write_text(body, encoding="utf-8")
    return manifest_path


def _schema_errors(body: str) -> list[str]:
    pack_schema = json.loads((SCHEMAS_ROOT / "pack.json").read_text(encoding="utf-8"))
    defs_schema = json.loads((SCHEMAS_ROOT / "_defs.json").read_text(encoding="utf-8"))
    registry = Registry().with_resource("_defs.json", Resource.from_contents(defs_schema))
    validator = jsonschema.Draft7Validator(pack_schema, registry=registry)
    return [error.message for error in validator.iter_errors(yaml.safe_load(body))]


def test_rendering_extensions_round_trip_through_schema_and_normalizer(tmp_path: Path) -> None:
    body = """schema_version: 1
id: render_pack
name: Rendering Pack
version: 1.0.0
extensions:
  rendering:
    renderers:
      - rendering/remotion.renderer.yaml
      - rendering/ffmpeg.renderer.json
    planners:
      - rendering/hybrid.planner.yaml
    finalizers:
      - rendering/ffmpeg.finalizer.yaml
"""
    expected = {
        "renderers": [
            "rendering/remotion.renderer.yaml",
            "rendering/ffmpeg.renderer.json",
        ],
        "planners": ["rendering/hybrid.planner.yaml"],
        "finalizers": ["rendering/ffmpeg.finalizer.yaml"],
    }

    assert _schema_errors(body) == []
    pack = load_pack_manifest(_write_pack(tmp_path, body))
    assert pack.extensions["rendering"] == expected
    assert pack.to_dict()["extensions"]["rendering"] == expected


def test_rendering_extensions_reject_unknown_keys_in_schema_and_normalizer(
    tmp_path: Path,
) -> None:
    body = """schema_version: 1
id: render_pack
name: Rendering Pack
version: 1.0.0
extensions:
  rendering:
    renderers: []
    backends: []
"""

    assert _schema_errors(body)
    with pytest.raises(
        PackValidationError,
        match=r"pack\.extensions\.rendering has unknown field\(s\): backends",
    ):
        load_pack_manifest(_write_pack(tmp_path, body))


@pytest.mark.parametrize("declared_path", ["../outside.renderer.yaml", "/tmp/outside.renderer.yaml"])
def test_rendering_manifest_paths_reject_pack_root_escapes(
    tmp_path: Path,
    declared_path: str,
) -> None:
    body = f"""schema_version: 1
id: render_pack
name: Rendering Pack
version: 1.0.0
extensions:
  rendering:
    renderers:
      - {declared_path}
"""
    pack = load_pack_manifest(_write_pack(tmp_path, body))

    with pytest.raises(PackValidationError, match="must stay within the pack root"):
        pack_rendering_manifest_paths(pack)


def test_rendering_manifest_paths_resolve_relative_to_pack_root(tmp_path: Path) -> None:
    body = """schema_version: 1
id: render_pack
name: Rendering Pack
version: 1.0.0
extensions:
  rendering:
    renderers:
      - manifests/renderer.yaml
    planners:
      - manifests/planner.yaml
    finalizers:
      - manifests/finalizer.yaml
"""
    pack = load_pack_manifest(_write_pack(tmp_path, body))

    renderers, planners, finalizers = pack_rendering_manifest_paths(pack)
    assert renderers == (pack.root / "manifests" / "renderer.yaml",)
    assert planners == (pack.root / "manifests" / "planner.yaml",)
    assert finalizers == (pack.root / "manifests" / "finalizer.yaml",)


def test_extract_pack_aliases_recognizes_rendering_alias_kinds(tmp_path: Path) -> None:
    body = """schema_version: 1
id: render_pack
name: Rendering Pack
version: 1.0.0
aliases:
  - kind: renderer
    alias: render_pack.legacy_renderer
    canonical_id: render_pack.renderer
  - kind: planner
    alias: render_pack.legacy_planner
    canonical_id: render_pack.planner
  - kind: finalizer
    alias: render_pack.legacy_finalizer
    canonical_id: render_pack.finalizer
"""
    assert _schema_errors(body) == []
    pack = load_pack_manifest(_write_pack(tmp_path, body))

    for kind in ("renderer", "planner", "finalizer"):
        aliases = extract_pack_aliases((pack,), kind=kind)
        assert aliases["render_pack"] == [
            {
                "kind": kind,
                "alias": f"render_pack.legacy_{kind}",
                "canonical_id": f"render_pack.{kind}",
                "source_pack_id": "render_pack",
            }
        ]
