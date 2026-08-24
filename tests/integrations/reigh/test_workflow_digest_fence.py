"""Digest fence over vendored workflows (B-1a — pin the data, not the code).

Named primitives:

- Every shipped VibeComfy-bound registry entry pins ``(path, sha256)`` whose
  digest matches the vendored Comfy API-format bytes on disk.
- Registry/workflow drift fails import-time validation (compiler
  enforcement) — :func:`verify_registry_workflows`.
- A tampered workflow file refuses admission fail-closed (``422
  capability_unavailable`` naming the digest mismatch) BEFORE any byte is
  written to the authority.
"""

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from astrid.core.integrations.reigh import capabilities as caps
from astrid.core.integrations.reigh.capabilities import (
    BINDING_VIBECOMFY,
    REGISTRY,
    CapabilityUnavailable,
    verify_registry_workflows,
)
from tests.integrations.reigh.test_task_routes import (
    TS,
    _create_project,
    _db_count,
    _post,
    task_server,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def workflow_package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A mutable copy of the vendored workflows tree behind ``_PACKAGE_DIR``."""
    staged = tmp_path / "package"
    shutil.copytree(
        Path(caps.__file__).resolve().parent / "workflows",
        staged / "workflows",
    )
    monkeypatch.setattr(caps, "_PACKAGE_DIR", staged)
    return staged


def _tamper(staged: Path, name: str) -> None:
    path = staged / "workflows" / name
    raw = path.read_bytes()
    path.write_bytes(raw + b"\n")  # any byte drift breaks the pinned digest


# ---------------------------------------------------------------------------
# Primitive 1: every shipped workflow-backed entry pins matching bytes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("entry", sorted(REGISTRY.values(), key=lambda e: e.capability_id))
def test_vibecomfy_entries_pin_vendored_bytes_matching_disk(entry) -> None:
    if entry.binding != BINDING_VIBECOMFY:
        assert entry.template is None
        pytest.skip("non-vibecomfy binding carries no vendored workflow")
    if entry.capability_id == "local.workflow.run":
        assert entry.template is None
        pytest.skip("declared local workflows pin their own bytes")
    assert entry.template is not None, f"{entry.capability_id} must pin a workflow"
    rel_path, expected = entry.template
    raw = (Path(caps.__file__).resolve().parent / rel_path).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == expected
    # Comfy API-format JSON: one object keyed by numeric node ids.
    parsed = json.loads(raw)
    assert isinstance(parsed, dict) and parsed
    assert all(isinstance(key, str) for key in parsed)


def test_every_shipped_workflow_file_is_pinned_by_some_entry() -> None:
    workflows_dir = Path(caps.__file__).resolve().parent / "workflows"
    pinned = {
        entry.template[0].split("/", 1)[1]
        for entry in REGISTRY.values()
        if entry.template is not None
    }
    on_disk = {path.name for path in workflows_dir.glob("*.json")}
    assert on_disk == pinned, "vendored workflows and registry pins diverged"


# ---------------------------------------------------------------------------
# Primitive 2: import-time validation fails closed on drift
# ---------------------------------------------------------------------------


def test_verify_registry_workflows_fails_closed_on_digest_drift(
    workflow_package: Path,
) -> None:
    _tamper(workflow_package, "z_image.json")
    with pytest.raises(RuntimeError, match="digest drift"):
        verify_registry_workflows()


def test_verify_registry_workflows_fails_closed_on_missing_file(
    workflow_package: Path,
) -> None:
    (workflow_package / "workflows" / "qwen_image_edit.json").unlink()
    with pytest.raises(RuntimeError, match="is missing"):
        verify_registry_workflows()


# ---------------------------------------------------------------------------
# Primitive 3: tampered workflow ⇒ admission refuses before any write
# ---------------------------------------------------------------------------


def test_load_workflow_snapshot_names_exact_digest_mismatch(
    workflow_package: Path,
) -> None:
    _tamper(workflow_package, "basic_image_upscale.json")
    entry = REGISTRY["reigh.image_upscale"]
    expected = entry.template[1] if entry.template else ""
    with pytest.raises(CapabilityUnavailable) as excinfo:
        caps.load_workflow_snapshot(entry)
    assert expected[:12] in excinfo.value.hint
    assert excinfo.value.identifier == "reigh.image_upscale"


def test_tampered_workflow_refuses_admission_before_any_write(
    tmp_bridge_root: Path,
    workflow_package: Path,
) -> None:
    _tamper(workflow_package, "basic_image_upscale.json")
    slug = "proj-digestfence"
    with task_server(tmp_bridge_root) as env:
        composition = env["composition"]
        _create_project(composition, slug)
        # Project seeding legitimately writes rows; record that baseline so
        # the refusal is provable as zero NEW authoritative writes.
        baseline_receipts = _db_count(
            composition, "SELECT COUNT(*) FROM command_receipts"
        )
        status, body = _post(
            env,
            f"/projects/{slug}/tasks",
            key=f"{TS}-digest-fence",
            body={
                "family": "image_upscale",
                "input": {"image_url": "http://127.0.0.1:9/x.png"},
            },
        )
        assert status == 422
        assert body["error"] == "capability_unavailable"
        assert "digest mismatch" in body["detail"]
        assert _db_count(composition, "SELECT COUNT(*) FROM tasks") == 0
        assert (
            _db_count(composition, "SELECT COUNT(*) FROM command_receipts")
            == baseline_receipts
        )


def test_admission_snapshots_verified_workflow_into_spec_provenance(
    tmp_bridge_root: Path,
) -> None:
    """Untampered admission records the exact vendored bytes in spec_json."""
    slug = "proj-wfsnapshot"
    with task_server(tmp_bridge_root) as env:
        composition = env["composition"]
        _create_project(composition, slug)
        status, body = _post(
            env,
            f"/projects/{slug}/tasks",
            key=f"{TS}-wf-snapshot",
            body={
                "family": "image_upscale",
                "input": {"image_url": "http://127.0.0.1:9/x.png"},
            },
        )
        assert status == 201
        task_id = body["task"]["id"]
        with composition.writer.read_only_connection() as conn:
            row = conn.execute(
                "SELECT spec_json FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
        spec = json.loads(row[0])
        snapshot = spec["workflow"]
        entry = REGISTRY["reigh.image_upscale"]
        assert spec["definition_version"] == entry.definition_version
        assert snapshot["path"] == entry.template[0]
        assert snapshot["sha256"] == entry.template[1]
        raw = (
            Path(caps.__file__).resolve().parent / entry.template[0]
        ).read_bytes()
        assert (
            hashlib.sha256(
                json.dumps(
                    snapshot["workflow"], indent=2, sort_keys=True
                ).encode()
                + b"\n"
            ).hexdigest()
            == hashlib.sha256(raw).hexdigest()
        )


def test_replay_after_snapshot_is_byte_stable(tmp_bridge_root: Path) -> None:
    """Idempotent replay resolves to the same admitted workflow snapshot."""
    slug = "proj-wfreplay"
    key = f"{TS}-wf-replay"
    body_payload = {
        "family": "image_upscale",
        "input": {"image_url": "http://127.0.0.1:9/x.png"},
    }
    with task_server(tmp_bridge_root) as env:
        composition = env["composition"]
        _create_project(composition, slug)
        first_status, first = _post(
            env, f"/projects/{slug}/tasks", key=key, body=body_payload
        )
        second_status, second = _post(
            env, f"/projects/{slug}/tasks", key=key, body=body_payload
        )
        assert (first_status, second_status) == (201, 200)
        assert first["task"]["id"] == second["task"]["id"]
        assert _db_count(composition, "SELECT COUNT(*) FROM tasks") == 1
