"""Focused B4 group-1 catalog/application/bridge composition tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from astrid.application import compose_standard_application
from astrid.core.pack.canonical import BundledCatalog
from astrid.packs import (
    StandardPackComposition,
    compose_standard_bridge,
    compose_standard_pack_database,
)

DEFAULT_PACKS = {"core", "timeline", "shots", "references"}


def test_operation_composition_projects_default_bundled_database() -> None:
    composition = compose_standard_pack_database()

    assert isinstance(composition, StandardPackComposition)
    assert isinstance(composition.catalog, BundledCatalog)
    assert tuple(composition.registry.packs) == tuple(sorted(DEFAULT_PACKS))
    assert composition.registry.canonical_projection is True
    assert composition.registry.pack("timeline").default_enabled is True
    assert composition.registry.pack("references").default_enabled is True


def test_application_retains_exact_injected_catalog_and_registry(
    tmp_path: Path,
) -> None:
    pair = compose_standard_pack_database(additional_pack_ids=("runaway",))

    with compose_standard_application(
        projects_root=tmp_path,
        catalog=pair.catalog,
        registry=pair.registry,
    ) as app:
        assert app.catalog is pair.catalog
        assert app.registry is pair.registry
        assert "runaway" in app.registry
        assert app.owner_lock is not None and app.owner_lock.held
        assert not app.writer.closed
        assert app.registry.pack("runaway").default_enabled is False

    assert app.writer.closed
    assert app.owner_lock is not None and not app.owner_lock.held


def test_bridge_retains_exact_injected_catalog_and_registry(
    tmp_path: Path,
) -> None:
    pair = compose_standard_pack_database(additional_pack_ids=("runaway",))

    bridge = compose_standard_bridge(
        projects_root=tmp_path,
        catalog=pair.catalog,
        registry=pair.registry,
    )
    try:
        assert bridge.catalog is pair.catalog
        assert bridge.registry is pair.registry
        assert bridge.bridge._writer is bridge.writer  # noqa: SLF001
        assert bridge.owner_lock is not None and bridge.owner_lock.held
    finally:
        bridge.close()

    assert bridge.writer.closed
    assert bridge.owner_lock is not None and not bridge.owner_lock.held


def test_injected_pair_does_not_rebuild_projection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pair = compose_standard_pack_database(additional_pack_ids=("runaway",))

    def unexpected_projection(*args: object, **kwargs: object) -> object:
        raise AssertionError("injected registry must not be projected again")

    import astrid.packs as packs_module

    monkeypatch.setattr(packs_module, "project_catalog_database", unexpected_projection)
    with compose_standard_application(
        projects_root=tmp_path / "application",
        catalog=pair.catalog,
        registry=pair.registry,
    ) as app:
        assert app.catalog is pair.catalog
        assert app.registry is pair.registry
    bridge = compose_standard_bridge(
        projects_root=tmp_path / "bridge",
        catalog=pair.catalog,
        registry=pair.registry,
    )
    bridge.close()
