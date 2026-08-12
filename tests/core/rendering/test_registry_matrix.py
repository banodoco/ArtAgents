"""Discovery / eligibility matrix edge cases (T1.5).

Extends ``tests/core/rendering/test_registry.py`` (T1.4) with additional
edge cases that lock the static discovery, precedence, conflict, alias,
override, eligibility, and evidence contract of the rendering registries.

Every test here is fully static: fixture backends are never imported and
never executed (``backend.py`` / ``backend_should_not_import.py`` files
raise ``AssertionError`` if anything tries to run them).
"""

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
from astrid.core.pack.override import OverrideStore
from astrid.core.pack.store import InstallRecord, InstalledPackStore
from astrid.core.pack.validate import extract_trust_summary
from astrid.core.rendering import registry as rendering_registry_module
from astrid.core.rendering.registry import (
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
    include_installed: bool = False,
):
    with (
        mock.patch.object(
            rendering_registry_module,
            "discover_packs",
            side_effect=_scanner(source_root),
        ),
        mock.patch.dict(os.environ, {"ASTRID_PACKS_PATH": ""}, clear=False),
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
        "schema_version: 1",
        f"id: {pack_id}",
        f"name: {pack_id}",
        "version: 1.0.0",
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
    accepted_permissions: list[dict] | None = None,
) -> Path:
    fixture_name = pack_id
    fixture = INSTALLED_FIXTURES / fixture_name
    install_root = astrid_home / "packs" / pack_id
    revision = install_root / "revisions" / pack_id
    revision.parent.mkdir(parents=True)
    shutil.copytree(fixture, revision)
    (install_root / "active").symlink_to(Path("revisions") / pack_id)

    summary = extract_trust_summary(revision)
    if accepted_permissions is None:
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
        active=True,
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


def _load_env_registries(project_root: Path, *, extra_pack_roots: tuple[str, ...] = ()):
    empty_source = project_root / "empty-source"
    empty_source.mkdir(parents=True, exist_ok=True)
    env_root = ENV_ROOT
    with (
        mock.patch.object(
            rendering_registry_module,
            "discover_packs",
            side_effect=_scanner(empty_source),
        ),
        mock.patch.dict(os.environ, {"ASTRID_PACKS_PATH": str(env_root)}, clear=False),
    ):
        return load_default_registries(
            project_root,
            extra_pack_roots=extra_pack_roots,
            include_installed=False,
        )


# ---------------------------------------------------------------------------
# Static no-import matrix
# ---------------------------------------------------------------------------


def test_static_load_and_read_surface_never_imports_fixture_backend_modules(
    tmp_path: Path,
) -> None:
    """The full static surface leaves no fixture backend module in sys.modules.

    Discovery, listing, inspection, conflict reporting, and evidence
    resolution may only read YAML/JSON data.  After exercising every read
    API, no module backed by a fixture pack directory may appear.
    """
    modules_before = set(sys.modules)

    with _load_with_source(tmp_path / "project") as (renderers, planners, finalizers):
        renderers.get("rendering.remotion")
        renderers.get("ffmpeg")
        renderers.list()
        renderers.inspect("rendering.remotion")
        renderers.candidates()
        renderers.candidates("rendering.remotion", eligible=True)
        renderers.conflicts()
        renderers.resolve_evidence("remotion")
        renderers.validate_all()
        planners.list()
        finalizers.list()

    modules_after = set(sys.modules)
    new_modules = modules_after - modules_before

    assert "backend_should_not_import" not in sys.modules
    assert not any("backend_should_not_import" in name for name in new_modules)
    assert not any("renderer_packs" in name for name in new_modules)
    fixture_root = str(FIXTURES.resolve())
    for name in new_modules:
        module = sys.modules.get(name)
        module_file = getattr(module, "__file__", None)
        assert module_file is None or not str(Path(module_file).resolve()).startswith(
            fixture_root
        ), f"module {name!r} is backed by a fixture pack file: {module_file}"


