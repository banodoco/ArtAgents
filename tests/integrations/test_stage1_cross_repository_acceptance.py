"""Small honest Stage 1 composition against the pinned runtime head.

This test intentionally imports the sibling runtime at the exact checkout used
for acceptance instead of relying on an ambient installed runtime package.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
import pytest

WORKSPACE = Path(__file__).parents[3]
RUNTIME = WORKSPACE / "banodoco-workspace-runtime-stage1-convergence"
sys.path.insert(0, str(RUNTIME))
sys.path.insert(0, str(RUNTIME / "packages" / "python"))

from banodoco_workspace_client import WorkspaceClient  # noqa: E402
from astrid.core.execution.generic_host import GenericPackHost, RuntimeProtocolClient  # noqa: E402
from astrid.sdk.client import AstridClient  # noqa: E402


def _start_runtime(realm: Path, support: Path, runtime: Path = RUNTIME) -> tuple[subprocess.Popen[str], dict[str, str]]:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join((str(runtime), str(runtime / "packages" / "python"), env.get("PYTHONPATH", "")))
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
        return AstridClient.open(), WorkspaceClient(metadata["endpoint"], (support / "credentials" / "owner.token").read_text().strip())

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

        timeline = astrid.timelines.create(project=project_id, slug="main", idempotency_key="timeline")
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
        assert host.register()["registration"]["executor_id"] == "acceptance-host"
        assert host.register()["registration"]["executor_id"] == "acceptance-host"
        registered = {item.capability_id: item for item in generated.list_capabilities()}
        assert registered[record.id].definition_digest == record.capability_digest
        task = generated.admit_task(
            capability_id=record.id,
            capability_digest=record.capability_digest,
            input_object_ids=[],
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
                    "spec": {},
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
        events = generated.list_run_events(task.run_id)
        assert {event.event_type for event in events} >= {"task.admitted", "task.completed"}
        assert generated.get_object("sha256:" + hashlib.sha256(b"hello").hexdigest()).data == b"hello"

        astrid.close()
        _stop_runtime(daemon)
        daemon, metadata = _start_runtime(realm, support)
        reopened, restarted_generated = connect()
        assert reopened.projects.show(project_id).ok
        assert reopened.timelines.show(project_id, timeline_id).ok
        assert restarted_generated.get_task(task.task_id).state == "succeeded"
        assert restarted_generated.get_object(object_id).data == b"managed-media"
        reopened.close()
    finally:
        _stop_runtime(daemon)


def test_b71_project_shot_reference_sdk_crud_survives_restart(tmp_path, monkeypatch):
    runtime = Path(os.environ.get("BANODOCO_RUNTIME_CHECKOUT") or RUNTIME).expanduser().resolve()
    realm, support = tmp_path / "realm", tmp_path / "support"
    daemon, metadata = _start_runtime(realm, support, runtime)
    monkeypatch.setenv("BANODOCO_RUNTIME_ENDPOINT", metadata["endpoint"])
    monkeypatch.setenv("BANODOCO_RUNTIME_CREDENTIAL", str(support / "credentials" / "owner.token"))
    monkeypatch.setenv("BANODOCO_RUNTIME_CHECKOUT", str(runtime))
    try:
        for module_name in list(sys.modules):
            if module_name == "banodoco_workspace_client" or module_name.startswith("banodoco_workspace_client."):
                sys.modules.pop(module_name, None)
        astrid = AstridClient.open()
        if not hasattr(astrid._remote.shots._client._generated, "create_project_shot"):
            astrid.close()
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
        assert astrid.shots.list(project_id).data[0]["shot_id"] == "b71-shot"
        assert astrid.shots.list(other_id).data == []
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
        astrid.close()
        _stop_runtime(daemon)
        daemon, metadata = _start_runtime(realm, support, runtime)
        monkeypatch.setenv("BANODOCO_RUNTIME_ENDPOINT", metadata["endpoint"])
        reopened = AstridClient.open()
        assert reopened.shots.show(project_id, "b71-shot").ok
        assert reopened.references.show(project_id, "b71-reference").ok
        reopened.close()
    finally:
        _stop_runtime(daemon)
