"""Small honest Stage 1 composition against the pinned runtime head.

This test intentionally imports the sibling runtime service at the exact
checkout used for acceptance. The generated workspace client itself comes
from Astrid's packaged vendor copy, so this test does not inject a sibling
generated-client directory or monkeypatch the SDK transport.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
import pytest

WORKSPACE = Path(__file__).parents[3]
RUNTIME_WORKTREE = WORKSPACE / "banodoco-workspace-runtime-stage1-convergence"
RUNTIME_COMMIT = "03d847b9c3a16de0fca21be7e7c4fe4e29b0482f"
_RUNTIME_TMP = tempfile.TemporaryDirectory(prefix="astrid-runtime-archive-")
RUNTIME = Path(_RUNTIME_TMP.name)
archive = subprocess.run(
    ["git", "-C", str(RUNTIME_WORKTREE), "archive", "--format=tar", RUNTIME_COMMIT],
    check=True,
    capture_output=True,
).stdout
with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as tar:
    tar.extractall(RUNTIME)
sys.path.insert(0, str(RUNTIME))

from banodoco_workspace_client import WorkspaceClient  # noqa: E402
from astrid.core.execution.generic_host import GenericPackHost, RuntimeProtocolClient  # noqa: E402
from astrid.sdk.client import AstridClient  # noqa: E402


def _start_runtime(realm: Path, support: Path, runtime: Path = RUNTIME) -> tuple[subprocess.Popen[str], dict[str, str]]:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join((str(runtime), env.get("PYTHONPATH", "")))
    process = subprocess.Popen(
        [sys.executable, "-m", "runtime_protocol", "start", "--root", str(realm), "--support-root", str(support)],
        cwd=runtime,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert process.stdout is not None
    line = process.stdout.readline().strip()
    if not line:
        stderr = process.stderr.read() if process.stderr else ""
        process.kill()
        raise AssertionError(f"runtime did not publish startup metadata: {stderr}")
    metadata = json.loads(line)
    return process, metadata


def _stop_runtime(process: subprocess.Popen[str]) -> None:
    if process.poll() is None:
        process.terminate()
        process.wait(timeout=5)


def test_pinned_daemon_astrid_host_composition_survives_restart(tmp_path, monkeypatch):
    pack = tmp_path / "pack"
    pack.mkdir()
    (pack / "executor.yaml").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "id": "acceptance.echo",
                "name": "Acceptance Echo",
                "kind": "external",
                "version": "1.0",
                "command": {
                    "argv": [
                        "{python_exec}",
                        "-c",
                        "from pathlib import Path; Path('{out}/answer.txt').write_text('hello')",
                    ]
                },
                "outputs": [
                    {
                        "name": "answer",
                        "type": "file",
                        "path_template": "{out}/answer.txt",
                        "artifact_type": "text/plain",
                    }
                ],
                "metadata": {"adapter_family": "cpu", "resource_keys": ["cpu"]},
            }
        ),
        encoding="utf-8",
    )

    realm = tmp_path / "realm"
    support = tmp_path / "support"
    daemon, metadata = _start_runtime(realm, support)

    def connect():
        monkeypatch.setenv("BANODOCO_RUNTIME_ENDPOINT", metadata["endpoint"])
        monkeypatch.setenv("BANODOCO_RUNTIME_CREDENTIAL", str(support / "credentials" / "owner.token"))
        credential = support / "credentials" / "owner.token"
        # This acceptance is intentionally below a directly-started daemon;
        # use the complete explicit client contract rather than the retired
        # ambient AstridClient.open() inference path.
        astrid = AstridClient.open(
            endpoint=metadata["endpoint"],
            credential=credential,
            realm_id=metadata["realm_id"],
            actor_id="owner",
            client_name="astrid-cross-repository-acceptance",
            client_version="stage1",
            protocol_version="workspace.v1",
        )
        token = credential.read_text(encoding="utf-8").strip()
        return astrid, WorkspaceClient(metadata["endpoint"], token)

    try:
        astrid, generated = connect()
        project = astrid.projects.create(slug="acceptance", name="Acceptance", idempotency_key="project")
        assert project.ok
        project_id = project.data["project_id"]

        source = tmp_path / "source.bin"
        source.write_bytes(b"managed-media")
        media = astrid.media.import_file(project=project_id, path=source, idempotency_key="media")
        assert media.ok and media.data["media_type"] == "application/octet-stream"
        object_id = media.data["object_id"]
        source.unlink()
        assert astrid.media.verify(project_id, object_id).ok
        assert generated.get_object(object_id).data == b"managed-media"
        ranged = generated.get_object(object_id, byte_range=(0, 6))
        assert ranged.status == 206 and ranged.data == b"managed"
        assert generated.head_object(object_id).etag

        timeline = astrid.timelines.create(project=project_id, slug="main", config={}, registry={}, idempotency_key="timeline")
        assert timeline.ok
        timeline_id = timeline.data["timeline_id"]
        shot = astrid.shots.create(
            project=project_id,
            shot={"shot_id": "shot-1", "name": "Shot 1"},
            idempotency_key="shot",
        )
        reference = astrid.references.create(
            project=project_id,
            reference_id="reference-1",
            kind="object",
            name="Reference 1",
            media_id=object_id,
            idempotency_key="reference",
        )
        assert shot.ok and reference.ok
        assert astrid.shots.show(project_id, "shot-1").data["shot_id"] == "shot-1"
        assert astrid.references.show(project_id, "reference-1").data["reference_id"] == "reference-1"

        record = GenericPackHost(pack_roots=[pack]).discover()[0]
        host = GenericPackHost(
            pack_roots=[pack],
            client=RuntimeProtocolClient(metadata["endpoint"], (support / "credentials" / "owner.token").read_text().strip()),
            executor_id="acceptance-host",
        )
        assert host.register()["registration"].executor_id == "acceptance-host"
        capability_page, capability_cursor = generated.list_capabilities()
        assert capability_cursor is None
        registered = {item.capability_id: item for item in capability_page}
        assert registered[record.id].definition_digest == record.capability_digest
        task = generated.admit_task(
            capability_id=record.id,
            capability_digest=record.capability_digest,
            input_object_ids=[],
            project_id=project_id,
            idempotency_key="task",
        )
        claim = generated.claim_task(
            executor_id="acceptance-host",
            capability_ids=[record.id],
            idempotency_key="claim",
            runtime_epoch=generated.health().runtime_epoch,
        )
        assert claim and claim["task_id"] == task.task_id
        heartbeat = generated.heartbeat_attempt(
            claim["attempt_id"],
            lease_id=claim["lease_id"],
            fence=claim["fence"],
            idempotency_key="heartbeat",
            runtime_epoch=generated.health().runtime_epoch,
        )
        assert heartbeat["attempt_id"] == claim["attempt_id"]
        result = host.run_task(
            {
                "task": {
                    "id": task.task_id,
                    "capability": record.id,
                    "project_id": project_id,
                    "spec": {"spec": {"inputs": {}}},
                    "attempt_id": claim["attempt_id"],
                    "fence": claim["fence"],
                }
            },
            lease_token=claim["lease_id"],
            attempt_id=claim["attempt_id"],
            fence=claim["fence"],
        )
        assert result.state == "succeeded"
        assert generated.get_task(task.task_id).state == "succeeded"
        assert generated.get_run(task.run_id)["task_ids"] == [task.task_id]
        event_page, event_cursor = generated.list_run_events(task.run_id)
        assert event_cursor is None
        assert {event.event_type for event in event_page} >= {"task.admitted", "task.completed"}
        assert generated.get_object("sha256:" + hashlib.sha256(b"hello").hexdigest()).data == b"hello"

        _stop_runtime(daemon)
        daemon, metadata = _start_runtime(realm, support)
        reopened, restarted_generated = connect()
        assert reopened.projects.show(project_id).ok
        assert reopened.timelines.show(project_id, timeline_id).ok
        assert restarted_generated.get_task(task.task_id).state == "succeeded"
        assert restarted_generated.get_object(object_id).data == b"managed-media"
    finally:
        _stop_runtime(daemon)


def test_b71_project_shot_reference_sdk_crud_survives_restart(tmp_path, monkeypatch):
    # Always exercise the immutable acceptance runtime, never a dirty sibling
    # checkout whose contract digest may have advanced independently.
    runtime = RUNTIME
    realm, support = tmp_path / "realm", tmp_path / "support"
    daemon, metadata = _start_runtime(realm, support, runtime)
    monkeypatch.setenv("BANODOCO_RUNTIME_ENDPOINT", metadata["endpoint"])
    monkeypatch.setenv("BANODOCO_RUNTIME_CREDENTIAL", str(support / "credentials" / "owner.token"))
    monkeypatch.setenv("BANODOCO_RUNTIME_CHECKOUT", str(runtime))
    try:
        astrid = AstridClient.open(
            endpoint=metadata["endpoint"],
            credential=support / "credentials" / "owner.token",
            realm_id=metadata["realm_id"],
            actor_id="owner",
            client_name="astrid-cross-repository-acceptance",
            client_version="stage1",
            protocol_version="workspace.v1",
        )
        if not hasattr(astrid._remote.shots._client._generated, "create_project_shot"):
            pytest.skip("runtime contract does not expose project shot operations")
        project = astrid.projects.create(slug="b71", name="B71", idempotency_key="b71-project")
        other = astrid.projects.create(slug="b71-other", name="B71 Other", idempotency_key="b71-other")
        assert project.ok and other.ok
        project_id = project.data["project_id"]
        other_id = other.data["project_id"]
        source = tmp_path / "b71.bin"
        source.write_bytes(b"b71-media")
        media = astrid.media.import_file(project=project_id, path=source, idempotency_key="b71-media")
        assert media.ok
        shot = astrid.shots.create(project=project_id, shot={"shot_id": "b71-shot", "name": "B71 Shot"}, idempotency_key="b71-shot")
        reference = astrid.references.create(project=project_id, reference_id="b71-reference", kind="character", name="B71", media_id=media.data["object_id"], idempotency_key="b71-reference")
        assert shot.ok and reference.ok
        assert astrid.shots.create(project=project_id, shot={"shot_id": "b71-shot", "name": "B71 Shot"}, idempotency_key="b71-shot").data["shot_id"] == "b71-shot"
        assert astrid.shots.list(project_id).data[0][0]["shot_id"] == "b71-shot"
        assert astrid.shots.list(other_id).data[0] == []
        source2 = tmp_path / "b71-2.bin"
        source2.write_bytes(b"b71-media-2")
        media2 = astrid.media.import_file(project=project_id, path=source2, idempotency_key="b71-media-2")
        first_items = astrid.shots.add_item(project_id, "b71-shot", media_id=media.data["object_id"], position=0, idempotency_key="b71-item-1")
        second_items = astrid.shots.add_item(project_id, "b71-shot", media_id=media2.data["object_id"], position=1, idempotency_key="b71-item-2")
        item_ids = [item["item_id"] for item in second_items.data["items"]]
        reordered = astrid.shots.reorder(project_id, "b71-shot", item_ids=list(reversed(item_ids)), expected_version=second_items.data["version"], idempotency_key="b71-reorder")
        removed = astrid.shots.remove_item(project_id, "b71-shot", item_ids[0], expected_version=reordered.data["version"], idempotency_key="b71-remove")
        assert first_items.ok and media2.ok and removed.ok and len(removed.data["items"]) == 1
        updated = astrid.shots.update(project_id, "b71-shot", expected_version=1, name="B71 Updated", idempotency_key="b71-shot-update")
        assert updated.ok is False and updated.error.code == "conflict"
        updated = astrid.shots.update(project_id, "b71-shot", expected_version=removed.data["version"], name="B71 Updated", idempotency_key="b71-shot-update")
        assert updated.ok and updated.data["name"] == "B71 Updated"
        archived = astrid.shots.archive(project_id, "b71-shot", expected_version=updated.data["version"], idempotency_key="b71-shot-archive")
        recovered = astrid.shots.recover(project_id, "b71-shot", expected_version=archived.data["version"], idempotency_key="b71-shot-recover")
        assert archived.ok and recovered.ok and recovered.data["archived"] is False
        association = astrid.references.associate(project_id, "b71-reference", media_id=media2.data["object_id"], role="depicts", idempotency_key="b71-associate")
        secondary = astrid.references.create(project=project_id, reference_id="b71-reference-2", kind="object", name="Prop", media_id=media.data["object_id"], idempotency_key="b71-reference-2")
        primary = astrid.references.set_primary(project_id, "b71-reference", association_id=association.data["media_references"][-1]["association_id"], expected_version=association.data["version"], idempotency_key="b71-primary")
        link = astrid.references.link(project=project_id, from_reference_id="b71-reference", to_reference_id="b71-reference-2", kind="associated_with", idempotency_key="b71-link")
        assert association.ok and secondary.ok and primary.ok and link.ok
        _stop_runtime(daemon)
        daemon, metadata = _start_runtime(realm, support, runtime)
        monkeypatch.setenv("BANODOCO_RUNTIME_ENDPOINT", metadata["endpoint"])
        reopened = AstridClient.open(
            endpoint=metadata["endpoint"],
            credential=support / "credentials" / "owner.token",
            realm_id=metadata["realm_id"],
            actor_id="owner",
            client_name="astrid-cross-repository-acceptance",
            client_version="stage1",
            protocol_version="workspace.v1",
        )
        assert reopened.shots.show(project_id, "b71-shot").ok
        assert reopened.references.show(project_id, "b71-reference").ok
    finally:
        _stop_runtime(daemon)