def test_inspection_of_env_layer_never_imports_or_executes_backend_code(
    tmp_path: Path,
) -> None:
    """Inspecting an env-layer pack is pure metadata work.

    The env pack is the least trusted layer; even its inspection path must
    never import or execute the fixture backend.
    """
    with (
        mock.patch.object(
            importlib,
            "import_module",
            side_effect=AssertionError("backend import"),
        ),
        mock.patch.object(subprocess, "Popen", side_effect=AssertionError("backend execution")),
    ):
        renderers, _, _ = _load_env_registries(tmp_path / "project")

        inspected = renderers.inspect("env_render.renderer")
        assert len(inspected) == 1
        assert inspected[0].source_kind == "env"
        assert inspected[0].execution_eligible is False
        assert len(renderers.candidates()) == 1
        assert len(renderers.list()) == 0
        assert renderers.conflicts() == ()
        evidence = renderers.resolve_evidence("env_render.renderer")
        assert evidence["eligible"] is False
        assert evidence["resolution_error"]["code"] == "execution_ineligible"
        with pytest.raises(RendererRegistryError) as caught:
            renderers.get("env_render.renderer")
        assert caught.value.code == "execution_ineligible"

    assert "backend_should_not_import" not in sys.modules


# ---------------------------------------------------------------------------
# Precedence matrix
# ---------------------------------------------------------------------------


def test_cross_layer_precedence_winner_is_recorded_in_evidence_and_conflicts(
    tmp_path: Path,
) -> None:
    """The higher-precedence layer wins and the evidence records it.

    ``priority_index`` is the discovery-order position: lower indices are
    discovered first and therefore outrank later layers.  Both the winner's
    ``resolve_evidence`` payload and the conflict report must record the
    same outcome.
    """
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
        evidence = renderers.resolve_evidence("sharedrender.renderer")
        conflicts = renderers.conflicts()

    assert winner.manifest.name == "Source Winner"
    assert winner.priority_index == 0
    assert winner.source_kind == "source"

    assert evidence["resolved_id"] == "sharedrender.renderer"
    assert evidence["source_kind"] == "source"
    assert evidence["pack_id"] == "sharedrender"
    assert evidence["priority"] == 0
    assert evidence["priority_index"] == 0
    assert evidence["eligible"] is True
    assert evidence["eligibility_reason"] == "source-tree pack is execution-eligible"
    assert evidence["alias_chain"] == []
    assert evidence["override"] is None

    assert len(conflicts) == 1
    assert conflicts[0].key == "sharedrender.renderer"
    assert conflicts[0].winner.manifest.name == "Source Winner"
    assert [candidate.manifest.name for candidate in conflicts[0].shadowed] == [
        "Extra Shadow"
    ]


def test_cross_pack_qualified_id_squatting_is_rejected_deterministically(
    tmp_path: Path,
) -> None:
    """A renderer id namespaced to another pack is rejected, never shadowed.

    ``validate_content_id_in_pack`` prevents one pack from declaring a
    renderer id that belongs to a different pack namespace, so a same-layer
    cross-pack collision cannot silently resolve to either declaration.
    """
    source_root = tmp_path / "source"
    _write_renderer_pack(
        source_root,
        "aaaalpha",
        renderer_name="Squatter",
        renderer_id="shared.matrix.renderer",
    )

    with pytest.raises(RendererRegistryError) as caught:
        with _load_with_source(tmp_path / "project", source_root):
            pass

    assert caught.value.code == "invalid_manifest"
    assert caught.value.capability_kind == "renderer"
    details = caught.value.to_dict()["details"]
    assert details["pack_id"] == "aaaalpha"
    assert str(details["manifest_path"]).endswith("a.renderer.yaml")


def test_ineligible_duplicate_manifest_is_excluded_from_conflicts_and_execution(
    tmp_path: Path,
) -> None:
    """An ineligible duplicate never becomes a shadowed alternate.

    Only execution-eligible candidates enter the executable registry, so a
    same-id duplicate that fails eligibility produces no conflict record and
    cannot influence the winner.
    """
    source_root = tmp_path / "source"
    _write_renderer_pack(
        source_root,
        "conflictrender",
        renderer_name="Eligible First",
        duplicate_name="Denied Second",
    )
    duplicate = source_root / "conflictrender" / "manifests" / "b.renderer.yaml"
    duplicate.write_text(
        duplicate.read_text(encoding="utf-8") + "required_permissions: [network]\n",
        encoding="utf-8",
    )

    with _load_with_source(tmp_path / "project", source_root) as (renderers, _, _):
        discovered = renderers.inspect("conflictrender.renderer")
        conflicts = renderers.conflicts()
        eligible = renderers.candidates("conflictrender.renderer", eligible=True)
        winner = renderers.get("conflictrender.renderer")

    assert [candidate.manifest.name for candidate in discovered] == [
        "Eligible First",
        "Denied Second",
    ]
    assert [candidate.execution_eligible for candidate in discovered] == [True, False]
    assert conflicts == ()
    assert [candidate.manifest.name for candidate in eligible] == ["Eligible First"]
    assert winner.manifest.name == "Eligible First"


