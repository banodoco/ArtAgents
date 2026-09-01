"""Stage-one pack composition stays checkout-only."""

from __future__ import annotations

import ast
import pkgutil
from pathlib import Path

import astrid.packs
import astrid.sdk
from astrid.core.cli.domain_product import REQUIRED_RUNTIME_MOUNTS, build_product_mounts


ROOT = Path(__file__).resolve().parents[2]


def test_packs_registry_keeps_only_checkout_composition() -> None:
    assert REQUIRED_RUNTIME_MOUNTS == {
        "timelines": ("timelines",),
        "shots": ("timelines", "shots"),
        "references": ("media", "references"),
    }
    assert len(build_product_mounts()) == 7
    assert not hasattr(astrid.packs, "STANDARD_SCHEMA_PACKS")
    assert not hasattr(astrid.packs, "build_standard_registry")
    assert not hasattr(astrid.packs, "compose_standard_bridge")
    assert not hasattr(astrid.packs, "open_standard_writer")


def test_pack_production_modules_have_no_local_service_or_bridge_imports() -> None:
    paths = [ROOT / "astrid/packs/__init__.py"]
    paths.extend(sorted((ROOT / "astrid/packs").rglob("*.py")))
    forbidden = (
        "astrid.application",
        "astrid.sdk.projects",
        "astrid.sdk.media",
        "astrid.sdk.timelines",
        "astrid.sdk.runs",
        "astrid.sdk.tasks",
        "astrid.sdk.references",
        "astrid.sdk.shots",
        "astrid.packs.timeline.bridge",
    )
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imports = [ast.unparse(node) for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
        assert not any(any(name in value for name in forbidden) for value in imports), path


def test_retired_local_timeline_bridge_is_not_a_pack_authority() -> None:
    assert not (ROOT / "astrid/packs/timeline/bridge.py").exists()


def test_sdk_surface_has_no_retired_local_service_modules() -> None:
    """The generated SDK surface no longer advertises local service facades."""
    retired = {
        "projects",
        "media",
        "timelines",
        "runs",
        "tasks",
        "references",
        "shots",
    }
    assert not retired.intersection(astrid.sdk.__all__)
    available = {name for _, name, _ in pkgutil.iter_modules(astrid.sdk.__path__)}
    assert not retired.intersection(available)
    assert all(not (ROOT / "astrid/sdk" / f"{name}.py").exists() for name in retired)
