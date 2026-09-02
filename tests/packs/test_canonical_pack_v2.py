from __future__ import annotations

from pathlib import Path

import pytest

from astrid.core.pack.canonical import (
    BundledCatalog,
    CanonicalPackValidationError,
    ExternalPackSource,
    read_normalize_validate,
    validate_canonical_pack,
)
from astrid.core.pack.discovery import discover_canonical_pack_metadata


def _pack(root: Path, pack_id: str = "demo", *, body: str = "capabilities: [render]\n") -> Path:
    pack_root = root / pack_id
    (pack_root / "skill").mkdir(parents=True)
    (pack_root / "skill" / "SKILL.md").write_text("# Demo\n", encoding="utf-8")
    (pack_root / "pack.yaml").write_text(
        f"schema_version: 2\nid: {pack_id}\nname: Demo\nversion: 1.0.0\n"
        "documentation:\n  kind: skill\n  path: skill/SKILL.md\n" + body,
        encoding="utf-8",
    )
    return pack_root


def test_strict_v2_normalizes_immutable_capability_and_resources(tmp_path: Path) -> None:
    root = _pack(tmp_path, body="capabilities: [render]\ncontent: {}\n")
    entry = validate_canonical_pack(root)
    assert entry.id == "demo"
    assert entry.capabilities.capabilities == ("render",)
    assert entry.documentation_projection().documentation == entry.documentation
    assert {resource.path for resource in entry.resources} == {"skill/SKILL.md"}
    with pytest.raises(TypeError):
        entry.definition.extensions["new"] = {}  # type: ignore[index]


def test_v1_alternate_and_database_manifests_fail_closed(tmp_path: Path) -> None:
    root = _pack(tmp_path, body="database: {}\n")
    with pytest.raises(CanonicalPackValidationError, match="database contributions are forbidden"):
        validate_canonical_pack(root)

    v1 = tmp_path / "v1"
    v1.mkdir()
    (v1 / "pack.yaml").write_text(
        "schema_version: 1\nid: v1\nname: V1\nversion: 1.0.0\ncapabilities: [x]\n", encoding="utf-8"
    )
    with pytest.raises(CanonicalPackValidationError, match="schema_version"):
        validate_canonical_pack(v1)

    alternate = tmp_path / "alternate"
    alternate.mkdir()
    (alternate / "pack.yml").write_text(
        "schema_version: 2\nid: alternate\nname: A\nversion: 1.0.0\ncapabilities: [x]\n",
        encoding="utf-8",
    )
    with pytest.raises(CanonicalPackValidationError, match="pack.yaml"):
        validate_canonical_pack(alternate)


def test_catalog_rejects_v1_payload_after_atomic_cutover(tmp_path: Path) -> None:
    _pack(tmp_path, "demo")
    v1 = tmp_path / "runtime_v1"
    v1.mkdir()
    (v1 / "pack.yaml").write_text(
        "schema_version: 1\nid: runtime_v1\nname: Runtime\nversion: 1.0.0\n", encoding="utf-8"
    )
    with pytest.raises(CanonicalPackValidationError, match="schema_version"):
        BundledCatalog.from_root(tmp_path)


def test_external_discovery_is_source_local_extra_env_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    extra = tmp_path / "extra"
    _pack(extra, "extra_pack")
    monkeypatch.setenv("ASTRID_PACKS_PATH", str(extra))
    discovered = discover_canonical_pack_metadata(project_root=tmp_path, extra_pack_roots=(extra,))
    assert [(item.id, item.source_kind) for item in discovered] == [("extra_pack", "extra")]
    entry = read_normalize_validate(
        extra / "extra_pack" / "pack.yaml", source=ExternalPackSource.EXTRA
    )
    assert entry.source == "extra"
