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

WORKSPACE = Path(__file__).parents[3]
RUNTIME = WORKSPACE / "banodoco-workspace-runtime-stage1-convergence"
sys.path.insert(0, str(RUNTIME))
sys.path.insert(0, str(RUNTIME / "packages" / "python"))

from banodoco_workspace_client import WorkspaceClient  # noqa: E402
from astrid.core.execution.generic_host import GenericPackHost, RuntimeProtocolClient  # noqa: E402
from astrid.sdk.client import AstridClient  # noqa: E402


def _start_runtime(realm: Path, support: Path) -> tuple[subprocess.Popen[str], dict[str, str]]:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join((str(RUNTIME), str(RUNTIME / "packages" / "python"), env.get("PYTHONPATH", "")))
    process = subprocess.Popen(
        [sys.executable, "-m", "runtime_protocol", "start", "--root", str(realm), "--support-root", str(support)],
        cwd=RUNTIME,
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
            timeline_id=timeline_id,
            shot={"shot_id": "shot-1", "start_ms": 0, "duration_ms": 1000},
            idempotency_key="shot",
        )
        reference = astrid.references.create(
            timeline_id=timeline_id,
            reference_id="reference-1",
            object_id=object_id,
            role="source",
            idempotency_key="reference",
        )
        assert shot.ok and reference.ok
        assert astrid.timelines.show(project_id, timeline_id).data["references"][0]["reference_id"] == "reference-1"

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
        )
        assert claim and claim["task_id"] == task.task_id
        heartbeat = generated.heartbeat_attempt(
            claim["attempt_id"],
            lease_id=claim["lease_id"],
            fence=claim["fence"],
            idempotency_key="heartbeat",
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
