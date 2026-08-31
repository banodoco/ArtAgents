from __future__ import annotations

import importlib
import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

import pytest

from astrid.core.pack import discover_packs, load_pack_manifest, pack_manifest_path
from astrid.core.pack.discovery import DiscoveredPack
from astrid.core.pack.override import OverrideStore
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
CYCLE_ROOT = FIXTURES / "cycle"


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


def _append_renderer_aliases(
    pack_root: Path,
    *aliases: tuple[str, str],
) -> None:
    manifest = pack_root / "pack.yaml"
    lines = ["aliases:"]
    for alias, canonical_id in aliases:
        lines.extend(
            [
                "  - kind: renderer",
                f"    alias: {alias}",
                f"    canonical_id: {canonical_id}",
            ]
        )
    manifest.write_text(
        manifest.read_text(encoding="utf-8") + "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def test_default_loader_returns_all_three_registry_types(tmp_path: Path) -> None:
    with _load_with_source(tmp_path) as registries:
        renderers, planners, finalizers = registries

    assert isinstance(renderers, RendererRegistry)
    assert isinstance(planners, PlannerRegistry)
    assert isinstance(finalizers, FinalizerRegistry)
    assert planners.list() == ()
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
    assert planners.list() == ()
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


@pytest.mark.skip(reason="programmatic renderer aliases are retired")
def test_alias_chain_and_programmatic_compatibility_aliases(tmp_path: Path) -> None:
    with _load_with_source(tmp_path) as (renderers, _, _):
        chained = renderers.get("rendering.legacy")
        chain_evidence = renderers.resolve_evidence("rendering.legacy")
        remotion = renderers.get("rendering.remotion")
        ffmpeg = renderers.get("rendering.ffmpeg")

    assert chained.id == "rendering.remotion"
    assert chain_evidence["alias_chain"] == [
        "rendering.legacy",
        "rendering.compat",
        "rendering.remotion",
    ]
    assert remotion.id == "rendering.remotion"
    assert ffmpeg.id == "rendering.ffmpeg"


def test_alias_cycle_is_rejected_as_structured_registry_error(tmp_path: Path) -> None:
    cycle_root = CYCLE_ROOT
    with (
        mock.patch(
            "astrid.core.rendering.registry.discover_packs",
            side_effect=_scanner(cycle_root),
        ),
        mock.patch.dict(os.environ, {"ASTRID_PACKS_PATH": ""}, clear=False),
    ):
        with pytest.raises(RendererRegistryError) as caught:
            load_default_registries(tmp_path)

    assert caught.value.code == "alias_cycle"
    assert caught.value.to_dict()["capability_kind"] == "renderer"


def test_alias_to_ineligible_direct_target_does_not_shadow_eligible_alias(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source"
    bad_root = _write_renderer_pack(
        source_root,
        "abad",
        renderer_name="Denied",
        required_permissions=("network",),
    )
    good_root = _write_renderer_pack(
        source_root,
        "bgood",
        renderer_name="Eligible",
    )
    for pack_root, target in (
        (bad_root, "abad.renderer"),
        (good_root, "bgood.renderer"),
    ):
        manifest = pack_root / "pack.yaml"
        manifest.write_text(
            manifest.read_text(encoding="utf-8")
            + "aliases:\n"
            + "  - kind: renderer\n"
            + "    alias: shared.renderer-alias\n"
            + f"    canonical_id: {target}\n",
            encoding="utf-8",
        )

    with _load_with_source(tmp_path / "project", source_root) as (renderers, _, _):
        selected = renderers.get("shared.renderer-alias")

    assert selected.id == "bgood.renderer"
    assert selected.manifest.name == "Eligible"


def test_two_hop_alias_to_ineligible_env_renderer_falls_through(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source"
    extra_root = tmp_path / "extra"
    env_root = tmp_path / "env"
    high = _write_renderer_pack(source_root, "highchain", renderer_name="High")
    fallback = _write_renderer_pack(
        extra_root,
        "trustedfallback",
        renderer_name="Trusted Fallback",
    )
    _write_renderer_pack(env_root, "envdenied", renderer_name="Environment Denied")
    _append_renderer_aliases(
        high,
        ("shared.transitive", "highchain.middle"),
        ("highchain.middle", "envdenied.renderer"),
    )
    _append_renderer_aliases(
        fallback,
        ("shared.transitive", "trustedfallback.renderer"),
    )

    with _load_with_source(
        tmp_path / "project",
        source_root,
        extra_pack_roots=(str(extra_root),),
        env_pack_roots=(str(env_root),),
    ) as (renderers, _, _):
        selected = renderers.get("shared.transitive")
        evidence = renderers.resolve_evidence("shared.transitive")
        denied = renderers.inspect("envdenied.renderer")

    assert selected.id == "trustedfallback.renderer"
    assert evidence["alias_chain"] == [
        "shared.transitive",
        "trustedfallback.renderer",
    ]
    assert len(denied) == 1
    assert denied[0].execution_eligible is False


def test_two_hop_alias_to_missing_terminal_falls_through(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    extra_root = tmp_path / "extra"
    high = _write_renderer_pack(source_root, "highchain", renderer_name="High")
    fallback = _write_renderer_pack(
        extra_root,
        "trustedfallback",
        renderer_name="Trusted Fallback",
    )
    _append_renderer_aliases(
        high,
        ("shared.transitive", "highchain.middle"),
        ("highchain.middle", "missing.renderer"),
    )
    _append_renderer_aliases(
        fallback,
        ("shared.transitive", "trustedfallback.renderer"),
    )

    with _load_with_source(
        tmp_path / "project",
        source_root,
        extra_pack_roots=(str(extra_root),),
    ) as (renderers, _, _):
        selected = renderers.get("shared.transitive")
        evidence = renderers.resolve_evidence("shared.transitive")

    assert selected.id == "trustedfallback.renderer"
    assert evidence["alias_chain"] == [
        "shared.transitive",
        "trustedfallback.renderer",
    ]


def test_alias_chain_uses_eligible_fallback_for_ineligible_intermediate_hop(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source"
    extra_root = tmp_path / "extra"
    env_root = tmp_path / "env"
    high = _write_renderer_pack(source_root, "highchain", renderer_name="High")
    fallback = _write_renderer_pack(
        extra_root,
        "trustedfallback",
        renderer_name="Trusted Fallback",
    )
    _write_renderer_pack(env_root, "envdenied", renderer_name="Environment Denied")
    _append_renderer_aliases(
        high,
        ("shared.transitive", "shared.middle"),
        ("shared.middle", "envdenied.renderer"),
    )
    _append_renderer_aliases(
        fallback,
        ("shared.middle", "trustedfallback.renderer"),
    )

    with _load_with_source(
        tmp_path / "project",
        source_root,
        extra_pack_roots=(str(extra_root),),
        env_pack_roots=(str(env_root),),
    ) as (renderers, _, _):
        selected = renderers.get("shared.transitive")
        evidence = renderers.resolve_evidence("shared.transitive")

    assert selected.id == "trustedfallback.renderer"
    assert evidence["alias_chain"] == [
        "shared.transitive",
        "shared.middle",
        "trustedfallback.renderer",
    ]


@pytest.mark.skip(reason="programmatic renderer aliases are retired")
def test_dangling_programmatic_alias_falls_through_to_eligible_pack_alias(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source"
    fallback = _write_renderer_pack(
        source_root,
        "trustedfallback",
        renderer_name="Trusted Fallback",
    )
    _append_renderer_aliases(
        fallback,
        ("shared.programmatic", "trustedfallback.renderer"),
    )

    with (
        mock.patch.object(
            rendering_registry_module,
            "_PROGRAMMATIC_RENDERER_ALIASES",
            (("shared.programmatic", "missing.renderer"),),
        ),
        _load_with_source(
            tmp_path / "project",
            source_root,
        ) as (renderers, _, _),
    ):
        selected = renderers.get("shared.programmatic")
        evidence = renderers.resolve_evidence("shared.programmatic")

    assert selected.id == "trustedfallback.renderer"
    assert evidence["alias_chain"] == [
        "shared.programmatic",
        "trustedfallback.renderer",
    ]


def test_override_is_applied_after_alias_resolution(tmp_path: Path) -> None:
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
        renderers, _, _ = load_default_registries(tmp_path)

    inspected = renderers.inspect("env_render.legacy")
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
        renderers, _, _ = load_default_registries(tmp_path)

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


def test_shorthand_is_never_a_renderer_alias(tmp_path: Path) -> None:
    with _load_with_source(tmp_path) as (renderers, planners, _):
        assert planners.list() == ()
        with pytest.raises(RendererRegistryError) as caught:
            renderers.get("hybrid")

    assert caught.value.code == "unknown_capability"
    assert renderers.alias_resolver is not None
    assert renderers.alias_resolver.is_alias("hybrid") is False


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
