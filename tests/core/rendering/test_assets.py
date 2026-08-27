from __future__ import annotations

import contextlib
import errno
import hashlib
import os
import shutil
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pytest

from astrid.core import timeline
from astrid.core.rendering import assets as asset_service
from astrid.core.rendering.assets import AssetMaterializer, InvocationAssetServer


def _write_registry(path: Path, assets: dict[str, dict[str, object]]) -> Path:
    timeline.save_registry({"assets": assets}, path)
    return path


def _read(
    url: str,
    *,
    range_header: str | None = None,
    origin: str | None = None,
) -> tuple[int, object, bytes]:
    headers = {}
    if range_header is not None:
        headers["Range"] = range_header
    if origin is not None:
        headers["Origin"] = origin
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=5) as response:
        return response.status, response.headers, response.read()


@contextlib.contextmanager
def _running_server(staging_dir: Path) -> Iterator[InvocationAssetServer]:
    server = InvocationAssetServer(staging_dir)
    try:
        server.__enter__()
    except PermissionError:
        pytest.skip("local HTTP server bind is not permitted in this sandbox")
    try:
        yield server
    finally:
        server.__exit__(None, None, None)


def test_local_path_is_staged_and_served_then_cleaned(tmp_path: Path) -> None:
    source = tmp_path / "source.bin"
    source.write_bytes(b"local asset bytes")
    registry_path = _write_registry(
        tmp_path / "hype.assets.json",
        {"main": {"file": source.name, "type": "application/octet-stream"}},
    )

    with AssetMaterializer(registry_path) as materializer:
        staging_dir = materializer.staging_dir
        staged = materializer.assets["main"]
        assert staged.kind == "local"
        assert staged.local_path is not None
        assert staged.local_path != source
        assert staged.local_path.parent == staging_dir
        assert staged.local_path.read_bytes() == source.read_bytes()

        with _running_server(staging_dir) as server:
            resolved = materializer.resolved_registry(server)
            local_url = resolved["assets"]["main"]["file"]
            assert local_url == staged.local_url
            status, headers, body = _read(local_url)
            assert status == 200
            assert headers["Accept-Ranges"] == "bytes"
            assert body == source.read_bytes()

    assert not staging_dir.exists()


def test_cached_url_is_staged_and_local_url_supports_range_resume(tmp_path: Path) -> None:
    payload = b"0123456789abcdef"
    cached = tmp_path / "shared-cache" / "cached.mp4"
    cached.parent.mkdir()
    cached.write_bytes(payload)
    url = "https://cdn.example.invalid/video.mp4"
    content_sha256 = hashlib.sha256(payload).hexdigest()
    registry_dir = tmp_path / "render"
    registry_dir.mkdir()
    registry_path = _write_registry(
        registry_dir / "hype.assets.json",
        {"video": {"url": url, "content_sha256": content_sha256, "type": "video/mp4"}},
    )
    calls: list[tuple[str, str | None]] = []

    def fake_fetch(requested_url: str, *, expected_sha256: str | None = None) -> Path:
        calls.append((requested_url, expected_sha256))
        return cached

    with AssetMaterializer(
        registry_path,
        cache_fetch=fake_fetch,
        remote_probe=lambda _url: False,
    ) as materializer:
        staged = materializer.assets["video"]
        assert staged.kind == "cached"
        assert staged.local_path is not None
        assert staged.local_path.parent == materializer.staging_dir
        assert staged.local_path.read_bytes() == payload
        with _running_server(materializer.staging_dir) as server:
            local_url = materializer.resolved_registry(server)["assets"]["video"]["file"]
            status, headers, body = _read(local_url, range_header="bytes=5-")

    assert calls == [(url, content_sha256)]
    assert status == 206
    assert headers["Content-Range"] == f"bytes 5-{len(payload) - 1}/{len(payload)}"
    assert body == payload[5:]


def test_already_remote_url_is_preserved_without_download(tmp_path: Path) -> None:
    url = "https://cdn.example.invalid/range-capable.mp4"
    registry_path = _write_registry(
        tmp_path / "hype.assets.json",
        {"video": {"url": url, "type": "video/mp4"}},
    )

    def unexpected_fetch(*args: object, **kwargs: object) -> Path:
        pytest.fail(f"remote URL was unexpectedly downloaded: {args!r} {kwargs!r}")

    with AssetMaterializer(
        registry_path,
        cache_fetch=unexpected_fetch,
        remote_probe=lambda _url: True,
    ) as materializer:
        asset = materializer.assets["video"]
        assert asset.kind == "remote"
        assert asset.local_path is None
        assert asset.remote_url == url
        assert materializer.needs_server is False
        resolved = materializer.resolved_registry()
        assert resolved["assets"]["video"]["file"] == url


