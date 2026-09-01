"""Negative and runtime-parity proof for the flattened schema authority."""

from __future__ import annotations

import importlib.util
import os
import re
from pathlib import Path

import pytest

from astrid.core.cli.domain_product import (
    REQUIRED_RUNTIME_MOUNTS,
    build_product_mounts,
)

ROOT = Path(__file__).resolve().parents[2]
RUNTIME_ROOT = Path(
    os.environ.get(
        "BANODOCO_RUNTIME_CHECKOUT",
        str(ROOT.parent / "banodoco-workspace-runtime-stage1-convergence"),
    )
)


def _tables(path: Path) -> set[str]:
    return {
        match.group(1).lower()
        for match in re.finditer(
            r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([A-Za-z_][A-Za-z0-9_]*)",
            path.read_text(encoding="utf-8"),
            re.IGNORECASE,
        )
    }


def test_astrid_has_no_local_schema_host_or_migrations() -> None:
    astrid = ROOT / "astrid"
    assert not (astrid / "core" / "schema_packs").exists()
    assert not list(astrid.rglob("schema-pack.yaml"))
    assert not [path for path in astrid.rglob("migrations") if path.is_dir()]
    for path in astrid.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert "astrid.core.schema_packs" not in source, path
        assert "schema-pack.yaml" not in source, path
    assert importlib.util.find_spec("astrid.core.schema_packs") is None


def test_neutral_runtime_contains_canonical_domain_tables_and_constraints() -> None:
    migration_dir = RUNTIME_ROOT / "runtime_protocol" / "migrations"
    domains = migration_dir / "003_domains.sql"
    references = migration_dir / "014_project_shots_references.sql"
    if not domains.is_file() or not references.is_file():
        pytest.skip("neutral runtime checkout is not available in this environment")

    assert {
        "timelines",
        "timeline_shots",
        "timeline_references",
        "project_documents",
        "generations",
        "generation_variants",
    } <= _tables(domains)
    assert {
        "project_shots",
        "shot_items",
        "project_references",
        "media_references",
        "reference_links",
    } <= _tables(references)

    sql = references.read_text(encoding="utf-8")
    for marker in (
        "project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE",
        "shot_id TEXT NOT NULL REFERENCES project_shots(id) ON DELETE CASCADE",
        "reference_id TEXT NOT NULL REFERENCES project_references(id) ON DELETE CASCADE",
        "from_reference_id TEXT NOT NULL REFERENCES project_references(id) ON DELETE CASCADE",
        "to_reference_id TEXT NOT NULL REFERENCES project_references(id) ON DELETE CASCADE",
        "CHECK (role = 'canonical' OR is_primary = 0)",
    ):
        assert marker in sql


def test_executable_capability_manifests_and_runtime_mounts_remain() -> None:
    manifests = list((ROOT / "astrid" / "packs").glob("*/pack.yaml"))
    assert manifests
    assert (ROOT / "astrid/packs/rendering/pack.yaml").is_file()
    assert REQUIRED_RUNTIME_MOUNTS == {
        "timelines": ("timelines",),
        "shots": ("timelines", "shots"),
        "references": ("media", "references"),
    }
    assert len(build_product_mounts()) == 7