def test_multiple_conflicts_are_reported_in_deterministic_key_order(
    tmp_path: Path,
) -> None:
    """Conflict reports are sorted by key and stable across repeated calls."""
    source_root = tmp_path / "source"
    _write_renderer_pack(
        source_root,
        "zzzomega",
        renderer_name="Omega First",
        duplicate_name="Omega Second",
    )
    _write_renderer_pack(
        source_root,
        "aaaalpha",
        renderer_name="Alpha First",
        duplicate_name="Alpha Second",
    )

    with _load_with_source(tmp_path / "project", source_root) as (renderers, _, _):
        first = renderers.conflicts()
        second = renderers.conflicts()

    assert [conflict.key for conflict in first] == [
        "aaaalpha.renderer",
        "zzzomega.renderer",
    ]
    assert [conflict.winner.manifest.name for conflict in first] == [
        "Alpha First",
        "Omega First",
    ]
    assert first == second


# ---------------------------------------------------------------------------
# Alias matrix
# ---------------------------------------------------------------------------


def test_env_pack_alias_is_inspectable_but_not_executable(tmp_path: Path) -> None:
    """Aliases declared by an untrusted env pack fail closed for execution.

    The inspection resolver sees every alias (so ``inspect`` resolves the
    env candidate); the executable resolver only contains aliases from
    trusted packs, so ``get`` treats the alias as unknown rather than ever
    resolving through untrusted metadata.
    """
    renderers, _, _ = _load_env_registries(tmp_path / "project")

    inspected = renderers.inspect("env_render.legacy")
    assert len(inspected) == 1
    assert inspected[0].manifest.name == "Environment Fixture Renderer"
    assert inspected[0].source_kind == "env"

    assert renderers.candidates("env_render.legacy", eligible=True) == ()
    with pytest.raises(RendererRegistryError) as caught:
        renderers.get("env_render.legacy")
    assert caught.value.code == "unknown_capability"
    with pytest.raises(RendererRegistryError) as evidence_caught:
        renderers.resolve_evidence("env_render.legacy")
    assert evidence_caught.value.code == "unknown_capability"


# ---------------------------------------------------------------------------
# Override matrix
# ---------------------------------------------------------------------------


def test_override_to_discovered_ineligible_target_fails_closed(tmp_path: Path) -> None:
    """Overriding onto a discoverable-but-ineligible target is rejected.

    The override lands on an env-layer renderer that can never be executed;
    resolution fails with a structured error that records the override that
    caused the redirect.
    """
    store = OverrideStore(tmp_path / "project")
    store.set_override("renderer", "rendering.remotion", "env_render.renderer")

    renderers, _, _ = _load_env_registries(tmp_path / "project")

    with pytest.raises(RendererRegistryError) as caught:
        renderers.get("rendering.remotion")

    assert caught.value.code == "execution_ineligible"
    details = caught.value.to_dict()["details"]
    assert details["override"] == {
        "from": "rendering.remotion",
        "to": "env_render.renderer",
    }
    assert details["target_id"] == "env_render.renderer"
    assert details["canonical_id"] == "rendering.remotion"


def _write_alias_to_absent_pack(packs_root: Path) -> Path:
    """A source pack whose renderer alias points at a canonical in ANOTHER
    pack namespace that does not exist in the discovery tree. Cross-pack
    alias targets are not statically checked (validate.py only validates
    same-pack targets), so this pack passes validate_pack and can be
    installed, while resolution still requires the override to supply the
    implementation."""
    pack_root = _write_renderer_pack(
        packs_root,
        "alias_missing",
        renderer_name="Alias Missing Renderer",
        renderer_id="alias_missing.renderer",
    )
    pack_yaml = pack_root / "pack.yaml"
    lines = pack_yaml.read_text(encoding="utf-8").splitlines()
    alias_block = [
        "aliases:",
        "  - kind: renderer",
        "    alias: alias_missing.legacy",
        "    canonical_id: other.abstract.renderer",
    ]
    # insert aliases before extensions
    idx = next(i for i, line in enumerate(lines) if line.startswith("extensions:"))
    lines[idx:idx] = alias_block
    pack_yaml.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return pack_root