def test_preexisting_cache_does_not_force_range_capable_url_local(tmp_path: Path) -> None:
    url = "https://cdn.example.invalid/already-cached.mp4"
    cached = tmp_path / "cache.mp4"
    cached.write_bytes(b"cached")
    registry_path = _write_registry(
        tmp_path / "hype.assets.json",
        {"video": {"url": url, "content_sha256": hashlib.sha256(b"cached").hexdigest()}},
    )

    def unexpected_fetch(*args: object, **kwargs: object) -> Path:
        pytest.fail(f"range-capable URL unexpectedly used cache: {args!r} {kwargs!r}")

    with AssetMaterializer(
        registry_path,
        cache_fetch=unexpected_fetch,
        remote_probe=lambda _url: True,
    ) as materializer:
        assert materializer.assets["video"].kind == "remote"
        assert materializer.resolved_registry()["assets"]["video"]["file"] == url


def test_traversal_and_cross_project_paths_are_rejected(tmp_path: Path) -> None:
    project_a = tmp_path / "projects" / "a"
    project_b = tmp_path / "projects" / "b"
    run_dir = project_a / "runs" / "render"
    run_dir.mkdir(parents=True)
    project_b.mkdir(parents=True)
    (project_a / "outside-run.mp4").write_bytes(b"inside project, outside run")
    foreign = project_b / "foreign.mp4"
    foreign.write_bytes(b"other project")

    traversal_registry = _write_registry(
        run_dir / "traversal.assets.json",
        {"bad": {"file": "../../outside-run.mp4"}},
    )
    with pytest.raises(ValueError, match="path traversal"):
        AssetMaterializer(traversal_registry, allowed_root=project_a)

    foreign_registry = _write_registry(
        run_dir / "foreign.assets.json",
        {"bad": {"file": str(foreign)}},
    )
    with pytest.raises(ValueError, match="outside the allowed project root"):
        AssetMaterializer(foreign_registry, allowed_root=project_a)


def test_managed_project_rejects_sibling_project_without_explicit_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    projects_root = tmp_path / "projects"
    project_a = projects_root / "a"
    project_b = projects_root / "b"
    run_dir = project_a / "runs" / "render"
    run_dir.mkdir(parents=True)
    project_b.mkdir(parents=True)
    foreign = project_b / "foreign.mp4"
    foreign.write_bytes(b"other project")
    registry_path = _write_registry(
        run_dir / "hype.assets.json",
        {"bad": {"file": str(foreign)}},
    )
    monkeypatch.setenv("ASTRID_PROJECTS_ROOT", str(projects_root))
    monkeypatch.setenv("ASTRID_PROJECT_SLUG", "a")

    with pytest.raises(ValueError, match="outside the allowed project root"):
        AssetMaterializer(registry_path)


def test_owned_managed_locator_is_allowed_only_by_exact_hash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    projects_root = tmp_path / "projects"
    project = projects_root / "project"
    project.mkdir(parents=True)
    managed = projects_root / ".astrid" / "media" / "sha256" / "aa" / "bb" / "asset.bin"
    managed.parent.mkdir(parents=True)
    managed.write_bytes(b"owned managed bytes")
    monkeypatch.setenv("ASTRID_PROJECTS_ROOT", str(projects_root))
    digest = hashlib.sha256(managed.read_bytes()).hexdigest()
    registry_path = _write_registry(
        project / "hype.assets.json",
        {"asset": {"file": str(managed)}},
    )

    with AssetMaterializer(
        registry_path,
        allowed_root=project,
        allowed_managed_paths={managed: digest},
    ) as materializer:
        staged = materializer.assets["asset"].local_path
        assert staged is not None
        assert staged.read_bytes() == managed.read_bytes()

    managed.write_bytes(b"tampered managed bytes")
    with pytest.raises(ValueError, match="failed integrity check"):
        AssetMaterializer(
            registry_path,
            allowed_root=project,
            allowed_managed_paths={managed: digest},
        )


