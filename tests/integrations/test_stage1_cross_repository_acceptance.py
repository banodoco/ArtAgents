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

ASTRID_SOURCE = Path(
    subprocess.run(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
).parent
WORKSPACE = ASTRID_SOURCE.parent
RUNTIME_WORKTREE = (
    WORKSPACE
    / "banodoco-workspace-runtime"
    / ".otto/worktrees/generation-candidate-promotion-20260901"
)
RUNTIME_COMMIT = "4050394c5395206f1ec6bf0d905ffbfb7bb0e4de"
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

from astrid.core.execution.generic_host import GenericPackHost, RuntimeProtocolClient  # noqa: E402
from astrid.packs.generation.executors.generate_image.task_adapter import (  # noqa: E402
    validate_shot_generation_recipe,
)
from astrid.sdk.client import AstridClient  # noqa: E402
from banodoco_workspace_client import WorkspaceClient  # noqa: E402


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


def test_generation_candidate_promotion_preserves_receipt_provenance_and_replay(
    tmp_path, monkeypatch
):
    """Prove Astrid's recipe reaches the runtime-owned atomic promotion seam."""
    realm, support = tmp_path / "realm", tmp_path / "support"
    daemon, metadata = _start_runtime(realm, support)
    monkeypatch.setenv("BANODOCO_RUNTIME_ENDPOINT", metadata["endpoint"])
    monkeypatch.setenv(
        "BANODOCO_RUNTIME_CREDENTIAL",
        str(support / "credentials" / "owner.token"),
    )
    try:
        astrid = AstridClient.open(
            endpoint=metadata["endpoint"],
            credential=support / "credentials" / "owner.token",
            realm_id=metadata["realm_id"],
            actor_id="owner",
            client_name="astrid-generation-promotion-acceptance",
            client_version="stage1",
            protocol_version="workspace.v1",
        )
        project = astrid.projects.create(
            slug="promotion", name="Promotion", idempotency_key="promotion-project"
        )
        assert project.ok
        project_id = project.data["project_id"]
        shot_id = "shot-generation-bridge"
        assert astrid.shots.create(
            project=project_id,
            shot={"shot_id": shot_id, "name": "Generation Bridge"},
            idempotency_key="promotion-shot",
        ).ok

        def ingest(name: str, content: bytes):
            path = tmp_path / name
            path.write_bytes(content)
            result = astrid.media.import_file(
                project=project_id,
                path=path,
                idempotency_key=f"promotion-media-{name.replace('.', '-')}",
            )
            assert result.ok
            return result.data["object_id"]

        old_media = ingest("old.png", b"old-primary")
        candidate_media = ingest("candidate.png", b"generated-candidate")
        plate_media = ingest("plate.png", b"derived-plate")
        proxy_media = ingest("proxy.png", b"derived-proxy")
        prompt_media = ingest("prompt.txt", b"a precise generated candidate")
        reference_media = ingest("reference.png", b"reference-input")

        def bare(media_id: str) -> str:
            return media_id.removeprefix("sha256:")

        recipe = {
            "schema": "astrid.shot-generation-recipe/v1",
            "project_id": project_id,
            "shot_id": shot_id,
            "target_role": "primary_visual",
            "prompt_binding": {
                "id": "binding-generation-bridge",
                "head": 1,
                "media_id": prompt_media,
                "content_sha256": bare(prompt_media),
            },
            "generator": {
                "capability_id": "generation.generate_image",
                "model": "z-image",
                "backend": "cloud",
                "mode": "t2i",
                "settings": {"seed": 42},
            },
            "inputs": [
                {
                    "ordinal": 0,
                    "role": "style",
                    "reference_id": "reference-generation-bridge",
                    "media_id": reference_media,
                    "content_sha256": bare(reference_media),
                }
            ],
            "parent_media_id": old_media,
            "parent_content_sha256": bare(old_media),
        }
        assert validate_shot_generation_recipe(
            recipe,
            project_id=project_id,
            model="z-image",
            mode="t2i",
            execution="cloud",
            resolved_settings={"seed": 42},
        ) == recipe

        primary = astrid.shots.add_item(
            project_id,
            shot_id,
            media_id=old_media,
            metadata={"role": "primary_visual", "status": "primary"},
            idempotency_key="promotion-primary",
        )
        primary_item = next(
            item for item in primary.data["items"] if item["media_id"] == bare(old_media)
        )
        plate = astrid.shots.add_item(
            project_id,
            shot_id,
            media_id=plate_media,
            metadata={
                "kind": "plate",
                "source_item_id": primary_item["item_id"],
                "source_media_id": old_media,
                "source_content_sha256": bare(old_media),
            },
            idempotency_key="promotion-plate",
        )
        plate_item = next(
            item for item in plate.data["items"] if item["media_id"] == bare(plate_media)
        )
        proxy = astrid.shots.add_item(
            project_id,
            shot_id,
            media_id=proxy_media,
            metadata={
                "kind": "proxy",
                "source_item_id": plate_item["item_id"],
                "source_media_id": plate_media,
                "source_content_sha256": bare(plate_media),
            },
            idempotency_key="promotion-proxy",
        )
        proxy_item = next(
            item for item in proxy.data["items"] if item["media_id"] == bare(proxy_media)
        )
        candidate = astrid.shots.add_item(
            project_id,
            shot_id,
            media_id=candidate_media,
            metadata={
                "role": "primary_visual",
                "status": "candidate",
                "content_sha256": bare(candidate_media),
                "recipe": recipe,
                "provenance": {
                    "project_id": project_id,
                    "shot_id": shot_id,
                    "target_role": "primary_visual",
                    "media_id": candidate_media,
                },
            },
            idempotency_key="promotion-candidate",
        )
        candidate_item = next(
            item
            for item in candidate.data["items"]
            if item["media_id"] == bare(candidate_media)
        )
        timeline_assets = [
            {
                "id": "timeline-generation-bridge",
                "metadata": {
                    "source_item_id": primary_item["item_id"],
                    "source_media_id": old_media,
                    "source_content_sha256": bare(old_media),
                },
            }
        ]
        promoted = astrid.shots.promote_candidate(
            project_id,
            shot_id,
            candidate_item["item_id"],
            expected_head_seq=candidate.data["version"],
            timeline_assets=timeline_assets,
            idempotency_key="promotion-command",
        )
        assert promoted.ok and promoted.receipt is not None
        assert promoted.receipt.command_kind == "shot.promote_candidate"
        assert promoted.receipt.result == promoted.data
        assert promoted.data["promotion"]["primary_item_id"] == candidate_item["item_id"]
        stale = {
            entry.get("item_id") or entry.get("asset_id")
            for entry in promoted.data["invalidation"]["stale"]
        }
        assert stale >= {
            plate_item["item_id"],
            proxy_item["item_id"],
            "timeline-generation-bridge",
        }

        replay = astrid.shots.promote_candidate(
            project_id,
            shot_id,
            candidate_item["item_id"],
            expected_head_seq=candidate.data["version"],
            timeline_assets=timeline_assets,
            idempotency_key="promotion-command",
        )
        assert replay.ok and replay.data == promoted.data
        assert replay.receipt is not None
        assert replay.receipt.to_json() == promoted.receipt.to_json()
        shown = astrid.shots.show(project_id, shot_id)
        primary_items = [
            item
            for item in shown.data["items"]
            if item["metadata"].get("role") == "primary_visual"
        ]
        assert sum(item["metadata"].get("status") == "primary" for item in primary_items) == 1
        assert any(
            item["item_id"] == primary_item["item_id"]
            and item["metadata"].get("status") == "superseded"
            for item in primary_items
        )

        foreign_media = ingest("foreign.png", b"foreign-provenance-candidate")
        foreign = astrid.shots.add_item(
            project_id,
            shot_id,
            media_id=foreign_media,
            metadata={
                "role": "primary_visual",
                "status": "candidate",
                "provenance": {
                    "project_id": "foreign-project",
                    "shot_id": shot_id,
                    "target_role": "primary_visual",
                    "media_id": foreign_media,
                },
            },
            idempotency_key="promotion-foreign-candidate",
        )
        foreign_item = next(
            item
            for item in foreign.data["items"]
            if item["media_id"] == bare(foreign_media)
        )
        rejected = astrid.shots.promote_candidate(
            project_id,
            shot_id,
            foreign_item["item_id"],
            expected_head_seq=foreign.data["version"],
            idempotency_key="promotion-foreign-command",
        )
        assert not rejected.ok and rejected.error.code == "validation_error"
        unchanged = astrid.shots.show(project_id, shot_id)
        assert unchanged.data["version"] == foreign.data["version"]
        assert next(
            item
            for item in unchanged.data["items"]
            if item["item_id"] == foreign_item["item_id"]
        )["metadata"]["status"] == "candidate"
    finally:
        _stop_runtime(daemon)
