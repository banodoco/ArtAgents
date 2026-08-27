"""Long-lived SDK clients preserve explicit schema-pack composition."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from astrid import AstridClient
from astrid.core.events.registry import core_only_registry, register_core_vocabulary
from astrid.core.migrations.runner import MigrationTooNewError
from astrid.core.schema_packs.registry import SchemaPackRegistry
from astrid.packs import register_standard_schema_packs


def _extended_registry() -> object:
    registry = SchemaPackRegistry()
    register_core_vocabulary(registry)
    register_standard_schema_packs(registry)
    return registry.freeze()


def test_long_lived_client_invokes_with_extended_registry(tmp_path: Path) -> None:
    registry = _extended_registry()
    with AstridClient.open(tmp_path, registry=registry) as client:
        project = client.projects.create(slug="extended-lab", name="Extended Lab")
        timeline = client.timelines.create(
            project="extended-lab",
            slug="primary",
            name="Primary",
            set_default=True,
            config={
                "tracks": [{"id": "main", "kind": "visual", "label": "Main"}],
                "clips": [],
                "output": {"resolution": "320x180", "fps": 24, "file": "primary.mp4"},
            },
            registry={"assets": {}},
        )
        result = client.invoke(
            "rendering.timeline_visualize",
            kind="executor",
            project="extended-lab",
            inputs={"formats": ["md"], "filmstrip": "off"},
        )
        runs = client.runs.list("extended-lab")

        assert project.ok
        assert timeline.ok
        assert result.ok
        assert result.run_id
        assert runs.ok
        assert len(runs.data or []) == 1

    with sqlite3.connect(tmp_path / ".astrid" / "astrid.sqlite3") as conn:
        packs = {str(row[0]) for row in conn.execute("SELECT pack FROM schema_migrations")}
    assert packs == {"core", "timeline", "shots", "references", "runaway"}


def test_explicit_incomplete_registry_still_rejects_pack_database(tmp_path: Path) -> None:
    # Build a canonical database with the normal composition first. Reopening
    # it with a deliberately core-only registry must retain migration safety.
    with AstridClient.open(tmp_path, registry=_extended_registry()):
        pass
    with pytest.raises(MigrationTooNewError):
        AstridClient.open(tmp_path, registry=core_only_registry())