def test_trusted_pack_alias_to_absent_canonical_routes_through_override(
    tmp_path: Path,
) -> None:
    """A pack-declared alias whose canonical is absent still routes through
    an override to an executable implementation.

    The frozen ordering is alias -> canonical -> override: a missing canonical
    must not silently drop a trusted pack alias when an override supplies the
    implementation.
    """
    project_root = tmp_path / "project"
    source_root = tmp_path / "source"
    source_root.mkdir()
    pack_root = _write_alias_to_absent_pack(source_root)

    # The cross-pack alias must pass static pack validation (the same-pack
    # target rule does not apply) so the pack remains installable.
    from astrid.core.pack.validate import validate_pack
    from astrid.core.pack.install_local import install_pack
    from astrid.core.pack.store import InstalledPackStore

    errors, warnings = validate_pack(str(pack_root))
    assert not errors, errors

    astrid_home = tmp_path / "astrid-home"
    empty_source = tmp_path / "empty-source"
    empty_source.mkdir()
    store = InstalledPackStore(astrid_home / "packs")
    exit_code = install_pack(
        pack_root,
        store=store,
        dry_run=False,
        skip_confirm=True,
        trust_acknowledged=True,
        trust_method="test",
        trust_actor="test",
    )
    assert exit_code == 0, f"install failed with exit {exit_code}"

    override_store = OverrideStore(project_root)
    override_store.set_override("renderer", "other.abstract.renderer", "alias_missing.renderer")

    # Resolve from the INSTALLED revision (include_installed=True, empty
    # source tree) so the override route is proven on the installed pack.
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
        renderers, _, _ = load_default_registries(project_root, include_installed=True)

    candidate = renderers.get("alias_missing.legacy")
    assert candidate.id == "alias_missing.renderer"
    assert candidate.source_kind == "installed"
    assert candidate.execution_eligible is True

    evidence = renderers.resolve_evidence("alias_missing.legacy")
    assert evidence["canonical_id"] == "other.abstract.renderer"
    assert evidence["resolved_id"] == "alias_missing.renderer"
    assert evidence["override"] == {
        "from": "other.abstract.renderer",
        "to": "alias_missing.renderer",
    }


def test_trusted_pack_alias_to_absent_canonical_without_override_fails_closed(
    tmp_path: Path,
) -> None:
    """Without an override, a pack alias to an absent canonical is dropped
    and resolution reports the missing target."""
    project_root = tmp_path / "project"
    source_root = tmp_path / "source"
    source_root.mkdir()
    _write_alias_to_absent_pack(source_root)

    with _load_with_source(project_root, source_root=source_root) as (renderers, _, _):
        with pytest.raises(RendererRegistryError) as caught:
            renderers.get("alias_missing.legacy")
        assert caught.value.code == "unknown_capability"
        with pytest.raises(RendererRegistryError) as evidence_caught:
            renderers.resolve_evidence("alias_missing.legacy")
        assert evidence_caught.value.code == "unknown_capability"


# ---------------------------------------------------------------------------
# Eligibility matrix
# ---------------------------------------------------------------------------


def test_env_candidate_cannot_shadow_eligible_extra_in_natural_discovery_order(
    tmp_path: Path,
) -> None:
    """An env-layer candidate stays out of the executable registry.

    When an eligible extra-root pack and an ineligible env pack declare the
    same renderer id, only the extra pack is ever executable — the env
    candidate remains discoverable and inspectable but contributes no
    conflict and cannot be selected.
    """
    extra_root = tmp_path / "extra"
    env_root = tmp_path / "env"
    _write_renderer_pack(extra_root, "sharedrender", renderer_name="Extra Eligible")
    _write_renderer_pack(env_root, "sharedrender", renderer_name="Env Ineligible")

    empty_source = tmp_path / "empty-source"
    empty_source.mkdir(exist_ok=True)
    with (
        mock.patch(
            "astrid.core.rendering.registry.discover_packs",
            side_effect=_scanner(empty_source),
        ),
        mock.patch.dict(os.environ, {"ASTRID_PACKS_PATH": str(env_root)}, clear=False),
    ):
        renderers, _, _ = load_default_registries(
            tmp_path / "project",
            extra_pack_roots=(str(extra_root),),
            include_installed=False,
        )

    winner = renderers.get("sharedrender.renderer")
    assert winner.manifest.name == "Extra Eligible"
    assert winner.source_kind == "extra"
    assert winner.priority_index == 0
    assert renderers.conflicts() == ()
    assert [
        (candidate.manifest.name, candidate.source_kind, candidate.execution_eligible)
        for candidate in renderers.candidates("sharedrender.renderer")
    ] == [
        ("Extra Eligible", "extra", True),
        ("Env Ineligible", "env", False),
    ]


