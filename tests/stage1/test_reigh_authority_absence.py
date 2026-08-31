"""Stage1 contract: retired hosted bridge authority is absent."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


def test_retired_authority_packages_and_routes_are_not_present() -> None:
    root = Path(__file__).resolve().parents[2]
    for rel in (
        "astrid/core/integrations/reigh",
        "astrid/core/integrations/worker",
        "astrid/packs/reigh",
        "astrid/core/contracts/remote_timeline.py",
        "scripts/reshape/editor_browser_smoke",
    ):
        assert not (root / rel).exists(), rel

    result = subprocess.run(
        [sys.executable, "-c", "import astrid, astrid.sdk, astrid.core.gateway; import sys; print([m for m in sys.modules if 'reigh' in m.lower() or 'supabase' in m.lower()])"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "[]"


def test_normal_capability_sources_have_no_reigh_ids_or_credentials() -> None:
    root = Path(__file__).resolve().parents[2]
    config = json.loads((root / "config/astrid-beta-capabilities.json").read_text())
    assert all(not row["id"].startswith("reigh.") for row in config["capabilities"])
    exemptions = json.loads((root / "astrid/core/contracts/output_result_exemptions.json").read_text())
    assert all(not value.startswith("reigh.") for value in exemptions["non_exempt"])
    assert all(not key.startswith("reigh.") for key in exemptions["exemptions"])
    assert importlib.util.find_spec("astrid.core.integrations.reigh") is None
    assert importlib.util.find_spec("astrid.core.integrations.worker") is None


def test_normal_astrid_process_never_loads_the_standalone_migrator() -> None:
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; import astrid; import astrid.sdk; import astrid.core.gateway; "
                "print([name for name in sys.modules if name.startswith('tools.astrid_migrate')])"
            ),
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "[]"


def test_canonical_runtime_lanes_have_no_bridge_or_provider_residue() -> None:
    root = Path(__file__).resolve().parents[2]
    for rel in (
        "astrid/core/rendering/remotion_runtime.py",
        "astrid/core/timeline/bundle.py",
        "astrid/core/schema_packs/catalog.py",
    ):
        assert (root / rel).is_file(), rel

    forbidden = (
        "append_imported_event",
        "_BRIDGE_CANONICAL_TOP_KEYS",
        "TimelineReadModel",
        "TimelineListRow",
        "ProjectListRow",
        "legacy_route",
        "reigh_events",
        "SUPABASE_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
    )
    for rel in ("astrid", "scripts"):
        for path in (root / rel).rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            assert not any(marker in text for marker in forbidden), path
