from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import threading
import urllib.error
import urllib.request

import pytest

from astrid.core.rendering import assets as asset_service
from astrid.core.rendering.assets import AssetMaterializer, InvocationAssetServer


def _write_registry(path: Path, *, object_id: str, payload: bytes, digest: str | None = None) -> Path:
    path.write_text(json.dumps({"assets": {"main": {
        "object_id": object_id,
        "digest": digest or hashlib.sha256(payload).hexdigest(),
        "type": "application/octet-stream",
    }}}), encoding="utf-8")
    return path


def _read(url: str, *, range_header: str | None = None, origin: str | None = None):
    headers: dict[str, str] = {}
    if range_header:
        headers["Range"] = range_header
    if origin:
        headers["Origin"] = origin
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=5) as response:
        return response.status, response.headers, response.read()


@pytest.fixture
def server():
    servers: list[InvocationAssetServer] = []

    def start(staging: Path) -> InvocationAssetServer:
        value = InvocationAssetServer(staging)
        try:
            value.__enter__()
        except PermissionError:
            pytest.skip("local HTTP server bind is not permitted in this sandbox")
        servers.append(value)
        return value

    yield start
    for value in servers:
        value.__exit__(None, None, None)


def test_runtime_materialized_bytes_are_staged_served_with_range_and_cleaned(tmp_path: Path, server) -> None:
    payload = b"runtime materialized asset bytes"
    registry = _write_registry(tmp_path / "hype.assets.json", object_id="media-1", payload=payload)
    with AssetMaterializer(registry, materialized_objects={"media-1": payload}) as materializer:
        staging = materializer.staging_dir
        staged = materializer.assets["main"]
        assert staged.kind == "managed"
        assert staged.local_path is not None and staged.local_path.read_bytes() == payload
        running = server(staging)
        url = materializer.resolved_registry(running)["assets"]["main"]["file"]
        status, headers, body = _read(url, range_header="bytes=8-", origin="http://localhost:3000")
        assert status == 206 and body == payload[8:]
        assert headers["Content-Range"] == f"bytes 8-{len(payload) - 1}/{len(payload)}"
        assert headers["Access-Control-Allow-Origin"] == "http://localhost:3000"
    assert not staging.exists()


def test_path_backed_runtime_object_requires_explicit_materialized_root(tmp_path: Path) -> None:
    payload = b"path-backed object"
    root = tmp_path / "materialized"
    root.mkdir()
    source = root / "object.bin"
    source.write_bytes(payload)
    registry = _write_registry(tmp_path / "assets.json", object_id="media-path", payload=payload)
    with pytest.raises(ValueError, match="materialized_root"):
        AssetMaterializer(registry, materialized_objects={"media-path": source})
    with AssetMaterializer(registry, materialized_objects={"media-path": source}, materialized_root=root) as materializer:
        assert materializer.assets["main"].local_path.read_bytes() == payload


def test_runtime_object_digest_is_verified_before_staging(tmp_path: Path) -> None:
    payload = b"actual bytes"
    registry = _write_registry(tmp_path / "assets.json", object_id="media-1", payload=payload, digest=hashlib.sha256(b"different").hexdigest())
    with pytest.raises(ValueError, match="integrity check"):
        AssetMaterializer(registry, materialized_objects={"media-1": payload})


def test_registry_rejects_retired_locators_and_requires_runtime_identity(tmp_path: Path) -> None:
    path = tmp_path / "assets.json"
    path.write_text(json.dumps({"assets": {"main": {"file": "local.mp4"}}}), encoding="utf-8")
    with pytest.raises(ValueError, match="retired media locator"):
        AssetMaterializer(path)
    path.write_text(json.dumps({"assets": {"main": {"digest": "a" * 64}}}), encoding="utf-8")
    with pytest.raises(ValueError, match="object_id"):
        AssetMaterializer(path)


def test_missing_runtime_object_removes_partial_stage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    registry = _write_registry(tmp_path / "assets.json", object_id="missing", payload=b"x")
    created: list[Path] = []
    real_mkdtemp = asset_service.tempfile.mkdtemp

    def tracked_mkdtemp(*args: object, **kwargs: object) -> str:
        result = real_mkdtemp(*args, **kwargs)
        created.append(Path(result))
        return result

    monkeypatch.setattr(asset_service.tempfile, "mkdtemp", tracked_mkdtemp)
    with pytest.raises(FileNotFoundError, match="no runtime materialized object"):
        AssetMaterializer(registry)
    assert created and not created[0].exists()


def test_symlink_runtime_materialization_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "materialized"
    root.mkdir()
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"secret")
    link = root / "object.bin"
    link.symlink_to(outside)
    registry = _write_registry(tmp_path / "assets.json", object_id="media-link", payload=b"secret")
    with pytest.raises(ValueError, match="may not be a symlink"):
        AssetMaterializer(registry, materialized_objects={"media-link": link}, materialized_root=root)


def test_overlapping_materializers_have_distinct_staging_dirs(tmp_path: Path) -> None:
    payload = b"same object"
    registry = _write_registry(tmp_path / "assets.json", object_id="media-1", payload=payload)
    first = AssetMaterializer(registry, materialized_objects={"media-1": payload})
    second = AssetMaterializer(registry, materialized_objects={"media-1": payload})
    try:
        assert first.staging_dir != second.staging_dir
        assert first.assets["main"].local_path != second.assets["main"].local_path
    finally:
        first.close()
        second.close()


