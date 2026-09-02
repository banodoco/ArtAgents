from __future__ import annotations

import importlib
import json
import os
import shutil
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

import pytest

from astrid.core.foundation.hash import sha256_file
from astrid.core.pack import discover_packs, load_pack_manifest, pack_manifest_path
from astrid.core.pack.discovery import DiscoveredPack
from astrid.core.pack.override import OverrideStore
from astrid.core.pack.store import InstallRecord, InstalledPackStore
from astrid.core.pack.validate import extract_trust_summary
from astrid.core.rendering import registry as rendering_registry_module
from astrid.core.rendering.registry import (
    FinalizerRegistry,
    PlannerRegistry,
    RendererRegistry,
    RendererRegistryError,
    load_default_registries,
)


FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "renderer_packs" / "discovery"
SOURCE_ROOT = FIXTURES / "source"
ENV_ROOT = FIXTURES / "env"
EXTRA_ROOT = FIXTURES / "extra"
INSTALLED_FIXTURES = FIXTURES / "installed"


def _scanner(source_root: Path):
    def scan(root: str | Path | None = None):
        return discover_packs(source_root if root is None else root)

    return scan


@contextmanager
def _load_with_source(
    project_root: Path,
    source_root: Path = SOURCE_ROOT,
    *,
    extra_pack_roots: tuple[str, ...] = (),
    env_pack_roots: tuple[str, ...] = (),
    include_installed: bool = False,
):
    with (
        mock.patch.object(
            rendering_registry_module,
            "discover_packs",
            side_effect=_scanner(source_root),
        ),
        mock.patch.dict(
            os.environ,
            {"ASTRID_PACKS_PATH": os.pathsep.join(env_pack_roots)},
            clear=False,
        ),
    ):
        yield load_default_registries(
            project_root,
            extra_pack_roots=extra_pack_roots,
            include_installed=include_installed,
        )


def _write_renderer_pack(
    packs_root: Path,
    pack_id: str,
    *,
    renderer_name: str,
    renderer_id: str | None = None,
    required_permissions: tuple[str, ...] = (),
    declared_permissions: tuple[str, ...] = (),
    duplicate_name: str | None = None,
) -> Path:
    pack_root = packs_root / pack_id
    manifests = pack_root / "manifests"
    manifests.mkdir(parents=True)
    manifest_names = ["a.renderer.yaml"]
    if duplicate_name is not None:
        manifest_names.append("b.renderer.yaml")
    permission_lines = "".join(
        f"  - id: {permission}\n    reason: Fixture permission.\n"
        for permission in declared_permissions
    )
    pack_lines = [
        "schema_version: 2",
        f"id: {pack_id}",
        f"name: {pack_id}",
        "version: 1.0.0",
        "domain: media",
        "stability: stable",
        "support: project",
        "visibility: visible",
    ]
    if permission_lines:
        pack_lines.append("permissions:\n" + permission_lines.rstrip())
    pack_lines.extend(
        [
            "extensions:",
            "  rendering:",
            "    renderers:",
            *(f"      - manifests/{name}" for name in manifest_names),
        ]
    )
    (pack_root / "pack.yaml").write_text("\n".join(pack_lines) + "\n", encoding="utf-8")

    capability_id = renderer_id or f"{pack_id}.renderer"
    names = [renderer_name, duplicate_name]
    for index, manifest_name in enumerate(manifest_names):
        required = ", ".join(required_permissions)
        body = [
            "schema_version: 1",
            f"id: {capability_id}",
            f"name: {names[index]}",
            "version: 1.0.0",
            "protocol_version: 1",
            "command: [python3, backend.py]",
            "operations: [render]",
        ]
        if required_permissions:
            body.append(f"required_permissions: [{required}]")
        (manifests / manifest_name).write_text("\n".join(body) + "\n", encoding="utf-8")
    (pack_root / "backend.py").write_text(
        'raise AssertionError("fixture backend must remain inert")\n',
        encoding="utf-8",
    )
    return pack_root




