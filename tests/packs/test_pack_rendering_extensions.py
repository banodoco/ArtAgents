from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
import yaml

from astrid.core.pack import PackValidationError, load_pack_manifest
from astrid.core.pack.alias_resolver import extract_pack_aliases
from astrid.core.pack.registry import pack_rendering_manifest_paths
from astrid.core.pack.validate import validate_pack


REPO_ROOT = Path(__file__).resolve().parents[2]
PACK_SCHEMA = REPO_ROOT / "astrid" / "core" / "pack" / "schemas" / "v2" / "pack.json"
RENDERING_OPERATIONS = {
    "renderer": "render",
    "planner": "plan",
    "finalizer": "finalize",
}


def _write_pack(tmp_path: Path, body: str, *, pack_id: str = "render_pack") -> Path:
    pack_root = tmp_path / pack_id
    pack_root.mkdir()
    manifest_path = pack_root / "pack.yaml"
    manifest_path.write_text(body, encoding="utf-8")
    return manifest_path


def _schema_errors(body: str) -> list[str]:
    pack_schema = json.loads(PACK_SCHEMA.read_text(encoding="utf-8"))
    validator_cls = jsonschema.validators.validator_for(pack_schema)
    validator = validator_cls(pack_schema)
    return [error.message for error in validator.iter_errors(yaml.safe_load(body))]


def _write_valid_rendering_pack(tmp_path: Path, *, aliases: bool) -> Path:
    alias_block = ""
    if aliases:
        alias_block = """aliases:
  - kind: renderer
    alias: renderpack.legacy_renderer
    canonical_id: renderpack.compat_renderer
  - kind: renderer
    alias: renderpack.compat_renderer
    canonical_id: renderpack.primary_renderer
  - kind: planner
    alias: renderpack.legacy_planner
    canonical_id: renderpack.primary_planner
  - kind: finalizer
    alias: renderpack.legacy_finalizer
    canonical_id: renderpack.primary_finalizer
"""
    body = f"""schema_version: 2
id: renderpack
name: Rendering Pack
version: 1.0.0
{alias_block}extensions:
  rendering:
    renderers:
      - manifests/renderer.yaml
    planners:
      - manifests/planner.yaml
    finalizers:
      - manifests/finalizer.yaml
"""
    pack_root = _write_pack(tmp_path, body, pack_id="renderpack").parent
    manifests_root = pack_root / "manifests"
    manifests_root.mkdir()
    for kind, operation in RENDERING_OPERATIONS.items():
        (manifests_root / f"{kind}.yaml").write_text(
            f"""schema_version: 1
id: renderpack.primary_{kind}
name: Primary {kind.title()}
version: 1.0.0
protocol_version: 1
command: [python3, {kind}.py]
operations: [{operation}]
""",
            encoding="utf-8",
        )
        (pack_root / f"{kind}.py").write_text(
            "raise SystemExit('must not import')\n",
            encoding="utf-8",
        )
    return pack_root


def test_rendering_extensions_round_trip_through_schema_and_normalizer(tmp_path: Path) -> None:
    body = """schema_version: 2
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
    body = """schema_version: 2
id: render_pack
name: Rendering Pack
version: 1.0.0
extensions:
  rendering:
    renderers: []
    backends: []
"""

    # Canonical v2 reserves ``extensions`` as a typed consumer namespace;
    # the rendering projection owns the deeper shape validation.
    assert _schema_errors(body) == []
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
    body = f"""schema_version: 2
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

    errors, _warnings = validate_pack(pack.root)
    assert any("must stay within the pack root" in error for error in errors), errors


def test_rendering_manifest_paths_resolve_relative_to_pack_root(tmp_path: Path) -> None:
    body = """schema_version: 2
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
    body = """schema_version: 2
id: render_pack
name: Rendering Pack
version: 1.0.0
capabilities: [rendering]
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


def test_validate_pack_accepts_rendering_extension_manifests(
    tmp_path: Path,
) -> None:
    pack_root = _write_valid_rendering_pack(tmp_path, aliases=False)

    errors, _warnings = validate_pack(pack_root)

    assert errors == []


def test_validate_pack_accepts_renderer_planner_and_finalizer_aliases(
    tmp_path: Path,
) -> None:
    pack_root = _write_valid_rendering_pack(tmp_path, aliases=True)

    errors, _warnings = validate_pack(pack_root)

    assert errors == []


@pytest.mark.parametrize("manifest_kind", tuple(RENDERING_OPERATIONS))
def test_validate_pack_rejects_malformed_rendering_manifests(
    tmp_path: Path,
    manifest_kind: str,
) -> None:
    pack_root = _write_valid_rendering_pack(tmp_path, aliases=False)
    manifest_path = pack_root / "manifests" / f"{manifest_kind}.yaml"
    payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    del payload["operations"]
    manifest_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    errors, _warnings = validate_pack(pack_root)

    assert any(
        f"manifests/{manifest_kind}.yaml" in error
        and "missing required field operations" in error
        for error in errors
    ), errors