def test_installed_pack_with_unaccepted_permissions_fails_closed(
    tmp_path: Path,
) -> None:
    """An install record that accepted no permissions is not trustworthy.

    The fixture pack declares ``subprocess`` and the manifest requires it,
    but the install record's accepted-permission list is empty — the trust
    audit cannot be validated, so the candidate is inspectable only.
    """
    astrid_home = tmp_path / "astrid-home"
    empty_source = tmp_path / "empty-source"
    empty_source.mkdir(exist_ok=True)
    _stage_installed_fixture(astrid_home, "installed_render", accepted_permissions=[])

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
        renderers, _, _ = load_default_registries(tmp_path / "project", include_installed=True)

    candidate = renderers.inspect("installed_render.renderer")[0]
    assert candidate.execution_eligible is False
    assert "accepted permissions" in candidate.eligibility.reason
    assert candidate.eligibility.accepted_permissions == ()
    with pytest.raises(RendererRegistryError) as caught:
        renderers.get("installed_render.renderer")
    assert caught.value.code == "execution_ineligible"


def test_permission_deficiency_reason_lists_all_missing_permissions_sorted(
    tmp_path: Path,
) -> None:
    """Every undeclared required permission is named, in sorted order."""
    source_root = tmp_path / "source"
    _write_renderer_pack(
        source_root,
        "permissionrender",
        renderer_name="Missing Declarations",
        required_permissions=("network", "environment"),
    )

    with _load_with_source(tmp_path / "project", source_root) as (renderers, _, _):
        candidate = renderers.inspect("permissionrender.renderer")[0]
        evidence = renderers.resolve_evidence("permissionrender.renderer")

    assert candidate.execution_eligible is False
    reason = candidate.eligibility.reason
    assert "environment" in reason
    assert "network" in reason
    assert reason.index("environment") < reason.index("network")
    assert candidate.eligibility.required_permissions == ("network", "environment")
    assert candidate.eligibility.declared_permissions == ()
    assert evidence["eligible"] is False
    assert evidence["resolution_error"]["code"] == "execution_ineligible"


# ---------------------------------------------------------------------------
# Facade / hybrid matrix
# ---------------------------------------------------------------------------


def test_hybrid_absent_from_every_renderer_surface(tmp_path: Path) -> None:
    """``hybrid`` never appears under any name in the renderer registry."""
    with _load_with_source(tmp_path / "project") as (renderers, planners, _):
        renderer_ids = [candidate.id for candidate in renderers.list()]
        mapping = renderers.as_mapping()

        assert all("hybrid" not in renderer_id for renderer_id in renderer_ids)
        assert "hybrid" not in mapping
        assert "rendering.hybrid" not in mapping
        assert renderers.inspect("hybrid") == ()
        assert renderers.inspect("rendering.hybrid") == ()
        with pytest.raises(RendererRegistryError) as caught:
            renderers.get("hybrid")
        assert caught.value.code == "unknown_capability"

        # The planner registry keeps its own hybrid translation capability.
        assert planners.get("rendering.legacy_hybrid").id == "rendering.legacy_hybrid"


# ---------------------------------------------------------------------------
# Evidence matrix
# ---------------------------------------------------------------------------


def test_resolve_evidence_records_alias_chain_and_eligibility_for_bare_alias(
    tmp_path: Path,
) -> None:
    """Bare ``remotion`` evidence carries the full alias chain and trust."""
    with _load_with_source(tmp_path / "project") as (renderers, _, _):
        evidence = renderers.resolve_evidence("remotion")

    assert evidence["requested_id"] == "remotion"
    assert evidence["canonical_id"] == "rendering.remotion"
    assert evidence["resolved_id"] == "rendering.remotion"
    assert evidence["alias_chain"] == ["remotion", "rendering.remotion"]
    assert evidence["override"] is None
    assert evidence["priority"] == 0
    assert evidence["manifest_digest"]
    assert len(evidence["manifest_digest"]) == 64
    assert evidence["eligible"] is True
    assert evidence["eligibility_reason"] == "source-tree pack is execution-eligible"
    assert evidence["eligibility"]["trust_method"] == "source_tree"
    assert evidence["eligibility"]["required_permissions"] == ["project_files", "subprocess"]
