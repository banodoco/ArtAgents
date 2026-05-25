"""Optional renderer parity gate against sprint-08 timeline fixtures.

The sprint-08 helpers ``createAgentWorkflowTimelineFixture`` /
``createEmbedDemoTimelineFixture`` live outside this repository until their JSON
snapshots and golden hashes are committed under ``tests/fixtures/sprint08/``.
The integration is therefore explicitly opt-in via ``ASTRID_RENDERER_PARITY=1``.
When opted in, missing helpers, malformed manifests, missing fixture files, and
missing goldens are concrete assertion failures rather than silent skips.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXPORT_HELPER = ROOT / "scripts" / "node" / "export_fixtures.mjs"
RUN_RENDERER_PARITY = os.environ.get("ASTRID_RENDERER_PARITY") == "1"


def _node_available() -> bool:
    return shutil.which("node") is not None


def _run_export_helper() -> dict:
    assert EXPORT_HELPER.is_file(), f"renderer parity export helper missing: {EXPORT_HELPER}"
    assert _node_available(), "node not available; renderer parity helper requires Node ESM"
    result = subprocess.run(
        ["node", str(EXPORT_HELPER), "--json"],
        capture_output=True,
        check=False,
        text=True,
    )
    assert result.returncode == 0, (
        f"export_fixtures.mjs failed with {result.returncode}: stderr={result.stderr!r}"
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"export_fixtures.mjs returned non-JSON output: {result.stdout!r}") from exc


def _canonical_hash(payload) -> str:
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@pytest.mark.renderer_parity
def test_renderer_parity_against_sprint08_fixtures() -> None:
    if not RUN_RENDERER_PARITY:
        pytest.skip("renderer parity integration is opt-in; set ASTRID_RENDERER_PARITY=1")
    manifest = _run_export_helper()

    fixtures = manifest.get("fixtures") or []
    assert fixtures, (
        "no sprint-08 fixtures committed under tests/fixtures/sprint08/. "
        "Snapshot createAgentWorkflowTimelineFixture/createEmbedDemoTimelineFixture from "
        "reigh-app/src/tools/video-editor/testing.ts and commit the JSON + golden hashes."
    )

    pending_goldens = [fixture["name"] for fixture in fixtures if not fixture.get("golden_hash")]
    assert not pending_goldens, (
        "sprint-08 fixtures present but goldens missing: "
        + ", ".join(pending_goldens)
        + ". Generate goldens via the headless render path and commit the .sha256 files."
    )

    for fixture in fixtures:
        path = Path(fixture["fixture_path"])
        assert path.is_file(), f"renderer parity fixture file missing for {fixture['name']}: {path}"
        payload = json.loads(path.read_text(encoding="utf-8"))
        actual = _canonical_hash(payload)
        expected = fixture["golden_hash"]
        assert actual == expected, (
            f"renderer parity hash mismatch for {fixture['name']}: "
            f"expected={expected} actual={actual}"
        )