def test_cleanup_runs_when_render_body_fails(tmp_path: Path) -> None:
    payload = b"content"
    registry = _write_registry(tmp_path / "assets.json", object_id="media-1", payload=payload)
    with pytest.raises(RuntimeError, match="render failed"):
        with AssetMaterializer(registry, materialized_objects={"media-1": payload}) as materializer:
            staging = materializer.staging_dir
            raise RuntimeError("render failed")
    assert not staging.exists()


def test_asset_materializer_has_no_local_storage_authority() -> None:
    source = Path(asset_service.__file__).read_text(encoding="utf-8")
    assert "sqlite3" not in source and "derive_database_path" not in source


def test_asset_server_is_loopback_single_port_and_joins_thread(tmp_path: Path, server) -> None:
    staging = tmp_path / "stage"
    staging.mkdir()
    asset = staging / "asset.bin"
    asset.write_bytes(b"abcdefghij")
    with server(staging) as running:
        thread = running.thread
        assert running.host == "127.0.0.1" and running.bind_port == 0
        assert running.server_address[0] == "127.0.0.1" and running.port != 0
        assert _read(running.local_url(asset))[2] == asset.read_bytes()
        with pytest.raises(urllib.error.HTTPError) as missing:
            _read(f"{running.base_url}/outside.bin")
        assert missing.value.code == 404
    assert thread is not None and not thread.is_alive()
    running.close()


def test_asset_server_cors_allows_exact_origin_and_denies_near_matches(tmp_path: Path, server) -> None:
    staging = tmp_path / "stage"
    staging.mkdir()
    asset = staging / "asset.bin"
    asset.write_bytes(b"cors")
    with server(staging) as running:
        _, allowed, _ = _read(running.local_url(asset), origin=asset_service.REMOTION_BROWSER_ORIGIN)
        assert allowed["Access-Control-Allow-Origin"] == asset_service.REMOTION_BROWSER_ORIGIN
        assert allowed["Vary"] == "Origin"
        for origin in ("http://localhost", "http://localhost:3001", "http://127.0.0.1:3000", "https://localhost:3000", "http://localhost.evil:3000"):
            _, denied, _ = _read(running.local_url(asset), origin=origin)
            assert denied.get("Access-Control-Allow-Origin") is None


def test_asset_server_custom_cors_origin_is_exact(tmp_path: Path) -> None:
    staging = tmp_path / "stage"
    staging.mkdir()
    asset = staging / "asset.bin"
    asset.write_bytes(b"cors")
    with InvocationAssetServer(staging, allowed_origin="http://localhost:3001") as running:
        _, allowed, _ = _read(running.local_url(asset), origin="http://localhost:3001")
        assert allowed["Access-Control-Allow-Origin"] == "http://localhost:3001"
        _, denied, _ = _read(running.local_url(asset), origin="http://localhost:3000")
        assert denied.get("Access-Control-Allow-Origin") is None


def test_server_closes_socket_when_thread_creation_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    staging = tmp_path / "stage"
    staging.mkdir()
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
        InvocationAssetServer(staging).start()
    assert closed == [True]


def test_server_cleanup_failure_is_reported_and_retryable(tmp_path: Path) -> None:
    staging = tmp_path / "stage"
    staging.mkdir()
    calls: list[str] = []

    class FakeThread:
        def is_alive(self) -> bool: return False
        def join(self) -> None: calls.append("join")

    class FakeServer:
        def server_close(self) -> None:
            calls.append("close")
            if calls.count("close") == 1:
                raise OSError("close failed")

    running = InvocationAssetServer(staging)
    running._server = FakeServer()  # type: ignore[assignment]
    running.thread = FakeThread()  # type: ignore[assignment]
    with pytest.raises(OSError, match="close failed"):
        running.close()
    running.close()
    assert calls == ["close", "join", "close", "join"]


@pytest.mark.parametrize("range_header", [
    "bytes=8-3", "bytes=99-", "bytes=0-1,4-5", "items=0-1", "bytes=-0", "bytes=999999999999-",
])
def test_invalid_ranges_return_416_with_unsatisfied_content_range(tmp_path: Path, range_header: str, server) -> None:
    staging = tmp_path / "stage"
    staging.mkdir()
    asset = staging / "asset.bin"
    asset.write_bytes(b"0123456789")
    with server(staging) as running:
        with pytest.raises(urllib.error.HTTPError) as error:
            _read(running.local_url(asset), range_header=range_header)
    assert error.value.code == 416
    assert error.value.headers["Accept-Ranges"] == "bytes"
    assert error.value.headers["Content-Range"] == "bytes */10"


def test_bounded_and_suffix_ranges_return_206_headers_and_exact_bytes(tmp_path: Path, server) -> None:
    staging = tmp_path / "stage"
    staging.mkdir()
    asset = staging / "asset.bin"
    asset.write_bytes(b"0123456789")
    with server(staging) as running:
        bounded = _read(running.local_url(asset), range_header="bytes=2-5")
        suffix = _read(running.local_url(asset), range_header="bytes=-3")
    assert bounded[0] == 206 and bounded[2] == b"2345"
    assert bounded[1]["Accept-Ranges"] == "bytes" and bounded[1]["Content-Length"] == "4"
    assert bounded[1]["Content-Range"] == "bytes 2-5/10"
    assert suffix[0] == 206 and suffix[2] == b"789"
    assert suffix[1]["Content-Range"] == "bytes 7-9/10"


def test_materializer_cleanup_failure_is_reported_and_retryable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = b"cleanup"
    registry = _write_registry(tmp_path / "assets.json", object_id="m1", payload=payload)
    materializer = AssetMaterializer(registry, materialized_objects={"m1": payload})
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
    assert attempts == 2 and not materializer.staging_dir.exists()