def _stage_installed_fixture(
    astrid_home: Path,
    pack_id: str,
    *,
    record_mode: str = "valid",
    active: bool = True,
) -> Path:
    fixture = INSTALLED_FIXTURES / pack_id
    install_root = astrid_home / "packs" / pack_id
    revision = install_root / "revisions" / pack_id
    revision.parent.mkdir(parents=True)
    shutil.copytree(fixture, revision)

    if active:
        (install_root / "active").symlink_to(Path("revisions") / pack_id)

    record_path = revision / ".astrid" / "install.json"
    if record_mode == "missing":
        return revision
    if record_mode == "corrupt":
        record_path.parent.mkdir(parents=True)
        record_path.write_text("{not-json", encoding="utf-8")
        return revision

    summary = extract_trust_summary(revision)
    accepted_permissions = summary["permissions"]
    record = InstallRecord(
        pack_id=pack_id,
        name=summary["name"],
        version=str(summary["version"]),
        schema_version=summary["schema_version"],
        source_path=str(fixture),
        installed_at="2026-01-01T00:00:00Z",
        revision=pack_id,
        install_root=str(install_root),
        active=active,
        manifest_digest=sha256_file(revision / "pack.yaml"),
        trust_summary=summary,
        source_type="local",
        trust_tier="local",
        last_validation_time="2026-01-01T00:00:00Z",
        trust_acknowledged_at="2026-01-01T00:00:00Z",
        trust_method="test",
        trust_actor="test",
        no_sandbox_warning_version=1,
        permissions_accepted=accepted_permissions,
    )
    InstalledPackStore(astrid_home / "packs").record_install(record)
    return revision


def test_default_loader_returns_all_three_registry_types(tmp_path: Path) -> None:
    with _load_with_source(tmp_path) as registries:
        renderers, planners, finalizers = registries

    assert isinstance(renderers, RendererRegistry)
    assert isinstance(planners, PlannerRegistry)
    assert isinstance(finalizers, FinalizerRegistry)
    assert planners.get("rendering.legacy_hybrid").manifest.name == "Fixture Hybrid Planner"
    assert finalizers.get("rendering.ffmpeg-finalizer").manifest.name == "Fixture FFmpeg Finalizer"


def test_discovery_is_static_and_never_imports_or_executes_backend_code(tmp_path: Path) -> None:
    with (
        mock.patch.object(
            importlib,
            "import_module",
            side_effect=AssertionError("backend import"),
        ),
        mock.patch.object(subprocess, "Popen", side_effect=AssertionError("backend execution")),
        _load_with_source(tmp_path) as registries,
    ):
        renderers, planners, finalizers = registries

    assert renderers.get("rendering.remotion").manifest.command[-1] == "backend_should_not_import.py"
    assert planners.list()
    assert finalizers.list()
    assert "backend_should_not_import" not in sys.modules


