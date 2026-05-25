"""Test ensure-storage with mocked runpod_lifecycle."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from astrid import pipeline


# ---------------------------------------------------------------------------
# Find path (volume exists)
# ---------------------------------------------------------------------------


def test_ensure_storage_finds_existing() -> None:
    """ensure_storage returns immediately when volume exists."""
    existing_volume = {"id": "vol-abc", "name": "my-volume", "size": 50}

    with patch("runpod_lifecycle.Pod.get_storage", AsyncMock(return_value=existing_volume)):
        from astrid.core.runpod.storage import ensure_storage

        import asyncio

        result = asyncio.run(ensure_storage("my-volume", datacenter_id="US-GA-1"))
        assert result == existing_volume
        # Pod.create_storage should NOT have been called
        # (get_storage returned non-None, so we short-circuit)


# ---------------------------------------------------------------------------
# Create path (volume missing)
# ---------------------------------------------------------------------------


def test_ensure_storage_creates_when_missing() -> None:
    """ensure_storage calls create_storage when get_storage returns None."""
    created_volume = {"id": "vol-new", "name": "new-volume", "size": 100}

    with patch("runpod_lifecycle.Pod.get_storage", AsyncMock(return_value=None)), \
         patch("runpod_lifecycle.Pod.create_storage", AsyncMock(return_value=created_volume)) as create_storage:
        from astrid.core.runpod.storage import ensure_storage

        import asyncio

        result = asyncio.run(ensure_storage("new-volume", size_gb=100, datacenter_id="US-GA-1"))
        assert result == created_volume
        create_storage.assert_awaited_once_with("new-volume", 100, "US-GA-1")


def test_ensure_storage_raises_without_datacenter_when_missing() -> None:
    """ensure_storage raises ValueError without datacenter_id when volume missing."""
    import os
    os.environ["RUNPOD_API_KEY"] = "test-key-rpa_0000000000000000000000000000000000000000000000"

    try:
        with patch("runpod_lifecycle.Pod.get_storage", AsyncMock(return_value=None)):
            from astrid.core.runpod.storage import ensure_storage

            import asyncio

            with pytest.raises(ValueError, match="datacenter_id"):
                asyncio.run(ensure_storage("missing-vol"))
    finally:
        if os.environ.get("RUNPOD_API_KEY") == "test-key-rpa_0000000000000000000000000000000000000000000000":
            del os.environ["RUNPOD_API_KEY"]


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


def test_ensure_storage_idempotent() -> None:
    """Calling ensure_storage twice is idempotent."""
    existing = {"id": "vol-abc", "name": "idem-vol", "size": 50}

    call_count = 0

    async def get_storage(name: str):
        nonlocal call_count
        call_count += 1
        return existing

    async def create_storage(name: str, size_gb: int, datacenter_id: str):
        pytest.fail("create_storage should not be called when volume exists")

    with patch("runpod_lifecycle.Pod.get_storage", get_storage), \
         patch("runpod_lifecycle.Pod.create_storage", create_storage):
        from astrid.core.runpod.storage import ensure_storage

        import asyncio

        r1 = asyncio.run(ensure_storage("idem-vol", datacenter_id="US-GA-1"))
        r2 = asyncio.run(ensure_storage("idem-vol", datacenter_id="US-GA-1"))
        assert r1 == r2 == existing


def test_require_existing_storage_fails_without_creating_when_missing() -> None:
    """Storage-required executor paths report the ensure-storage command without creation."""
    from astrid.core.runpod.storage import ENSURE_STORAGE_HINT, require_existing_storage

    with patch("runpod_lifecycle.Pod.get_storage", AsyncMock(return_value=None)), \
         patch("runpod_lifecycle.Pod.create_storage", AsyncMock()) as create_storage:
        import asyncio

        with pytest.raises(ValueError, match="missing-vol"):
            asyncio.run(require_existing_storage("missing-vol", context="RunPod provision"))

        create_storage.assert_not_called()

    try:
        asyncio.run(require_existing_storage(None, context="RunPod session"))
    except ValueError as exc:
        message = str(exc)
    else:  # pragma: no cover - assertion guard
        pytest.fail("require_existing_storage should fail without a storage name")

    assert ENSURE_STORAGE_HINT in message
    assert "python3 -m astrid runpod ensure-storage <storage-name>" in message


# ---------------------------------------------------------------------------
# Provision/session executors do NOT auto-create storage
# ---------------------------------------------------------------------------

# Note: The provision and session executors in run.py do NOT call
# ensure_storage — they just pass storage_name through to launch().
# If that fails, the error propagates naturally. This test confirms
# the executors don't silently create volumes as a side-effect.


def test_provision_does_not_auto_create_storage() -> None:
    """provision executor does NOT invoke ensure_storage or create_storage."""
    # Read the run.py source and verify no auto-create paths
    run_py = Path(__file__).parent.parent.parent.parent / "astrid" / "packs" / "external" / "runpod" / "run.py"
    source = run_py.read_text()
    # The cmd_provision function should NOT reference ensure_storage
    # or Pod.create_storage
    assert "ensure_storage" not in source, (
        "provision executor must NOT auto-create storage volumes"
    )
    assert "create_storage" not in source, (
        "provision executor must NOT call create_storage"
    )


def test_storage_free_provision_and_session_do_not_probe_or_create_storage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Storage-free executor modes do not call get_storage or create_storage."""
    from astrid.packs.external.runpod.run import cmd_provision, cmd_session

    pod = MagicMock()
    pod.id = "pod-storage-free"
    pod.name = "astrid-storage-free"
    pod._storage_volume = None
    pod.wait_ready = AsyncMock()
    pod._ensure_ssh_details = AsyncMock(return_value={"ip": "1.2.3.4", "port": 2222})
    pod.terminate = AsyncMock()
    launch = AsyncMock(return_value=pod)

    class ProvisionArgs:
        gpu_type = "NVIDIA GeForce RTX 4090"
        storage_name = None
        require_storage = False
        max_runtime_seconds = None
        name_prefix = None
        image = None
        container_disk_gb = None
        datacenter_id = None
        ports = None

    class SessionArgs(ProvisionArgs):
        remote_root = None
        remote_script = None
        local_root = None
        timeout = None
        upload_mode = None
        excludes = None

    monkeypatch.setenv("RUNPOD_API_KEY", "test-key-rpa_0000000000000000000000000000000000000000000000")

    with patch("runpod_lifecycle.launch", launch), \
         patch("runpod_lifecycle.get_pod", AsyncMock(return_value=pod)), \
         patch("runpod_lifecycle.RunPodConfig", MagicMock()), \
         patch("runpod_lifecycle.Pod.get_storage", AsyncMock()) as get_storage, \
         patch("runpod_lifecycle.Pod.create_storage", AsyncMock()) as create_storage:
        assert cmd_provision(ProvisionArgs(), tmp_path / "provision") == 0
        assert cmd_session(SessionArgs(), tmp_path / "session") == 0

    get_storage.assert_not_called()
    create_storage.assert_not_called()


