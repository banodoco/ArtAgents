"""Replay-bundle capture on backend render/finalize/plan failure."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from astrid.core.foundation.hash import sha256_file
from astrid.core.rendering.contracts import (
    SCHEMA_VERSION,
    AudioOwnership,
    RenderProfile,
    RenderRequest,
    RenderResult,
    RendererManifest,
    SupportReport,
    VideoArtifact,
    compute_request_digest,
)
from astrid.core.rendering.errors import RendererInternalError, raise_internal_error
from astrid.core.rendering.publication import publish_render_result
from astrid.core.rendering.registry import (
    ExecutionEligibility,
    FinalizerRegistry,
    PlannerRegistry,
    RendererRegistry,
    RenderingCandidate,
)
from astrid.core.rendering.replay import (
    BUNDLE_FILENAME,
    ReplayBundle,
    write_replay_bundle,
)
from astrid.core.rendering.service import RenderService


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _profile() -> RenderProfile:
    return RenderProfile(
        width=160,
        height=90,
        fps_rational=(10, 1),
        time_base=(1, 10240),
        container="mp4",
        video_codec="h264",
        video_profile=None,
        video_level=None,
        pixel_format="yuv420p",
        audio_codec=None,
        audio_sample_rate=None,
        audio_channel_layout=None,
    )


def _support(backend: str) -> SupportReport:
    return SupportReport(
        schema_version=SCHEMA_VERSION,
        supported=True,
        reasons=[],
        features={"fixture": True},
        alternatives=[],
        backend=backend,
        backend_version="1.0.0",
    )


def _candidate(root: Path, capability_id: str, kind: str) -> RenderingCandidate[Any]:
    common = dict(
        schema_version=SCHEMA_VERSION,
        id=capability_id,
        name=capability_id,
        version="1.0.0",
        protocol_version=SCHEMA_VERSION,
        command=("fixture-command",),
        required_permissions=(),
        required_binaries=(),
    )
    if kind == "renderer":
        manifest = RendererManifest(
            **common,
            operations=("render", "support"),
            capabilities={"supports_windows": True},
        )
    elif kind == "planner":
        from astrid.core.rendering.contracts import PlannerManifest

        manifest = PlannerManifest(
            **common,
            operations=("plan", "support"),
            capabilities={"supports_fallback": True},
        )
    else:
        from astrid.core.rendering.contracts import FinalizerManifest

        manifest = FinalizerManifest(
            **common,
            operations=("finalize", "support"),
            capabilities={"preserves_attachments": True},
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
        manifest_digest=_digest(capability_id),
        priority_index=0,
        eligibility=ExecutionEligibility(
            eligible=True,
            reason="fixture trust",
            trust_method="test",
        ),
    )


def _request(tmp_path: Path) -> RenderRequest:
    timeline = tmp_path / "timeline.json"
    assets = tmp_path / "assets.json"
    timeline.write_text('{"tracks": [], "clips": []}', encoding="utf-8")
    assets.write_text('{"assets": {}}', encoding="utf-8")
    return RenderRequest(
        schema_version=SCHEMA_VERSION,
        timeline_path=str(timeline),
        assets_registry_path=str(assets),
        output_name="video.mp4",
    )


def _service(
    tmp_path: Path,
    transport: Any,
    *,
    replay_root: Path | None = None,
    capture_success: bool = False,
) -> RenderService:
    renderers = RendererRegistry([_candidate(tmp_path, "rendering.ffmpeg", "renderer")])
    planners = PlannerRegistry([])
    finalizers = FinalizerRegistry(
        [_candidate(tmp_path, "rendering.ffmpeg-finalizer", "finalizer")]
    )
    return RenderService(
        registries=(renderers, planners, finalizers),
        transport=transport,
        validator=lambda result, **_kwargs: result,
        publisher=publish_render_result,
        replay_root=replay_root,
        capture_success=capture_success,
    )


class FailingTransport:
    """Support succeeds; the ``render`` verb raises a structured failure."""

    def __init__(
        self,
        *,
        stdout: str = "",
        stderr: str = "",
        partial_result: Any = None,
        message: str = "fixture backend crashed",
        recovery_command: str = "retry the fixture render",
    ) -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.partial_result = partial_result
        self.message = message
        self.recovery_command = recovery_command
        self.calls: list[tuple[str, str]] = []

    def run(
        self,
        verb: str,
        command: Any,
        *,
        backend: str,
        request_path: Path,
        result_path: Path,
        cwd: Path,
        **kwargs: Any,
    ) -> Any:
        del command, cwd, kwargs
        self.calls.append((verb, backend))
        if verb == "support":
            return _support(backend)
        if verb == "render":
            if self.partial_result is not None:
                Path(result_path).write_text(
                    json.dumps(self.partial_result), encoding="utf-8"
                )
            details: dict[str, str] = {}
            if self.stdout:
                details["stdout"] = self.stdout
            if self.stderr:
                details["stderr"] = self.stderr
            raise_internal_error(
                backend=backend,
                message=self.message,
                recovery_command=self.recovery_command,
                details=details,
            )
        raise AssertionError(f"unexpected verb {verb!r}")


class SuccessTransport:
    """Support and render both succeed with a tiny fake artifact."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def run(
        self,
        verb: str,
        command: Any,
        *,
        backend: str,
        request_path: Path,
        result_path: Path,
        cwd: Path,
        **kwargs: Any,
    ) -> Any:
        del command, result_path, cwd, kwargs
        self.calls.append((verb, backend))
        if verb == "support":
            return _support(backend)
        if verb == "render":
            payload = json.loads(Path(request_path).read_text(encoding="utf-8"))
            workspace = Path(request_path).parent
            output = workspace / "outputs" / payload["output_name"]
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(b"fixture-video")
            video = VideoArtifact.from_file(
                path=output,
                workspace_root=workspace,
                profile=_profile(),
                duration_frames=10,
                audio=AudioOwnership.NONE,
                attachments={},
            )
            return RenderResult(
                schema_version=SCHEMA_VERSION,
                video=video,
                audio_ownership=AudioOwnership.NONE,
                backend_fragments={backend: {"fixture": True}},
            )
        raise AssertionError(f"unexpected verb {verb!r}")