def test_priority_index_selects_the_lowest_index_and_conflicts_are_reported(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source"
    extra_root = tmp_path / "extra"
    _write_renderer_pack(source_root, "sharedrender", renderer_name="Source Winner")
    _write_renderer_pack(extra_root, "sharedrender", renderer_name="Extra Shadow")

    with _load_with_source(
        tmp_path / "project",
        source_root,
        extra_pack_roots=(str(extra_root),),
    ) as (renderers, _, _):
        winner = renderers.get("sharedrender.renderer")
        conflicts = renderers.conflicts()

    assert winner.manifest.name == "Source Winner"
    assert winner.priority_index == 0
    assert len(conflicts) == 1
    assert conflicts[0].winner.manifest.name == "Source Winner"
    assert [candidate.manifest.name for candidate in conflicts[0].shadowed] == [
        "Extra Shadow"
    ]


def test_same_pack_conflict_report_is_deterministic(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    _write_renderer_pack(
        source_root,
        "conflictrender",
        renderer_name="First",
        duplicate_name="Second",
    )

    with _load_with_source(tmp_path / "project", source_root) as (renderers, _, _):
        conflict = renderers.conflicts()[0]

    assert conflict.key == "conflictrender.renderer"
    assert conflict.winner.manifest.name == "First"
    assert [candidate.manifest.name for candidate in conflict.shadowed] == ["Second"]




def test_override_is_applied_after_canonical_resolution(tmp_path: Path) -> None:
    store = OverrideStore(tmp_path)
    store.set_override("renderer", "rendering.remotion", "rendering.ffmpeg")

    with _load_with_source(tmp_path) as (renderers, _, _):
        selected = renderers.get("rendering.remotion")
        evidence = renderers.resolve_evidence("rendering.remotion")

    assert selected.id == "rendering.ffmpeg"
    assert evidence["canonical_id"] == "rendering.remotion"
    assert evidence["override"] == {
        "from": "rendering.remotion",
        "to": "rendering.ffmpeg",
    }


@pytest.mark.parametrize(
    ("target", "code"),
    [
        ("rendering.missing", "invalid_override_target"),
        ("rendering.render", "facade_recursion"),
    ],
)
def test_invalid_and_facade_override_targets_are_rejected(
    tmp_path: Path,
    target: str,
    code: str,
) -> None:
    store = OverrideStore(tmp_path)
    store.set_override("renderer", "rendering.remotion", target)

    with _load_with_source(tmp_path) as (renderers, _, _):
        with pytest.raises(RendererRegistryError) as caught:
            renderers.get("rendering.remotion")

    assert caught.value.code == code


def test_source_and_project_local_candidates_are_executable(tmp_path: Path) -> None:
    empty_source = tmp_path / "empty-source"
    empty_source.mkdir()
    project_root = tmp_path / "project"
    local_root = project_root / "astrid" / "packs"
    _write_renderer_pack(local_root, "local", renderer_name="Local Renderer")

    with _load_with_source(project_root, empty_source) as (local_registry, _, _):
        local = local_registry.get("local.renderer")
    with _load_with_source(tmp_path / "other-project") as (source_registry, _, _):
        source = source_registry.get("rendering.remotion")

    assert local.source_kind == "local"
    assert local.execution_eligible is True
    assert local.eligibility.trust_method == "project_local"
    assert source.source_kind == "source"
    assert source.execution_eligible is True
    assert source.eligibility.trust_method == "source_tree"


def test_environment_candidate_is_inspectable_but_not_executable(tmp_path: Path) -> None:
    empty_source = tmp_path / "empty-source"
    empty_source.mkdir()
    env_root = ENV_ROOT
    with (
        mock.patch(
            "astrid.core.rendering.registry.discover_packs",
            side_effect=_scanner(empty_source),
        ),
        mock.patch.dict(os.environ, {"ASTRID_PACKS_PATH": str(env_root)}, clear=False),
    ):
        renderers, _, _ = load_default_registries(tmp_path, include_installed=False)

    inspected = renderers.inspect("env_render.renderer")
    assert len(inspected) == 1
    assert inspected[0].source_kind == "env"
    assert inspected[0].execution_eligible is False
    with pytest.raises(RendererRegistryError) as caught:
        renderers.get("env_render.renderer")
    assert caught.value.code == "execution_ineligible"
    evidence = renderers.resolve_evidence("env_render.renderer")
    assert evidence["eligible"] is False
    assert evidence["resolution_error"]["code"] == "execution_ineligible"


def test_explicit_extra_root_is_executable_and_records_trust_method(tmp_path: Path) -> None:
    empty_source = tmp_path / "empty-source"
    empty_source.mkdir()
    with _load_with_source(
        tmp_path / "project",
        empty_source,
        extra_pack_roots=(str(EXTRA_ROOT),),
    ) as (renderers, _, _):
        candidate = renderers.get("extra_render.renderer")
        evidence = renderers.resolve_evidence("extra_render.renderer")

    assert candidate.source_kind == "extra"
    assert candidate.execution_eligible is True
    assert evidence["trust_method"] == "explicit_extra_pack_root"


def test_installed_active_revision_with_valid_audit_is_executable(tmp_path: Path) -> None:
    astrid_home = tmp_path / "astrid-home"
    empty_source = tmp_path / "empty-source"
    empty_source.mkdir()
    _stage_installed_fixture(astrid_home, "installed_render")

    with (
        mock.patch.dict(
            os.environ,
            {"ASTRID_HOME": str(astrid_home), "ASTRID_PACKS_PATH": ""},
            clear=False,
        ),
        mock.patch(
            "astrid.core.rendering.registry.discover_packs",
            side_effect=_scanner(empty_source),
        ),
    ):
        renderers, _, _ = load_default_registries(tmp_path, include_installed=True)

    candidate = renderers.get("installed_render.renderer")
    assert candidate.source_kind == "installed"
    assert candidate.execution_eligible is True
    assert candidate.eligibility.trust_method == "test"
    assert candidate.eligibility.accepted_permissions == ("subprocess",)


@pytest.mark.parametrize("record_mode", ["missing", "corrupt"])
def test_installed_missing_or_corrupt_record_fails_closed(
    tmp_path: Path,
    record_mode: str,
) -> None:
    astrid_home = tmp_path / "astrid-home"
    empty_source = tmp_path / "empty-source"
    empty_source.mkdir()
    _stage_installed_fixture(
        astrid_home,
        "corrupt_render",
        record_mode=record_mode,
    )

    with (
        mock.patch.dict(
            os.environ,
            {"ASTRID_HOME": str(astrid_home), "ASTRID_PACKS_PATH": ""},
            clear=False,
        ),
        mock.patch(
            "astrid.core.rendering.registry.discover_packs",
            side_effect=_scanner(empty_source),
        ),
    ):
        renderers, _, _ = load_default_registries(tmp_path, include_installed=True)

    assert renderers.inspect("corrupt_render.renderer") == ()
    with pytest.raises(RendererRegistryError) as caught:
        renderers.get("corrupt_render.renderer")
    assert caught.value.code == "unknown_capability"


@pytest.mark.parametrize("bad_install_root", [None, []])
def test_installed_type_corrupt_audit_is_not_discovered(
    tmp_path: Path,
    bad_install_root: object,
) -> None:
    astrid_home = tmp_path / "astrid-home"
    empty_source = tmp_path / "empty-source"
    empty_source.mkdir()
    revision = _stage_installed_fixture(astrid_home, "corrupt_render")
    record_path = revision / ".astrid" / "install.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["install_root"] = bad_install_root
    record_path.write_text(json.dumps(record), encoding="utf-8")

    with (
        mock.patch.dict(
            os.environ,
            {"ASTRID_HOME": str(astrid_home), "ASTRID_PACKS_PATH": ""},
            clear=False,
        ),
        mock.patch(
            "astrid.core.rendering.registry.discover_packs",
            side_effect=_scanner(empty_source),
        ),
    ):
        renderers, _, _ = load_default_registries(tmp_path, include_installed=True)

    assert renderers.inspect("corrupt_render.renderer") == ()

def test_inactive_installed_revision_is_not_discovered(tmp_path: Path) -> None:
    astrid_home = tmp_path / "astrid-home"
    empty_source = tmp_path / "empty-source"
    empty_source.mkdir()
    _stage_installed_fixture(
        astrid_home,
        "inactive_render",
        active=False,
    )

    with (
        mock.patch.dict(
            os.environ,
            {"ASTRID_HOME": str(astrid_home), "ASTRID_PACKS_PATH": ""},
            clear=False,
        ),
        mock.patch(
            "astrid.core.rendering.registry.discover_packs",
            side_effect=_scanner(empty_source),
        ),
    ):
        renderers, _, _ = load_default_registries(tmp_path, include_installed=True)

    assert renderers.inspect("inactive_render.renderer") == ()


def test_ineligible_higher_precedence_candidate_cannot_shadow_trusted_lower(
    tmp_path: Path,
) -> None:
    env_root = tmp_path / "env" / "sharedrender"
    source_root = tmp_path / "source" / "sharedrender"
    _write_renderer_pack(env_root.parent, "sharedrender", renderer_name="Untrusted First")
    _write_renderer_pack(source_root.parent, "sharedrender", renderer_name="Trusted Second")
    env_pack = load_pack_manifest(pack_manifest_path(env_root))
    source_pack = load_pack_manifest(pack_manifest_path(source_root))
    discovered = (
        DiscoveredPack(env_pack, "env", 0),
        DiscoveredPack(source_pack, "source", 1),
    )

    with mock.patch(
        "astrid.core.rendering.registry.discover_pack_metadata",
        return_value=discovered,
    ):
        renderers, _, _ = load_default_registries(tmp_path, include_installed=False)

    selected = renderers.get("sharedrender.renderer")
    assert selected.manifest.name == "Trusted Second"
    assert selected.priority_index == 1
    assert renderers.conflicts() == ()
    assert [candidate.execution_eligible for candidate in renderers.inspect(selected.id)] == [
        False,
        True,
    ]


def test_manifest_permission_not_declared_by_pack_is_ineligible(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    _write_renderer_pack(
        source_root,
        "permissionrender",
        renderer_name="Missing Declaration",
        required_permissions=("network",),
    )

    with _load_with_source(tmp_path / "project", source_root) as (renderers, _, _):
        candidate = renderers.inspect("permissionrender.renderer")[0]

    assert candidate.execution_eligible is False
    assert "not declared" in candidate.eligibility.reason


@pytest.mark.parametrize("selector", ["remotion", "ffmpeg", "hybrid"])
def test_unqualified_renderer_selectors_are_rejected(
    tmp_path: Path,
    selector: str,
) -> None:
    with _load_with_source(tmp_path) as (renderers, planners, _):
        assert planners.get("rendering.legacy_hybrid").id == "rendering.legacy_hybrid"
        with pytest.raises(RendererRegistryError) as caught:
            renderers.get(selector)

    assert caught.value.code == "unknown_capability"
    assert renderers.alias_resolver is None


def test_renderer_manifest_cannot_register_the_facade_id(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    _write_renderer_pack(
        source_root,
        "rendering",
        renderer_name="Recursive Facade",
        renderer_id="rendering.render",
    )

    with pytest.raises(RendererRegistryError) as caught:
        with _load_with_source(tmp_path / "project", source_root):
            pass

    assert caught.value.code == "facade_recursion"


def test_resolve_evidence_has_required_selection_and_trust_shape(tmp_path: Path) -> None:
    with _load_with_source(tmp_path) as (renderers, _, _):
        evidence = renderers.resolve_evidence("rendering.remotion")

    assert {
        "source_kind",
        "pack_id",
        "manifest_digest",
        "alias_chain",
        "override",
        "priority",
        "eligibility_reason",
    } <= evidence.keys()
    assert evidence["source_kind"] == "source"
    assert evidence["pack_id"] == "rendering"
    assert len(evidence["manifest_digest"]) == 64
    assert evidence["alias_chain"] == []
    assert evidence["override"] is None
    assert evidence["priority"] == 0
    assert evidence["execution_eligible"] is True
    assert evidence["eligibility"]["trust_method"] == "source_tree"
