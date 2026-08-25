"""Self-contained pytest fixture builders for local bridge testing.

These fixtures create isolated temp Astrid project roots, projects,
timelines, assembly/identity sidecars, registry files, and small media
files — all without depending on any external filesystem state.

Coverage:
- Legacy direct-assembly (assembly.json only, no assembly.identity.json)
- Event-log-like identity sidecar (assembly.json + assembly.identity.json)
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Low-level data factories
# ---------------------------------------------------------------------------

def make_timeline_id() -> str:
    """Return a stable RFC 9562 UUID v7 string for a timeline identity."""
    return str(uuid.uuid4())


def make_ulid() -> str:
    """Return a ULID-like string for timeline directory names."""
    from astrid.core.threads.ids import generate_ulid

    return generate_ulid()


def make_project_slug() -> str:
    """Return a unique project slug for fixture isolation."""
    return f"proj-{uuid.uuid4().hex[:8]}"


def make_assembly_json(
    *,
    clips: list[dict[str, Any]] | None = None,
    tracks: list[dict[str, Any]] | None = None,
    output: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a minimal assembly.json payload."""
    return {
        "output": output or {"resolution": "1920x1080", "fps": 24, "file": "output.mp4"},
        "clips": clips or [],
        "tracks": tracks or [],
    }


def make_identity_json(
    *,
    timeline_id: str | None = None,
    provenance: str = "created",
    backend: str = "local_fs",
) -> dict[str, Any]:
    """Build an assembly.identity.json payload."""
    return {
        "timeline_id": timeline_id or make_timeline_id(),
        "provenance": provenance,
        "backend": backend,
    }


def make_project_json(
    *,
    slug: str | None = None,
    name: str | None = None,
    default_timeline_id: str | None = None,
) -> dict[str, Any]:
    """Build a project.json payload."""
    s = slug or make_project_slug()
    return {
        "created_at": "2026-05-11T00:00:00Z",
        "name": name or s,
        "schema_version": 1,
        "slug": s,
        "updated_at": "2026-05-11T00:00:00Z",
        "default_timeline_id": default_timeline_id,
    }


def make_registry_json(
    assets: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a registry.json payload."""
    return {"assets": assets or {}}


# ---------------------------------------------------------------------------
# Temp project root fixture (the top-level container)
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_bridge_root(tmp_path: Path) -> Path:
    """Return a fixture-owned, empty projects root for bridge tests.

    The repository-wide autouse sandbox creates ``workspace-config``,
    ``astrid-home``, and ``projects`` beside ``tmp_path``. Keep the bridge
    root nested so tests can distinguish fixture setup from seed mutations.
    """
    root = tmp_path / "bridge-projects"
    root.mkdir()
    return root


# ---------------------------------------------------------------------------
# Project fixture builders
# ---------------------------------------------------------------------------

@pytest.fixture
def seed_bridge_project(tmp_bridge_root: Path) -> Callable[..., Path]:
    """Return a callable that creates a project directory tree in the bridge root.

    Creates::

        <root>/
          <slug>/
            project.json
            sources/       (empty by default)
            timelines/
              <ulid>/
                assembly.json
                assembly.identity.json
                registry.json
                display.json
                manifest.json
    """

    def _seed(
        *,
        slug: str | None = None,
        timeline_ulid: str | None = None,
        timeline_id: str | None = None,
        clips: list[dict[str, Any]] | None = None,
        tracks: list[dict[str, Any]] | None = None,
        output: dict[str, Any] | None = None,
        assets: dict[str, Any] | None = None,
        with_identity: bool = True,
        with_display: bool = True,
        with_manifest: bool = True,
        with_registry: bool = True,
        with_sources: bool = True,
        identity_provenance: str = "created",
    ) -> Path:
        s = slug or make_project_slug()
        ulid = timeline_ulid or make_ulid()
        tid = timeline_id or make_timeline_id()

        pdir = tmp_bridge_root / s
        pdir.mkdir(parents=True, exist_ok=True)

        # project.json
        (pdir / "project.json").write_text(
            json.dumps(make_project_json(slug=s, name=s, default_timeline_id=tid)),
            encoding="utf-8",
        )

        # sources/
        if with_sources:
            (pdir / "sources").mkdir(parents=True, exist_ok=True)

        # timeline dir
        tdir = pdir / "timelines" / ulid
        tdir.mkdir(parents=True, exist_ok=True)

        # assembly.json
        (tdir / "assembly.json").write_text(
            json.dumps(make_assembly_json(clips=clips, tracks=tracks, output=output)),
            encoding="utf-8",
        )

        # assembly.identity.json
        if with_identity:
            (tdir / "assembly.identity.json").write_text(
                json.dumps(make_identity_json(timeline_id=tid, provenance=identity_provenance)),
                encoding="utf-8",
            )

        # registry.json
        if with_registry:
            (tdir / "registry.json").write_text(
                json.dumps(make_registry_json(assets=assets or {})),
                encoding="utf-8",
            )

        # display.json
        if with_display:
            (tdir / "display.json").write_text(
                json.dumps({
                    "schema_version": 1,
                    "slug": "primary",
                    "name": "Primary",
                    "is_default": True,
                }),
                encoding="utf-8",
            )

        # manifest.json
        if with_manifest:
            (tdir / "manifest.json").write_text(
                json.dumps({
                    "schema_version": 1,
                    "contributing_runs": [],
                    "final_outputs": [],
                    "tombstoned_at": None,
                }),
                encoding="utf-8",
            )

        return pdir

    return _seed


# ---------------------------------------------------------------------------
# Timeline fixture accessors
# ---------------------------------------------------------------------------

def bridge_timeline_dir(project_dir: Path, timeline_ulid: str) -> Path:
    """Return the timeline directory inside a seeded bridge project."""
    return project_dir / "timelines" / timeline_ulid


def read_bridge_identity(project_dir: Path, timeline_ulid: str) -> dict[str, Any]:
    """Read assembly.identity.json from a bridge project timeline."""
    path = bridge_timeline_dir(project_dir, timeline_ulid) / "assembly.identity.json"
    return json.loads(path.read_text(encoding="utf-8"))


def read_bridge_assembly(project_dir: Path, timeline_ulid: str) -> dict[str, Any]:
    """Read assembly.json from a bridge project timeline."""
    path = bridge_timeline_dir(project_dir, timeline_ulid) / "assembly.json"
    return json.loads(path.read_text(encoding="utf-8"))


def read_bridge_registry(project_dir: Path, timeline_ulid: str) -> dict[str, Any]:
    """Read registry.json from a bridge project timeline."""
    path = bridge_timeline_dir(project_dir, timeline_ulid) / "registry.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def _staged_binding_runtimes(
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stage marker-only binding runtimes for admission-level tests."""
    root = tmp_path_factory.mktemp("binding-runtimes")
    vibecomfy = root / "VibeComfy"
    vibecomfy.mkdir()
    (vibecomfy / "pyproject.toml").write_text("", encoding="utf-8")
    wgp = root / "Wan2GP"
    wgp.mkdir()
    (wgp / "wgp.py").write_text("", encoding="utf-8")
    (wgp / "defaults").mkdir()
    monkeypatch.setenv("REIGH_VIBECOMFY_HOME", str(vibecomfy))
    monkeypatch.setenv("REIGH_WGP_HOME", str(wgp))