def _bundle_dirs(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(root.glob(f"*/{BUNDLE_FILENAME}"))


def _load_bundle(bundle_json: Path) -> dict[str, Any]:
    return json.loads(bundle_json.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Failure captures the complete record
# ---------------------------------------------------------------------------


def test_failure_captures_complete_bundle(tmp_path: Path) -> None:
    request = _request(tmp_path)
    transport = FailingTransport(
        stdout="renderer boom",
        stderr="traceback line",
        partial_result={"partial": True, "frames": 3},
    )
    replay_root = tmp_path / "replays"
    service = _service(tmp_path, transport, replay_root=replay_root)
    output = tmp_path / "failed.mp4"

    with pytest.raises(RendererInternalError, match="fixture backend crashed"):
        service.render_request(
            request, selector="rendering.ffmpeg", out_path=output
        )

    bundles = _bundle_dirs(replay_root)
    assert len(bundles) == 1
    bundle_dir = bundles[0].parent
    bundle = _load_bundle(bundles[0])

    assert bundle["bundle_schema_version"] == 1
    assert bundle["renderer_id"] == "rendering.ffmpeg"
    # The pinned request digest is the digest of the LOCALIZED on-disk
    # request.json (what replay verifies), not the original absolute-path
    # request.
    localized_request = json.loads(
        (bundle_dir / "request.json").read_text(encoding="utf-8")
    )
    assert bundle["request_digest"] == compute_request_digest(localized_request)
    assert bundle["request_digest"] != compute_request_digest(request.to_dict())
    assert bundle["manifest_digest"] == _digest("rendering.ffmpeg")
    assert bundle["argv"] == [
        "fixture-command",
        "render",
        "--request",
        "request.json",
        "--result",
        "result.json",
    ]

    # Runtime documents are authoritative; replay capture does not copy
    # attempt-local timeline/assets paths into a second source of truth.
    assert bundle["inputs"] == {}
    assert json.loads(
        (bundle_dir / "request.json").read_text(encoding="utf-8")
    )["timeline_path"] == "<host-path>"

    assert bundle["logs"] == {"stdout": "renderer boom", "stderr": "traceback line"}
    # The partial result is persisted as a localized hashed file and only its
    # descriptor (never raw backend bytes) is inlined into bundle.json.
    partial_descriptor = bundle["partial_result"]
    assert set(partial_descriptor) == {"sha256", "path"}
    assert partial_descriptor["path"].startswith("partial/")
    assert bundle["result_sha256"] == partial_descriptor["sha256"]
    assert bundle["result_path"] == partial_descriptor["path"]
    partial_file = bundle_dir / partial_descriptor["path"]
    assert partial_file.is_file()
    assert json.loads(partial_file.read_text(encoding="utf-8")) == {
        "partial": True,
        "frames": 3,
    }
    # backend_config is the selected backend's configuration namespace.
    assert bundle["backend_config"] == {}

    # The support report that preceded the failing render is captured.
    assert bundle["support_report"] == _support("rendering.ffmpeg").to_dict()

    metadata = bundle["metadata"]
    assert metadata["backend_version"] == "1.0.0"
    assert metadata["verb"] == "render"
    assert metadata["success"] is False
    assert metadata["error_kind"] == "internal"
    assert metadata["error_message"] == "fixture backend crashed"
    assert metadata["recovery_command"] == "retry the fixture render"
    # Qualified-ID discovery/trust identity rides in the metadata.
    assert metadata["source_pack"] == "rendering"
    assert metadata["source_kind"] == "source"
    assert metadata["eligibility"]["eligible"] is True
    assert metadata["eligibility"]["trust_method"] == "test"
    assert metadata["trust_method"] == "test"

    assert list((bundle_dir / "inputs").iterdir()) == []


# ---------------------------------------------------------------------------
# Redaction of credentials and URLs
# ---------------------------------------------------------------------------


def test_credentials_and_urls_redacted_from_logs_and_metadata(
    tmp_path: Path,
) -> None:
    stdout = (
        "begin render\n"
        "Authorization: Bearer sk-test-secret-123456789012\n"
        "fetch https://example.com/api?token=abc123&x=1\n"
    )
    transport = FailingTransport(
        stdout=stdout,
        message="crashed with sk-abc-secret-123456789012",
        recovery_command="retry at https://example.com/upload?api_key=supersecret",
    )
    replay_root = tmp_path / "replays"
    service = _service(tmp_path, transport, replay_root=replay_root)

    with pytest.raises(RendererInternalError):
        service.render_request(
            _request(tmp_path), selector="rendering.ffmpeg", out_path=tmp_path / "x.mp4"
        )

    bundles = _bundle_dirs(replay_root)
    assert len(bundles) == 1
    bundle = _load_bundle(bundles[0])
    bundle_text = json.dumps(bundle)

    assert "sk-test-secret-123456789012" not in bundle_text
    assert "sk-abc-secret-123456789012" not in bundle_text
    assert "abc123" not in bundle_text
    assert "supersecret" not in bundle_text

    logs = bundle["logs"]["stdout"]
    assert "Authorization: [redacted]" in logs
    assert "token=[redacted]" in logs

    metadata = bundle["metadata"]
    assert "sk-abc-secret-123456789012" not in metadata["error_message"]
    assert "[redacted]" in metadata["error_message"]
    assert "api_key=[redacted]" in metadata["recovery_command"]


def test_write_replay_bundle_redacts_logs_metadata_and_localizes_argv(
    tmp_path: Path,
) -> None:
    bundle = ReplayBundle(
        renderer_id="rendering.ffmpeg",
        request_digest="0" * 64,
        manifest_digest="1" * 64,
        argv=[
            "tool",
            "render",
            "--request",
            "/host/workspace/req.json",
            "--result",
            "/host/workspace/res.json",
        ],
        inputs={},
        logs={"stdout": "Authorization: Bearer sk-abcdefghijklmnop"},
        metadata={"recovery_command": "see https://example.com?access_token=xyz"},
    )

    dest = write_replay_bundle(bundle, tmp_path / "bundle")

    payload = _load_bundle(dest / BUNDLE_FILENAME)
    assert "/host/workspace/req.json" not in json.dumps(payload)
    assert payload["argv"] == [
        "tool",
        "render",
        "--request",
        "request.json",
        "--result",
        "result.json",
    ]
    assert payload["logs"]["stdout"] == "Authorization: [redacted]"
    assert payload["metadata"]["recovery_command"] == (
        "see https://example.com?access_token=[redacted]"
    )


# ---------------------------------------------------------------------------
# Ownership: project run vs explicit root vs default sibling
# ---------------------------------------------------------------------------


def test_project_run_owns_bundle_under_run_logs_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ASTRID_TASK_PROJECT", "demo")
    monkeypatch.setenv("ASTRID_TASK_RUN_ID", "run-001")
    monkeypatch.setenv("ASTRID_PROJECTS_ROOT", str(tmp_path / "projects"))
    transport = FailingTransport()
    service = _service(tmp_path, transport, replay_root=tmp_path / "replays")

    with pytest.raises(RendererInternalError):
        service.render_request(
            _request(tmp_path), selector="rendering.ffmpeg", out_path=tmp_path / "x.mp4"
        )

    run_replays = (
        tmp_path
        / "projects"
        / "demo"
        / "runs"
        / "run-001"
        / "logs"
        / "replays"
    )
    bundles = _bundle_dirs(run_replays)
    assert len(bundles) == 1
    assert _load_bundle(bundles[0])["renderer_id"] == "rendering.ffmpeg"
    # The explicit root must NOT own a run-attached bundle.
    assert not (tmp_path / "replays").exists()


def test_explicit_replay_root_owns_bundle_when_not_attached(tmp_path: Path) -> None:
    transport = FailingTransport()
    replay_root = tmp_path / "replays"
    service = _service(tmp_path, transport, replay_root=replay_root)

    with pytest.raises(RendererInternalError):
        service.render_request(
            _request(tmp_path), selector="rendering.ffmpeg", out_path=tmp_path / "x.mp4"
        )

    bundles = _bundle_dirs(replay_root)
    assert len(bundles) == 1
    assert _load_bundle(bundles[0])["renderer_id"] == "rendering.ffmpeg"


def test_default_sibling_of_output_when_no_root_configured(tmp_path: Path) -> None:
    transport = FailingTransport()
    service = _service(tmp_path, transport)
    output = tmp_path / "failed.mp4"

    with pytest.raises(RendererInternalError):
        service.render_request(
            _request(tmp_path), selector="rendering.ffmpeg", out_path=output
        )

    bundles = _bundle_dirs(tmp_path / ".failed.mp4.replay")
    assert len(bundles) == 1
    assert _load_bundle(bundles[0])["renderer_id"] == "rendering.ffmpeg"


# ---------------------------------------------------------------------------
# Localized hashed inputs; no absolute host paths in the bundle
# ---------------------------------------------------------------------------


def test_runtime_authority_does_not_copy_attempt_inputs(tmp_path: Path) -> None:
    theme = tmp_path / "theme.json"
    theme.write_text(json.dumps({"name": "fixture-theme"}), encoding="utf-8")
    timeline = tmp_path / "timeline.json"
    timeline.write_text(
        json.dumps({"theme": str(theme), "tracks": [], "clips": []}),
        encoding="utf-8",
    )
    assets = tmp_path / "assets.json"
    assets.write_text('{"assets": {}}', encoding="utf-8")
    request = RenderRequest(
        schema_version=SCHEMA_VERSION,
        timeline_path=str(timeline),
        assets_registry_path=str(assets),
        output_name="video.mp4",
    )
    transport = FailingTransport()
    replay_root = tmp_path / "replays"
    service = _service(tmp_path, transport, replay_root=replay_root)

    with pytest.raises(RendererInternalError):
        service.render_request(
            request, selector="rendering.ffmpeg", out_path=tmp_path / "x.mp4"
        )

    bundles = _bundle_dirs(replay_root)
    assert len(bundles) == 1
    bundle_dir = bundles[0].parent
    bundle = _load_bundle(bundles[0])

    assert bundle["inputs"] == {}
    host_text = str(tmp_path)
    bundle_text = json.dumps(bundle)
    assert host_text not in bundle_text
    assert host_text not in (bundle_dir / "request.json").read_text(
        encoding="utf-8"
    )

    localized_request = json.loads(
        (bundle_dir / "request.json").read_text(encoding="utf-8")
    )
    assert localized_request["timeline_path"] == "<host-path>"
    assert localized_request["assets_registry_path"] == "<host-path>"
    assert list((bundle_dir / "inputs").iterdir()) == []


def test_replay_request_redacts_attempt_paths_without_input_copies(tmp_path: Path) -> None:
    """Replay metadata contains no absolute attempt-local paths."""
    from astrid.core.foundation.paths import REPO_ROOT

    missing = REPO_ROOT / "definitely-not-a-captured-input.mp4"
    timeline = tmp_path / "timeline.json"
    timeline.write_text(
        json.dumps(
            {
                "theme": "banodoco-default",
                "clips": [
                    {
                        "id": "a",
                        "file": str(missing),
                        "label": "not a path value",
                        "duration": 1.5,
                    }
                ],
                "tracks": [],
            }
        ),
        encoding="utf-8",
    )
    assets = tmp_path / "assets.json"
    assets.write_text('{"assets": {}}', encoding="utf-8")
    request = RenderRequest(
        schema_version=SCHEMA_VERSION,
        timeline_path=str(timeline),
        assets_registry_path=str(assets),
        output_name="video.mp4",
    )
    service = _service(tmp_path, FailingTransport(), replay_root=tmp_path / "replays")

    with pytest.raises(RendererInternalError):
        service.render_request(
            request, selector="rendering.ffmpeg", out_path=tmp_path / "x.mp4"
        )

    bundle_dir = _bundle_dirs(tmp_path / "replays")[0].parent
    bundle = _load_bundle(bundle_dir / BUNDLE_FILENAME)
    assert bundle["inputs"] == {}
    request_copy = (bundle_dir / "request.json").read_text(encoding="utf-8")
    assert str(missing) not in request_copy
    assert '"timeline_path": "<host-path>"' in request_copy


def test_partial_result_redacted_and_written_as_hashed_file(tmp_path: Path) -> None:
    """Backend-authored partial results are redacted before being persisted."""
    partial = {
        "frames": 3,
        "asset_url": "https://example.com/asset.mp4?token=abc123",
        "auth": "Authorization: Bearer sk-test-abcdefghijklmnop",
    }
    transport = FailingTransport(partial_result=partial)
    service = _service(tmp_path, transport, replay_root=tmp_path / "replays")

    with pytest.raises(RendererInternalError):
        service.render_request(
            _request(tmp_path), selector="rendering.ffmpeg", out_path=tmp_path / "x.mp4"
        )

    bundle_dir = _bundle_dirs(tmp_path / "replays")[0].parent
    bundle = _load_bundle(bundle_dir / BUNDLE_FILENAME)
    partial_file = bundle_dir / bundle["partial_result"]["path"]
    partial_text = partial_file.read_text(encoding="utf-8")
    assert "abc123" not in partial_text
    assert "sk-test-abcdefghijklmnop" not in partial_text
    assert "[redacted]" in partial_text
    # The descriptor pins the redacted content that is actually on disk.
    assert bundle["result_sha256"] == sha256_file(partial_file)
    assert bundle["result_path"] == bundle["partial_result"]["path"]


def test_support_failure_captures_replay_bundle(tmp_path: Path) -> None:
    """A support probe that fails with a backend bug produces a replay bundle."""

    class FailingSupportTransport:
        def run(
            self,
            verb: str,
            command: Any,
            *,
            backend: str,
            request_path: Path,
            result_path: Path,
            cwd: Path,
            **kwargs: Any,
        ) -> Any:
            del command, request_path, result_path, cwd, kwargs
            if verb == "support":
                raise_internal_error(
                    backend=backend,
                    message="support probe crashed",
                    recovery_command="fix the support probe",
                )
            raise AssertionError(f"unexpected verb {verb!r}")

    replay_root = tmp_path / "replays"
    service = _service(tmp_path, FailingSupportTransport(), replay_root=replay_root)

    with pytest.raises(RendererInternalError, match="support probe crashed"):
        service.render_request(
            _request(tmp_path),
            selector="rendering.ffmpeg",
            out_path=tmp_path / "x.mp4",
        )

    bundles = _bundle_dirs(replay_root)
    assert len(bundles) == 1
    bundle = _load_bundle(bundles[0])
    assert bundle["renderer_id"] == "rendering.ffmpeg"
    assert bundle["metadata"]["verb"] == "support"
    assert bundle["metadata"]["success"] is False
    assert bundle["metadata"]["error_kind"] == "internal"
    assert bundle["metadata"]["error_message"] == "support probe crashed"
    # No support report precedes a failing support invocation.
    assert bundle["support_report"] is None


# ---------------------------------------------------------------------------
# Success does not capture unless explicitly requested
# ---------------------------------------------------------------------------


def test_no_bundle_on_success_unless_explicitly_requested(tmp_path: Path) -> None:
    replay_root = tmp_path / "replays"

    service = _service(tmp_path, SuccessTransport(), replay_root=replay_root)
    service.render_request(
        _request(tmp_path), selector="rendering.ffmpeg", out_path=tmp_path / "ok.mp4"
    )
    assert not (tmp_path / "replays").exists()

    capture_service = _service(
        tmp_path,
        SuccessTransport(),
        replay_root=replay_root,
        capture_success=True,
    )
    capture_service.render_request(
        _request(tmp_path),
        selector="rendering.ffmpeg",
        out_path=tmp_path / "ok2.mp4",
    )

    bundles = _bundle_dirs(replay_root)
    assert len(bundles) == 1
    bundle = _load_bundle(bundles[0])
    assert bundle["metadata"]["success"] is True
    assert bundle["metadata"]["error_kind"] is None
    assert bundle["metadata"]["error_message"] is None
    assert bundle["metadata"]["verb"] == "render"
    assert bundle["renderer_id"] == "rendering.ffmpeg"


def test_absolute_host_paths_including_tmp_are_redacted(tmp_path: Path) -> None:
    """Any absolute host path (repo, home, /tmp, /var/folders, other volume)
    must be redacted in the persisted bundle metadata — never left verbatim."""
    from astrid.core.rendering.replay import ReplayBundle, write_replay_bundle

    bundle = ReplayBundle(
        renderer_id="rendering.ffmpeg",
        request_digest="0" * 64,
        manifest_digest="0" * 64,
        argv=["python3", "run.py", "render", "--request", "/tmp/req.json", "--result", "/tmp/res.json"],
        metadata={
            "host_hint": "/private/var/folders/ab/cdefghijklmnopqrstuvwxyz/T/tmpXXXX/input.mp4",
            "tmp_hint": "/tmp/scratch/theme.json",
            "plain": "not a path",
        },
    )
    dest = write_replay_bundle(bundle, tmp_path / "bundle")
    payload = json.loads((dest / "bundle.json").read_text(encoding="utf-8"))
    metadata = payload["metadata"]
    assert "private/var" not in metadata["host_hint"]
    assert "tmpXXXX" not in metadata["host_hint"]
    assert "/tmp" not in metadata["tmp_hint"]
    assert metadata["plain"] == "not a path"
    assert "host-path" in metadata["host_hint"]