def test_managed_asset_free_registry_may_be_invocation_temporary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    projects_root = tmp_path / "projects"
    (projects_root / "a").mkdir(parents=True)
    registry_path = _write_registry(tmp_path / "hype.assets.json", {})
    monkeypatch.setenv("ASTRID_PROJECTS_ROOT", str(projects_root))
    monkeypatch.setenv("ASTRID_PROJECT_SLUG", "a")

    with AssetMaterializer(registry_path) as materializer:
        assert materializer.assets == {}
        assert materializer.resolved_registry() == {"assets": {}}


def test_managed_nonempty_registry_must_be_inside_owner_project(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    projects_root = tmp_path / "projects"
    (projects_root / "a").mkdir(parents=True)
    outside_registry = _write_registry(
        tmp_path / "hype.assets.json",
        {"remote": {"url": "https://cdn.example.invalid/video.mp4"}},
    )
    monkeypatch.setenv("ASTRID_PROJECTS_ROOT", str(projects_root))
    monkeypatch.setenv("ASTRID_PROJECT_SLUG", "a")

    with pytest.raises(ValueError, match="Asset registry.*outside the allowed project root"):
        AssetMaterializer(outside_registry, remote_probe=lambda _url: True)


def test_symlink_escape_is_rejected(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    outside = tmp_path / "outside.mp4"
    outside.write_bytes(b"secret")
    link = project / "linked.mp4"
    link.symlink_to(outside)
    registry_path = _write_registry(
        project / "hype.assets.json",
        {"bad": {"file": link.name}},
    )

    with pytest.raises(ValueError, match="outside the allowed project root"):
        AssetMaterializer(registry_path, allowed_root=project)


def test_symlink_to_contained_file_is_staged_safely(tmp_path: Path) -> None:
    project = tmp_path / "project"
    source_dir = project / "sources"
    source_dir.mkdir(parents=True)
    source = source_dir / "source.mp4"
    source.write_bytes(b"contained target")
    link = project / "linked.mp4"
    link.symlink_to(source)
    registry_path = _write_registry(
        project / "hype.assets.json",
        {"asset": {"file": link.name}},
    )

    with AssetMaterializer(registry_path, allowed_root=project) as materializer:
        staged = materializer.assets["asset"].local_path
        assert staged is not None
        assert staged.read_bytes() == source.read_bytes()


def test_unmanaged_absolute_file_preserves_legacy_behavior(tmp_path: Path) -> None:
    registry_dir = tmp_path / "render"
    source_dir = tmp_path / "sources"
    registry_dir.mkdir()
    source_dir.mkdir()
    source = source_dir / "source.mp4"
    source.write_bytes(b"absolute source")
    registry_path = _write_registry(
        registry_dir / "hype.assets.json",
        {"source": {"file": str(source)}},
    )

    with AssetMaterializer(registry_path) as materializer:
        staged = materializer.assets["source"].local_path
        assert staged is not None
        assert staged.read_bytes() == source.read_bytes()


def test_server_binds_once_to_loopback_port_zero_and_joins_thread(tmp_path: Path) -> None:
    staging = tmp_path / "stage"
    staging.mkdir()
    asset = staging / "asset.bin"
    asset.write_bytes(b"abcdefghij")
    outside = tmp_path / "not-staged.bin"
    outside.write_bytes(b"must not be served")
    with _running_server(staging) as server:
        thread = server.thread
        assert server.bind_port == 0
        assert server.host == "127.0.0.1"
        assert server.server_address[0] == "127.0.0.1"
        assert server.port != 0
        assert thread is not None and thread.is_alive()
        status, headers, body = _read(server.local_url(asset))
        assert status == 200
        assert body == asset.read_bytes()
        # Requests without an Origin header are not browser CORS requests;
        # the server must not advertise a wildcard policy to arbitrary hosts.
        assert headers.get("Access-Control-Allow-Origin") is None
        with pytest.raises(urllib.error.HTTPError) as missing:
            _read(f"{server.base_url}/{outside.name}")
        assert missing.value.code == 404

    assert thread is not None and not thread.is_alive()
    server.close()
    assert not thread.is_alive()


def test_asset_server_allows_only_owned_remotion_browser_origin(tmp_path: Path) -> None:
    staging = tmp_path / "stage"
    staging.mkdir()
    asset = staging / "asset.bin"
    asset.write_bytes(b"cors-scoped asset")

    with _running_server(staging) as server:
        status, headers, body = _read(
            server.local_url(asset),
            origin=asset_service.REMOTION_BROWSER_ORIGIN,
        )
        assert status == 200
        assert body == asset.read_bytes()
        assert headers["Access-Control-Allow-Origin"] == asset_service.REMOTION_BROWSER_ORIGIN
        assert headers["Vary"] == "Origin"


def test_asset_server_allows_only_configured_remotion_browser_origin(tmp_path: Path) -> None:
    staging = tmp_path / "stage"
    staging.mkdir()
    asset = staging / "asset.bin"
    asset.write_bytes(b"dynamic-port asset")

    origin = "http://localhost:3001"
    with InvocationAssetServer(staging, allowed_origin=origin) as server:
        status, headers, body = _read(server.local_url(asset), origin=origin)
        assert status == 200
        assert body == asset.read_bytes()
        assert headers["Access-Control-Allow-Origin"] == origin
        assert headers["Vary"] == "Origin"

        for denied_origin in (
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:3001",
            "https://localhost:3001",
            "http://user:pass@localhost:3001",
            "http://localhost.evil:3001",
        ):
            _, denied_headers, _ = _read(
                server.local_url(asset), origin=denied_origin
            )
            assert denied_headers.get("Access-Control-Allow-Origin") is None


@pytest.mark.parametrize("origin", [
    "http://127.0.0.1:3000",
    "http://localhost",
    "https://localhost:3000",
    "http://localhost.evil:3001",
    "https://attacker.example",
])
def test_asset_server_does_not_advertise_cors_to_unowned_origins(
    tmp_path: Path,
    origin: str,
) -> None:
    staging = tmp_path / "stage"
    staging.mkdir()
    asset = staging / "asset.bin"
    asset.write_bytes(b"cors-private asset")

    with _running_server(staging) as server:
        status, headers, body = _read(server.local_url(asset), origin=origin)
        assert status == 200
        assert body == asset.read_bytes()
        assert headers.get("Access-Control-Allow-Origin") is None


def test_bound_socket_is_closed_when_thread_construction_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    staging = tmp_path / "stage"
    staging.mkdir()
    server = InvocationAssetServer(staging)
    closed: list[bool] = []

    class FakeHTTPServer:
        server_port = 43210

        def __init__(self, address: tuple[str, int], handler: object) -> None:
            assert address == ("127.0.0.1", 0)

        def serve_forever(self) -> None:
            return None

        def server_close(self) -> None:
            closed.append(True)

    def fail_thread(*args: object, **kwargs: object) -> threading.Thread:
        raise RuntimeError("thread construction failed")

    monkeypatch.setattr(asset_service, "ThreadingHTTPServer", FakeHTTPServer)
    monkeypatch.setattr(asset_service.threading, "Thread", fail_thread)
    with pytest.raises(RuntimeError, match="thread construction failed"):
        server.start()
    assert closed == [True]


def test_server_cleanup_failure_is_reported_and_retryable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    staging = tmp_path / "stage"
    staging.mkdir()
    calls: list[str] = []

    class FakeThread:
        def is_alive(self) -> bool:
            return False

        def join(self) -> None:
            calls.append("join")

    class FakeServer:
        def server_close(self) -> None:
            calls.append("close")
            if calls.count("close") == 1:
                raise OSError("close failed")

    server = InvocationAssetServer(staging)
    server._server = FakeServer()  # type: ignore[assignment]
    server.thread = FakeThread()  # type: ignore[assignment]
    with pytest.raises(OSError, match="close failed"):
        server.close()
    server.close()
    assert calls == ["close", "join", "close", "join"]


@pytest.mark.parametrize(
    "range_header",
    [
        "bytes=8-3",
        "bytes=99-",
        "bytes=0-1,4-5",
        "items=0-1",
        "bytes=-0",
        f"bytes={'9' * 5000}-",
    ],
)
def test_invalid_ranges_return_416(tmp_path: Path, range_header: str) -> None:
    staging = tmp_path / "stage"
    staging.mkdir()
    asset = staging / "asset.bin"
    asset.write_bytes(b"0123456789")
    with _running_server(staging) as server:
        with pytest.raises(urllib.error.HTTPError) as error:
            _read(server.local_url(asset), range_header=range_header)
    assert error.value.code == 416
    assert error.value.headers["Content-Range"] == "bytes */10"


def test_valid_single_bounded_and_suffix_ranges_return_206(tmp_path: Path) -> None:
    staging = tmp_path / "stage"
    staging.mkdir()
    asset = staging / "asset.bin"
    asset.write_bytes(b"0123456789")
    with _running_server(staging) as server:
        url = server.local_url(asset)
        bounded = _read(url, range_header="bytes=2-5")
        suffix = _read(url, range_header="bytes=-3")

    assert bounded[0] == 206
    assert bounded[1]["Content-Range"] == "bytes 2-5/10"
    assert bounded[2] == b"2345"
    assert suffix[0] == 206
    assert suffix[1]["Content-Range"] == "bytes 7-9/10"
    assert suffix[2] == b"789"


def test_staging_cleanup_runs_when_context_body_fails(tmp_path: Path) -> None:
    source = tmp_path / "source.bin"
    source.write_bytes(b"content")
    registry_path = _write_registry(
        tmp_path / "hype.assets.json",
        {"asset": {"file": source.name}},
    )
    staging_dir: Path | None = None

    with pytest.raises(RuntimeError, match="render failed"):
        with AssetMaterializer(registry_path) as materializer:
            staging_dir = materializer.staging_dir
            raise RuntimeError("render failed")

    assert staging_dir is not None
    assert not staging_dir.exists()


def test_partial_stage_is_removed_when_materialization_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry_path = _write_registry(
        tmp_path / "hype.assets.json",
        {"missing": {"file": "missing.mp4"}},
    )
    created: list[Path] = []
    real_mkdtemp = asset_service.tempfile.mkdtemp

    def tracked_mkdtemp(*args: object, **kwargs: object) -> str:
        result = real_mkdtemp(*args, **kwargs)
        created.append(Path(result))
        return result

    monkeypatch.setattr(asset_service.tempfile, "mkdtemp", tracked_mkdtemp)
    with pytest.raises(FileNotFoundError, match="missing file"):
        AssetMaterializer(registry_path)

    assert len(created) == 1
    assert not created[0].exists()


def test_overlapping_materializers_get_distinct_staging_dirs_and_urls(tmp_path: Path) -> None:
    source = tmp_path / "source.bin"
    source.write_bytes(b"same source")
    registry_path = _write_registry(
        tmp_path / "hype.assets.json",
        {"asset": {"file": source.name}},
    )

    with AssetMaterializer(registry_path) as first, AssetMaterializer(registry_path) as second:
        assert first.staging_dir != second.staging_dir
        with _running_server(first.staging_dir) as first_server, _running_server(
            second.staging_dir
        ) as second_server:
            first_url = first.resolved_registry(first_server)["assets"]["asset"]["file"]
            second_url = second.resolved_registry(second_server)["assets"]["asset"]["file"]
            assert first_url != second_url
            assert _read(first_url)[2] == b"same source"
            assert _read(second_url)[2] == b"same source"


def test_hardlink_failure_falls_back_to_copy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source.bin"
    source.write_bytes(b"copy fallback")
    registry_path = _write_registry(
        tmp_path / "hype.assets.json",
        {"asset": {"file": source.name}},
    )

    def fail_link(*args: object, **kwargs: object) -> None:
        raise OSError(errno.EXDEV, os.strerror(errno.EXDEV))

    monkeypatch.setattr(asset_service.os, "link", fail_link)
    with AssetMaterializer(registry_path) as materializer:
        staged_path = materializer.assets["asset"].local_path
        assert staged_path is not None
        assert staged_path.read_bytes() == source.read_bytes()
        assert staged_path.stat().st_ino != source.stat().st_ino


def test_cleanup_failure_is_reported_and_can_be_retried(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source.bin"
    source.write_bytes(b"cleanup")
    registry_path = _write_registry(
        tmp_path / "hype.assets.json",
        {"asset": {"file": source.name}},
    )
    materializer = AssetMaterializer(registry_path)
    real_rmtree = shutil.rmtree
    attempts = 0

    def fail_once(path: Path) -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise OSError("busy")
        real_rmtree(path)

    monkeypatch.setattr(asset_service.shutil, "rmtree", fail_once)
    with pytest.raises(OSError, match="busy"):
        materializer.close()
    assert materializer.staging_dir.exists()
    materializer.close()
    assert attempts == 2
    assert not materializer.staging_dir.exists()
