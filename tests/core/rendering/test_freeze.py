"""T7.6 freeze — epic-wide final assertions for the renderer epic.

These are the freeze-level locks requested by the T7.6 brief.  They reuse the
exact fixtures the earlier batches introduced (``test_service``'s fake
transport and ``test_attached_render``'s ledger harness) so the freeze
asserts the same behavior from the whole-workspace angle:

* every built-in path (remotion, ffmpeg, optimized, audio-reactive, hybrid,
  single-segment) commits exactly one video and exactly one sidecar, and
  leaves no temporary invocation workspace behind;
* every failure path (renderer, finalizer, support) removes its temporary
  artifacts and never commits a sidecar;
* attached renders create only their intended ledger (the parent run record
  and the child step's ``produces`` outputs — never a new ``run.json``);
* the package ships the frozen data (schemas + manifests + parity fixtures)
  and the default registries expose exactly the frozen built-in surface.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from importlib import resources
from pathlib import Path
from typing import Any

import pytest

from astrid.core.rendering import attached
from astrid.core.rendering.contracts import RendererManifest
from astrid.core.rendering.errors import (
    RendererBinaryMissingError,
    RendererInternalError,
)
from astrid.core.rendering.registry import (
    ExecutionEligibility,
    FinalizerRegistry,
    PlannerRegistry,
    RendererRegistry,
    RenderingCandidate,
    load_default_registries,
)
from astrid.core.rendering.service import RenderService
from astrid.core.subprocess_env import TASK_PROJECT_ENV, TASK_RUN_ID_ENV, TASK_STEP_ID_ENV

# Reuse the exact fixtures the earlier batches locked (sibling test modules;
# `tests/` is a package, and this import style is used repo-wide).
from tests.core.rendering.test_attached_render import (
    _fake_success,
    _Registry,
    _seed_parent,
    _Service,
)
from tests.core.rendering.test_package_data import FIXTURES, RENDERING_MANIFESTS, SCHEMAS
from tests.core.rendering.test_service import (
    FakeTransport,
    _plan,
    _real_media_inputs,
    _real_service,
    _request,
    _require_ffmpeg,
    _service,
)

# ---------------------------------------------------------------------------
# Every built-in path -> exactly one video + one committed sidecar
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("selector", "plan_segments", "backend_config", "expect_finalize", "expected_engine"),
    [
        pytest.param(
            "rendering.remotion", None, {}, False, "rendering.remotion", id="remotion"
        ),
        pytest.param(
            "rendering.ffmpeg", None, {}, False, "rendering.ffmpeg", id="ffmpeg"
        ),
        pytest.param(
            "rendering.ffmpeg",
            None,
            {"rendering.ffmpeg": {"mode": "optimized", "stream_copy": True}},
            False,
            "rendering.ffmpeg",
            id="optimized",
        ),
        pytest.param(
            "rendering.ffmpeg",
            None,
            {"rendering.ffmpeg": {"audio_reactive": True}},
            False,
            "rendering.ffmpeg",
            id="audio-reactive",
        ),
        pytest.param("hybrid", (5, 5), {}, True, "hybrid", id="hybrid"),
        pytest.param("hybrid", (10,), {}, True, "hybrid", id="single-segment"),
    ],
)
def test_freeze_builtin_paths_one_video_one_committed_sidecar(
    tmp_path: Path,
    selector: str,
    plan_segments: tuple[int, ...] | None,
    backend_config: dict[str, dict[str, Any]],
    expect_finalize: bool,
    expected_engine: str,
) -> None:
    transport = FakeTransport()
    if plan_segments is not None:
        transport.plan = _plan("fixture.window", segment_frames=plan_segments)
        service = _service(
            tmp_path,
            transport,
            renderer_ids=("fixture.window",),
            planner_ids=("rendering.legacy_hybrid",),
        )
    else:
        service = _service(tmp_path, transport)
    output = tmp_path / "freeze-builtin.mp4"
    request = replace(_request(tmp_path), backend_config=backend_config)

    service.render_request(request, selector=selector, out_path=output)

    # Exactly one video, committed at the requested path.
    assert sorted(tmp_path.glob("*.mp4")) == [output]
    # Exactly one committed sidecar, next to that video.
    sidecars = sorted(tmp_path.glob("*.provenance.json"))
    assert sidecars == [Path(f"{output}.provenance.json")]
    payload = json.loads(sidecars[0].read_text(encoding="utf-8"))
    assert payload["sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
    assert payload["output"] == str(output.resolve())
    assert payload["routing"]["requested_engine"] == expected_engine
    assert payload["routing"]["auto_route"] is False
    if expect_finalize:
        assert ("finalize", "rendering.ffmpeg-finalizer") in transport.calls
    else:
        assert not any(verb == "finalize" for verb, _backend in transport.calls)
    # No temporary invocation workspace survives a successful commit.
    assert not list(tmp_path.glob(".*.render-service-*"))
    assert not list(tmp_path.rglob("outputs"))


# ---------------------------------------------------------------------------
# Failure paths clean temp artifacts and never commit a sidecar
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "mode",
    ["backend-render", "finalizer", "support"],
    ids=["backend-render", "finalizer", "support"],
)
def test_freeze_failure_paths_clean_temps_and_never_commit_sidecar(
    tmp_path: Path, mode: str
) -> None:
    transport = FakeTransport()
    output = tmp_path / "freeze-failed.mp4"
    if mode == "backend-render":
        transport.fail_render = "rendering.ffmpeg"
        service = _service(tmp_path, transport)
        selector = "rendering.ffmpeg"
    elif mode == "finalizer":
        transport.fail_finalize = "rendering.ffmpeg-finalizer"
        transport.plan = _plan("fixture.window", segment_frames=(5, 5))
        service = _service(
            tmp_path,
            transport,
            renderer_ids=("fixture.window",),
            planner_ids=("rendering.legacy_hybrid",),
        )
        selector = "hybrid"
    else:
        transport.fail_support = "rendering.ffmpeg"
        service = _service(tmp_path, transport)
        selector = "rendering.ffmpeg"

    with pytest.raises(RendererInternalError):
        service.render_request(_request(tmp_path), selector=selector, out_path=output)

    # Never commit a video or a sidecar...
    assert not output.exists()
    assert not list(tmp_path.glob("*.provenance.json"))
    # ...and clean every temporary artifact (invocation workspace, backend
    # partials, backend output dirs).
    assert not list(tmp_path.glob(".*.render-service-*"))
    assert not list(tmp_path.rglob("partial.tmp"))
    assert not list(tmp_path.rglob("outputs"))


# ---------------------------------------------------------------------------
# Real-service paths through the real CommandTransport (not FakeTransport)
# ---------------------------------------------------------------------------


def test_freeze_real_ffmpeg_transport_one_video_one_committed_sidecar(
    tmp_path: Path,
) -> None:
    """The real FFmpeg backend through the real CommandTransport commits
    exactly one video and one committed sidecar and leaves no temporary
    invocation workspace behind."""
    _require_ffmpeg()
    timeline_path, assets_path = _real_media_inputs(tmp_path)
    service = _real_service(tmp_path)
    output = tmp_path / "freeze-real-ffmpeg.mp4"

    service.render_request(
        replace(
            _request(tmp_path),
            timeline_path=str(timeline_path),
            assets_registry_path=str(assets_path),
        ),
        selector="rendering.ffmpeg",
        out_path=output,
    )

    assert sorted(tmp_path.glob("*.mp4")) == [output]
    sidecars = sorted(tmp_path.glob("*.provenance.json"))
    assert sidecars == [Path(f"{output}.provenance.json")]
    payload = json.loads(sidecars[0].read_text(encoding="utf-8"))
    assert payload["sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
    assert payload["output"] == str(output.resolve())
    assert payload["routing"]["requested_engine"] == "rendering.ffmpeg"
    assert not list(tmp_path.glob(".*.render-service-*"))
    assert not list(tmp_path.rglob("outputs"))


def _missing_binary_candidate(root: Path, capability_id: str) -> RenderingCandidate[Any]:
    """A candidate whose manifest names an executable that does not exist."""
    manifest = RendererManifest(
        schema_version=1,
        id=capability_id,
        name=capability_id,
        version="1.0.0",
        protocol_version=1,
        command=("no-such-renderer-binary",),
        required_permissions=(),
        required_binaries=(),
        operations=("render", "support"),
        capabilities={"supports_windows": True},
    )
    manifest_path = root / f"{capability_id}.yaml"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text("fixture\n", encoding="utf-8")
    return RenderingCandidate(
        manifest=manifest,
        source_kind="source",
        pack_id=capability_id.split(".", 1)[0],
        pack_root=root,
        manifest_path=manifest_path,
        manifest_digest=hashlib.sha256(capability_id.encode()).hexdigest(),
        priority_index=0,
        eligibility=ExecutionEligibility(
            eligible=True,
            reason="fixture trust",
            trust_method="test",
        ),
    )


def test_freeze_real_transport_missing_binary_no_sidecar_temps_cleaned(
    tmp_path: Path,
) -> None:
    """A real failure path through the real CommandTransport (required binary
    missing) never commits a sidecar, cleans every temporary artifact, and
    still retains a replay bundle for the failed support invocation."""
    renderers = RendererRegistry(
        [_missing_binary_candidate(tmp_path, "fixture.missing")]
    )
    planners = PlannerRegistry([])
    finalizers = FinalizerRegistry([])
    service = RenderService(registries=(renderers, planners, finalizers))
    output = tmp_path / "freeze-real-failed.mp4"

    with pytest.raises(RendererBinaryMissingError):
        service.render_request(
            _request(tmp_path), selector="fixture.missing", out_path=output
        )

    assert not output.exists()
    assert not list(tmp_path.glob("*.provenance.json"))
    assert not list(tmp_path.glob(".*.render-service-*"))
    assert not list(tmp_path.rglob("partial.tmp"))
    assert not list(tmp_path.rglob("outputs"))
    # The failing support invocation still produced a replay bundle next to
    # the (never-committed) output.
    replay_bundles = list(tmp_path.glob(f".{output.name}.replay/*/bundle.json"))
    assert len(replay_bundles) == 1
    pinned = json.loads(replay_bundles[0].read_text(encoding="utf-8"))
    assert pinned["renderer_id"] == "fixture.missing"
    assert pinned["metadata"]["verb"] == "support"
    assert pinned["metadata"]["error_kind"] == "binary_missing"


# ---------------------------------------------------------------------------
# Attached renders create only their intended ledger
# ---------------------------------------------------------------------------


def test_freeze_attached_render_creates_only_its_intended_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    projects_root = tmp_path / "projects"
    _seed_parent(projects_root)  # the orchestrator's parent run record
    calls: list[object] = []
    monkeypatch.setattr(attached, "run_executor", _fake_success(calls))
    output = tmp_path / "freeze-attached" / "preview.mp4"

    attached.invoke_attached_render(
        tmp_path / "timeline.json",
        tmp_path / "assets.json",
        output,
        project_slug="demo",
        parent_run_id="parent-run",
        step_id="freeze-child",
        root=projects_root,
        executor_registry=_Registry(),
    )

    # Exactly one ledger exists anywhere: the parent run record.  The
    # attached render records outputs under that run's step tree and never
    # creates a new run.json of its own.
    assert list(projects_root.rglob("run.json")) == [
        projects_root / "demo" / "runs" / "parent-run" / "run.json"
    ]
    produces = (
        projects_root
        / "demo"
        / "runs"
        / "parent-run"
        / "steps"
        / "freeze-child"
        / "v1"
        / "produces"
    )
    assert (produces / "preview.mp4").is_file()
    assert (produces / "preview.mp4.provenance.json").is_file()
    # The intended ledger holds exactly one video and one sidecar.
    assert len(list(projects_root.rglob("*.mp4"))) == 1
    assert len(list(projects_root.rglob("*.provenance.json"))) == 1


def test_freeze_unbound_attached_falls_back_without_any_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    projects_root = tmp_path / "projects"
    monkeypatch.setenv("ASTRID_PROJECTS_ROOT", str(projects_root))
    for name in (TASK_PROJECT_ENV, TASK_RUN_ID_ENV, TASK_STEP_ID_ENV):
        monkeypatch.delenv(name, raising=False)
    service = _Service()
    output = tmp_path / "public" / "standalone.mp4"

    attached.invoke_attached_render(
        tmp_path / "timeline.json",
        tmp_path / "assets.json",
        output,
        selector="rendering.fixture",
        service=service,
    )

    assert len(service.calls) == 1
    assert not projects_root.exists()
    assert not list(tmp_path.rglob("run.json"))


# ---------------------------------------------------------------------------
# Package data: schemas + manifests + fixtures, exact built-in surface
# ---------------------------------------------------------------------------


def test_freeze_package_data_and_exact_builtin_registry_surface() -> None:
    # Schemas + parity fixtures + manifests are package resources.
    root = resources.files("astrid")
    schema_root = root.joinpath("core", "rendering", "schemas", "v1")
    fixture_root = root.joinpath("core", "rendering", "fixtures", "renderer_parity")
    assert {item.name for item in schema_root.iterdir()} >= SCHEMAS
    assert {item.name for item in fixture_root.iterdir()} >= FIXTURES
    missing = [
        path
        for path in sorted(RENDERING_MANIFESTS)
        if not root.joinpath(*path.split("/")).is_file()
    ]
    assert not missing

    # The default registries expose exactly the frozen built-in surface —
    # no extra built-in renderers/planners/finalizers beyond the epic's set.
    renderers, planners, finalizers = load_default_registries(include_installed=False)
    assert {candidate.id for candidate in renderers.list()} == {
        "rendering.remotion",
        "rendering.ffmpeg",
    }
    assert {candidate.id for candidate in planners.list()} == {
        "rendering.legacy_hybrid"
    }
    assert {candidate.id for candidate in finalizers.list()} == {
        "rendering.ffmpeg-finalizer"
    }