# ---------------------------------------------------------------------------
# list_volumes
# ---------------------------------------------------------------------------


def test_list_volumes_passthrough() -> None:
    """list_volumes passes through to api.get_network_volumes."""
    mock_volumes = [{"id": "v1", "name": "vol-a"}, {"id": "v2", "name": "vol-b"}]

    import os
    os.environ["RUNPOD_API_KEY"] = "test-key-rpa_0000000000000000000000000000000000000000000000"

    try:
        with patch("runpod_lifecycle.api.get_network_volumes", return_value=mock_volumes):
            from astrid.core.runpod.storage import list_volumes

            import asyncio

            result = asyncio.run(list_volumes())
            assert result == mock_volumes
    finally:
        if os.environ.get("RUNPOD_API_KEY") == "test-key-rpa_0000000000000000000000000000000000000000000000":
            del os.environ["RUNPOD_API_KEY"]


def test_runpod_volumes_ls_requires_api_key(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.delenv("RUNPOD_API_KEY", raising=False)

    rc = pipeline._dispatch_runpod_volumes(["ls"])

    assert rc == 1
    assert "RUNPOD_API_KEY is not set" in capsys.readouterr().err


def test_runpod_volumes_ls_emits_json_and_is_read_only(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("RUNPOD_API_KEY", "test-key-rpa_0000000000000000000000000000000000000000000000")
    volumes = [{"id": "vol-a", "name": "astrid-a"}]

    with patch("runpod_lifecycle.api.get_network_volumes", return_value=volumes), \
         patch("runpod_lifecycle.Pod.create_storage", AsyncMock()) as create_storage:
        rc = pipeline._dispatch_runpod_volumes(["ls"])

    assert rc == 0
    assert json.loads(capsys.readouterr().out) == volumes
    create_storage.assert_not_called()


def test_runpod_ensure_storage_cli_requires_datacenter_when_creation_needed(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("RUNPOD_API_KEY", "test-key-rpa_0000000000000000000000000000000000000000000000")

    with patch("runpod_lifecycle.Pod.get_storage", AsyncMock(return_value=None)), \
         patch("runpod_lifecycle.Pod.create_storage", AsyncMock()) as create_storage:
        rc = pipeline._dispatch_runpod_ensure_storage(["missing-vol"])

    assert rc == 1
    assert "datacenter_id is required" in capsys.readouterr().err
    create_storage.assert_not_called()


def test_runpod_ensure_storage_cli_supports_datacenter_id_alias(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("RUNPOD_API_KEY", "test-key-rpa_0000000000000000000000000000000000000000000000")
    created = {"id": "vol-new", "name": "new-volume", "size": 50}

    with patch("runpod_lifecycle.Pod.get_storage", AsyncMock(return_value=None)), \
         patch("runpod_lifecycle.Pod.create_storage", AsyncMock(return_value=created)):
        rc = pipeline._dispatch_runpod_ensure_storage(["new-volume", "--datacenter-id", "US-GA-1"])

    assert rc == 0
    assert json.loads(capsys.readouterr().out) == created
